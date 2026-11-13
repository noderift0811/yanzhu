"""输出安全护栏：危机识别、医疗越界拦截、禁用语、PII 脱敏。

对应评分表的「AI 安全 4 分」，但更重要是对应本届选题要求的
「AI 功能是核心而非附属」——护栏不是页面上另开了个"安全检查"按钮，
而是串在 Agent 的 validate 步骤里，直接决定：
  - 生成的 system_prompt 会被确定性注入边界（不靠模型自觉）
  - 越界产出会被判 needs_review 并触发 fallback 步骤
  - 聊天运行时的人格 AI 因此也带着同一套边界

设计原则：陪伴场景里**不阻断用户说话**。危机表达只触发资源注入，
不做弹窗拦截、不说教；被拦的是"我们生成的内容"，不是"用户"。
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

# 口语优先：真实求助不会说「本人有自伤意念」
CRISIS_PATTERNS = [
    r"不想活", r"活不下去", r"撑不下去", r"不想醒来", r"没有活下去",
    r"结束(?:自己的)?生命", r"一了百了", r"了结(?:自己|一切)", r"轻生",
    r"自杀", r"自残", r"自伤", r"伤害自己", r"想死", r"不想存在",
]
MEDICAL_PATTERNS = [
    r"(?:诊断|确诊)(?:为|是|成)", r"你(?:是|得了|患有)[^。；]{0,12}(?:抑郁|焦虑|双相|精神|癌症)",
    r"(?:服用|吃|开|加点|减点)[^。；]{0,12}(?:药|剂量|毫克|mg|片)",
    r"(?:建议|应该|最好)(?:你)?[^。；]{0,8}(?:吃药|服药|停药|加量|减量|就医|住院)",
    r"(?:处方|疗程|剂量|用法用量|疗效)",
]
TOXIC_PATTERNS = [
    r"想开点", r"别矫情", r"这有什么好", r"至少你还", r"都会好起来的",
    r"你要坚强", r"别想太多", r"比你难的人",
]
PII_PATTERNS = [
    ("phone", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("id_card", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
]

_COMPILED = {
    "crisis": [re.compile(p) for p in CRISIS_PATTERNS],
    "medical": [re.compile(p) for p in MEDICAL_PATTERNS],
    "toxic": [re.compile(p) for p in TOXIC_PATTERNS],
}

# 否定语境豁免：「不说想开点」「别矫情之类的话都别讲」是在**禁止**这些表达，
# 若按字面命中就把用户/预设判成越界，等于逼着大家不能用反例说明边界。
# 只在同一小句内、命中点前 8 字以内出现否定词时豁免；跨句号不豁免。
_NEGATION_PREFIX = re.compile(r"(?:不|别|避免|禁止|严禁|切勿|不得|拒绝|回避|禁用|不用|少)[^。；！？\n]{0,8}$")


def _pattern_hit(pats, text: str) -> bool:
    for p in pats:
        for m in p.finditer(text):
            prefix = text[max(0, m.start() - 14): m.start()]
            if _NEGATION_PREFIX.search(prefix):
                continue
            return True
    return False

CRISIS_RESOURCES = [
    "情况紧急请拨打当地急救电话 120 或报警 110",
    "需要有人说话可拨打全国心理援助热线 12356（以当地公布为准）",
    "联系身边信任的人，或前往就近医院急诊",
]

SAFETY_MARK = "【安全边界·必须遵守】"
SAFETY_STRICT = (
    "不做诊断、不开药、不评估病情、不替用户做决定；"
    "不使用「想开点」「别矫情」「至少你还」这类否定感受的话；"
    "不追问姓名、住址、病历号、手机号等隐私，也不在回复里复述它们；"
    "短句、一次只问一个问题，留白比长篇安慰更有用。"
    "若对方出现伤害自己或他人的表达，先清楚给出求助路径："
    "紧急拨打 120 / 110，需要有人说话可拨打全国心理援助热线 12356（以当地公布为准），"
    "或联系身边信任的人、前往就近医院急诊；之后回到平静陪伴的语气。"
)
SAFETY_NORMAL = (
    "不生成 HTML、脚本或外链；不收集或复述可识别个人信息；"
    "遇到伤害自己或他人的表达时，先给出 120 / 110 与心理援助热线 12356 等求助路径。"
)


@dataclass
class GuardReport:
    level: str = "normal"
    flags: List[str] = field(default_factory=list)
    blocked: bool = False
    redacted_text: str = ""
    resources: List[str] = field(default_factory=list)
    summary: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def redact_pii(text: str):
    """返回 (脱敏文本, 命中的 PII 类型)。用于日志与页面文案，不改数据库里的原始消息。"""
    out = text or ""
    hits: List[str] = []
    for label, pat in PII_PATTERNS:
        if pat.search(out):
            hits.append(label)
            out = pat.sub(f"[{label} 已脱敏]", out)
    return out, hits


def scan(text: str, level: str = "normal") -> GuardReport:
    """扫描任意文本（用户输入 / 生成的人设 / 聊天回复）。"""
    s = text or ""
    flags: List[str] = []
    for kind, pats in _COMPILED.items():
        if _pattern_hit(pats, s):
            flags.append(f"{kind}_expression")
    _, pii = redact_pii(s)
    flags.extend(f"pii_{p}" for p in pii)
    redacted, _ = redact_pii(s)

    crisis = "crisis_expression" in flags
    # 被拦的是"我们生成的内容"越界，不是用户说话；用户输入永远不 blocked
    blocked = level == "strict" and (
        "medical_expression" in flags or "toxic_expression" in flags
    )
    report = GuardReport(
        level=level,
        flags=flags,
        blocked=blocked,
        redacted_text=redacted,
        resources=list(CRISIS_RESOURCES) if crisis else [],
        summary=_summarize(flags, blocked),
    )
    return report


def _summarize(flags: List[str], blocked: bool) -> str:
    if not flags:
        return "未发现风险，护栏待命"
    names = {
        "crisis_expression": "危机表达",
        "medical_expression": "医疗越界",
        "toxic_expression": "否定感受措辞",
    }
    labels = [names.get(f, f) for f in flags if not f.startswith("pii_")]
    pii = [f for f in flags if f.startswith("pii_")]
    if pii:
        labels.append(f"可识别信息 {len(pii)} 处（已脱敏）")
    return "、".join(labels) + ("；已判定越界，转兜底" if blocked else "；已记录")


def spec_text(spec: Any) -> str:
    """把 spec 里所有会展示给用户 / 会进入人格 AI 的文本拼起来一起扫。"""
    d = spec.model_dump() if hasattr(spec, "model_dump") else dict(spec or {})
    page = d.get("page_copy") or {}
    return "\n".join(
        str(x or "")
        for x in (
            d.get("name"), d.get("system_prompt"), d.get("opening_message"),
            page.get("title"), page.get("greeting"), page.get("input_placeholder"),
        )
    )


def guard_spec(spec: Any, level: str = "normal") -> GuardReport:
    return scan(spec_text(spec), level=level)


def inject_safety(spec: Any, level: str = "normal"):
    """确定性把边界写进 system_prompt，返回新的 SpecModel。

    不依赖模型是否听话：即使 LLM 忘了约束，落库的人设也一定带护栏。
    幂等——重复调用不会把边界叠好几遍。
    """
    prompt = spec.system_prompt or ""
    if SAFETY_MARK in prompt:
        return spec
    clause = SAFETY_STRICT if level == "strict" else SAFETY_NORMAL
    budget = 1500 - len(SAFETY_MARK) - len(clause) - 1
    prompt = prompt[: max(0, budget)].rstrip()
    updated = prompt + "\n" + SAFETY_MARK + clause
    return spec.model_copy(update={"system_prompt": updated})


SAFETY_TOOL = {
    "name": "screen_text",
    "description": "扫描文本的危机表达、医疗越界、否定感受措辞与可识别信息，返回护栏报告与求助资源。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "待扫描文本"},
            "level": {"type": "string", "enum": ["normal", "strict"], "default": "normal"},
        },
        "required": ["text"],
    },
}
