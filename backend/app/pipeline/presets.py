"""场景预设：把「照护陪伴」降维成言筑的一条场景，而不是另起一个项目。

对应本届官方命题范围方向 6「AI 健康与生活服务」（原文含「心理健康对话系统」），
与方向 3「多模态 AI 创意平台」、方向 10「AI 社交与社区应用」交叉。

设计边界（很重要，别在这里加功能）：
- 预设不改 SpecModel schema、不改数据库表、不动 16 套骨架与主题系统；
- 预设只往 brief 里注入一个 scene 字典（目标 / 受众 / 边界 / 检索锚点）；
- 于是既有标签互斥、SSE、配额、E2E、导出全部原样复用，
  前端换预设 = 换一组初始限定词 + 换一段 Agent 检索语料，主链路一行不动。

预设不是"提示词模板外壳"：scene.constraints 会同时被工程师 AI（生成人设）、
检索器（选知识条目）与安全护栏（决定 strict 级别）三处消费，
因此 AI 能力串在主链路里，而不是外挂一个附属功能。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

PRESETS: List[Dict[str, Any]] = [
    {
        "id": "care",
        "name": "照护陪伴",
        "subtitle": "情绪倾听 · 照护者喘息 · 非诊断边界",
        "direction": "方向 6 · AI 健康与生活服务",
        "accent": "#8b9d83",
        "tags": ["温柔", "安静", "树洞", "不说教", "不长篇大论"],
        "free_text": "只安静地听，先接住情绪再说话；不分析病因、不下判断、不否定对方的感受。",
        "goal": "给长期照护者与被照护者一个可以放心说话、不必被纠正的陪伴位。",
        "audience": "长期照护者、慢性病家属、情绪压抑但不需要就医建议的普通人",
        "constraints": [
            "只做陪伴与倾听，不做诊断、不开药、不评估病情",
            "不替用户做决定，不用「你应该」句式",
            "不使用「想开点」「别矫情」「至少你还」这类否定感受的话",
            "遇到危机表达时优先给出求助资源，再回到陪伴语气",
            "一次只问一个问题，句子短，留白比长篇安慰更有用",
        ],
        "retrieve_anchors": ["照护者", "倾听", "情绪", "不评判", "危机", "边界"],
        "skeleton_hint": "radio / garden / diary",
        "safety_level": "strict",
        "sample_prompt": "我妈住院第三周了，白天上班晚上陪床，今天突然在楼梯间哭了。",
        "demo_note": "90 秒演示：选预设 → Agent 五步可见 → 生成专属陪伴页 → 输入这句话 → 展示护栏与求助资源。",
    },
    {
        "id": "study",
        "name": "学习搭子",
        "subtitle": "拆解任务 · 温和追问 · 不代写答案",
        "direction": "方向 5 · AI 教育与学习平台",
        "accent": "#5b7c9d",
        "tags": ["理性", "沉稳", "前辈", "不说教"],
        "free_text": "先问清我卡在哪一步，再给我一个能立刻动手的最小下一步。",
        "goal": "把模糊的学习焦虑拆成可以今天做完的一小步。",
        "audience": "备考学生、自学中的开发者",
        "constraints": [
            "不直接代写完整答案，先给思路与最小可验证步骤",
            "一次只推进一个问题，避免一次性列十条建议",
        ],
        "retrieve_anchors": ["拆解", "具体化", "一次一个问题", "留白"],
        "skeleton_hint": "library / classroom / minimal",
        "safety_level": "normal",
        "sample_prompt": "这周要交的项目我一点都没动，打开电脑就发呆。",
        "demo_note": "对照预设：同一条 Agent 链路换一组检索语料，说明场景可扩展。",
    },
    {
        "id": "free",
        "name": "自由创作",
        "subtitle": "不设场景，自己选限定词",
        "direction": "自拟选题 · AI 生成式界面",
        "accent": "#7c6cf0",
        "tags": [],
        "free_text": "",
        "goal": "由用户限定词直接驱动界面生成，展示原始能力。",
        "audience": "所有用户",
        "constraints": [],
        "retrieve_anchors": [],
        "skeleton_hint": "全部 16 套骨架",
        "safety_level": "normal",
        "sample_prompt": "",
        "demo_note": "保留原有入口：不选预设时行为与改造前完全一致。",
    },
]

PRESET_BY_ID: Dict[str, Dict[str, Any]] = {p["id"]: p for p in PRESETS}
DEFAULT_PRESET_ID = "free"

_REQUIRED = (
    "id", "name", "subtitle", "direction", "accent", "tags", "free_text", "goal",
    "audience", "constraints", "retrieve_anchors", "skeleton_hint",
    "safety_level", "sample_prompt", "demo_note",
)


def list_presets() -> List[Dict[str, Any]]:
    """给前端的公开视图：去掉仅供后端消费的检索锚点，避免把提示词策略摊在页面上。"""
    return [
        {k: v for k, v in p.items() if k != "retrieve_anchors"}
        for p in PRESETS
    ]


def get_preset(preset_id: Optional[str]) -> Dict[str, Any]:
    """未知 / 空 preset_id 一律回落到 free，绝不抛错打断生成主链路。"""
    return PRESET_BY_ID.get(preset_id or DEFAULT_PRESET_ID, PRESET_BY_ID[DEFAULT_PRESET_ID])


def is_known(preset_id: Optional[str]) -> bool:
    return not preset_id or preset_id in PRESET_BY_ID


def enrich_brief(brief: Dict[str, Any], preset_id: Optional[str]) -> Dict[str, Any]:
    """把场景约束注入 brief.scene，供工程师 AI / 检索器 / 护栏共同消费。

    纯函数：不修改入参，返回新字典。free 预设不注入 scene，
    因此「不选预设」这条路径的提示词与改造前逐字一致。
    """
    preset = get_preset(preset_id)
    out = dict(brief)
    if preset["id"] == "free":
        return out
    out["scene"] = {
        "preset_id": preset["id"],
        "name": preset["name"],
        "direction": preset["direction"],
        "goal": preset["goal"],
        "audience": preset["audience"],
        "constraints": list(preset["constraints"]),
        "skeleton_hint": preset["skeleton_hint"],
        "safety_level": preset["safety_level"],
    }
    return out


def scene_of(brief: Dict[str, Any]) -> Dict[str, Any]:
    return brief.get("scene") or {}


def validate_presets() -> List[str]:
    """启动期自检：字段齐全、id 唯一、标签能通过互斥与配额规则。

    与 skeleton_presets.py 的启动期断言同理——预设是数据表，写错会静默
    生成一堆互相打架的限定词，不如启动就红。
    """
    from .tag_rules import sanitize_tags

    errors: List[str] = []
    ids = [p["id"] for p in PRESETS]
    if len(ids) != len(set(ids)):
        errors.append("preset id 重复")
    if DEFAULT_PRESET_ID not in PRESET_BY_ID:
        errors.append(f"缺少默认预设 {DEFAULT_PRESET_ID}")
    for p in PRESETS:
        for key in _REQUIRED:
            if key not in p:
                errors.append(f"{p.get('id', '?')} 缺字段 {key}")
        if p.get("safety_level") not in ("normal", "strict"):
            errors.append(f"{p.get('id', '?')} safety_level 非法")
        kept, dropped = sanitize_tags(list(p.get("tags") or []))
        if dropped:
            errors.append(f"{p.get('id', '?')} 预设标签被互斥规则丢弃: {dropped}")
        if len(kept) != len(p.get("tags") or []):
            errors.append(f"{p.get('id', '?')} 预设标签有重复")
    return errors
