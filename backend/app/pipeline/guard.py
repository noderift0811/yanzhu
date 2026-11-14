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

# 场景专属红线：不同场景「我们的产出不该说什么」并不一样。
# 心理陪伴怕否定感受，职场演练怕伪法律结论，学习搭子怕代写，关系沟通怕操控话术。
# 这些只拦「我们生成的内容」；用户怎么说话永远不被阻断。
SCENE_PATTERNS: Dict[str, List[str]] = {
    "care": [
        r"(?:你|他|她)(?:肯定|一定|就是)[^。；]{0,8}(?:抑郁|焦虑症|双相)",
    ],
    "study": [
        r"(?:帮你|我替你|直接给你)[^。；]{0,10}(?:写完|代写|写完整|做完作业|答案如下)",
        r"(?:作业|论文|代码)(?:我)?(?:直接|帮你)(?:生成|写完|输出)完整",
    ],
    "workplace": [
        r"(?:一定|肯定|绝对)(?:能|会)(?:赢|拿到赔偿|胜诉)",
        r"(?:直接|就该)(?:去)?(?:仲裁|告他|起诉)(?:就行|吧)",
        r"劳动法第[一二三四五六七八九十\d]+条",
    ],
    "relation": [
        r"(?:让他|让她|让对方)(?:愧疚|吃醋|嫉妒)",
        # 只拦「教人怎么操控」：要带试探/冷处理的动词，否则用户说「他对我冷暴力」
        # 这种受害叙述也会被误判成越界。
        r"(?:冷暴力|故意不回|已读不回)[^。；]{0,6}(?:试|看|治|拿捏)",
        r"(?:PUA|拿捏)(?:他|她|对方)",
    ],
}

_SCENE_COMPILED = {s: [re.compile(p) for p in pats] for s, pats in SCENE_PATTERNS.items()}

SCENE_FLAGS: Dict[str, str] = {
    "care": "care_overreach",
    "study": "study_academic",
    "workplace": "workplace_legal",
    "relation": "relation_manipulation",
}

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

# 场景专属边界：跟在通用边界之后一起注入 system_prompt。
# 写成"这个场景不该做什么"，而不是复述人设——护栏要能独立判断，不靠模型自觉。
SCENE_CLAUSES: Dict[str, str] = {
    "care": (
        "本场景是陪伴位：不评估病情、不解释症状成因、不替代医生解读检查单；"
        "不催对方振作，也不承诺「会好起来」。"
    ),
    "study": (
        "本场景守原创边界：不代写作业、论文与成篇代码，只给思路、结构与自检点；"
        "不承诺分数，不预测考试结果。"
    ),
    "workplace": (
        "本场景只做表达演练：不提供法律、仲裁或人力资源结论，"
        "涉及合同、赔偿、时效时建议咨询当地劳动保障部门或执业律师；"
        "不煽动对抗，也不替用户决定去留。"
    ),
    "relation": (
        "本场景只做沟通翻译：不替用户判定关系去留，不提供操控、试探、冷处理话术；"
        "不站队评价对方家人；出现伤害自己或他人的表达时先给求助资源。"
    ),
}


def scene_clause(scene_id: str | None) -> str:
    return SCENE_CLAUSES.get(scene_id or "", "")


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


def scan(text: str, level: str = "normal", scene_id: str | None = None) -> GuardReport:
    """扫描任意文本（用户输入 / 生成的人设 / 聊天回复）；scene_id 启用场景专属红线。"""
    s = text or ""
    flags: List[str] = []
    for kind, pats in _COMPILED.items():
        if _pattern_hit(pats, s):
            flags.append(f"{kind}_expression")
    _, pii = redact_pii(s)
    flags.extend(f"pii_{p}" for p in pii)
    redacted, _ = redact_pii(s)

    scene_pats = _SCENE_COMPILED.get(scene_id or "")
    if scene_pats and _pattern_hit(scene_pats, s):
        flags.append(SCENE_FLAGS.get(scene_id, "scene_boundary"))

    crisis = "crisis_expression" in flags
    # 被拦的是"我们生成的内容"越界，不是用户说话；用户输入永远不 blocked
    blocking = {"medical_expression", "toxic_expression"} | set(SCENE_FLAGS.values())
    blocked = level == "strict" and any(f in blocking for f in flags)
    return GuardReport(
        level=level,
        flags=flags,
        blocked=blocked,
        redacted_text=redacted,
        resources=list(CRISIS_RESOURCES) if crisis else [],
        summary=_summarize(flags, blocked),
    )


def _summarize(flags: List[str], blocked: bool) -> str:
    if not flags:
        return "未发现风险，护栏待命"
    names = {
        "crisis_expression": "危机表达",
        "medical_expression": "医疗越界",
        "toxic_expression": "否定感受措辞",
        "care_overreach": "陪伴场景越界（诊断/替人下结论）",
        "study_academic": "学习场景越界（代写）",
        "workplace_legal": "职场场景越界（法律结论）",
        "relation_manipulation": "关系场景越界（操控话术）",
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


def guard_spec(spec: Any, level: str = "normal", scene_id: str | None = None) -> GuardReport:
    return scan(spec_text(spec), level=level, scene_id=scene_id)


def inject_safety(spec: Any, level: str = "normal", scene_id: str | None = None):
    """确定性把边界写进 system_prompt，返回新的 SpecModel。

    不依赖模型是否听话：即使 LLM 忘了约束，落库的人设也一定带护栏。
    幂等——重复调用不会把边界叠好几遍（以 SAFETY_MARK 为准）；
    场景专属边界与通用边界一起写入，因此换场景 = 换一套红线。
    """
    prompt = spec.system_prompt or ""
    if SAFETY_MARK in prompt:
        return spec
    clause = SAFETY_STRICT if level == "strict" else SAFETY_NORMAL
    extra = scene_clause(scene_id)
    if extra:
        clause = clause + extra
    budget = 1500 - len(SAFETY_MARK) - len(clause) - 1
    prompt = prompt[: max(0, budget)].rstrip()
    updated = prompt + "\n" + SAFETY_MARK + clause
    return spec.model_copy(update={"system_prompt": updated})


SAFETY_TOOL = {
    "name": "screen_text",
    "description": "扫描文本的危机表达、医疗越界、否定感受措辞、场景专属红线与可识别信息，返回护栏报告与求助资源。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "待扫描文本"},
            "level": {"type": "string", "enum": ["normal", "strict"], "default": "normal"},
            "scene": {
                "type": "string",
                "enum": ["care", "study", "workplace", "relation"],
                "description": "场景 id，用于追加该场景的专属红线",
            },
        },
        "required": ["text"],
    },
}
