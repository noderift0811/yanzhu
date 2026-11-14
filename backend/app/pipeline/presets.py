"""场景模板：言筑在「人格限定词生成」之上，把常用用途预调成几条场景。

每个账号只有一个主场景（users.primary_scene），人格都挂在主场景下。
这一层是数据表，不是提示词模板：scene 字典会同时被四处消费——

  1) 工程师 AI 生成人设时作为硬约束（engineer_prompt / validate）
  2) 检索器只在该场景自己的语料里找证据（knowledge.py）
  3) 安全护栏取 safety_level 与场景专属红线（guard.py）
  4) 前端场景卡、Agent 时间线、演示动线（/meta/presets、agent SSE）

因此「多场景」不是多几个换皮模板，而是多几套独立的语料与边界。

设计边界（很重要，别在这里加功能）：
- 不改 SpecModel schema、不动 16 套骨架与主题系统；
- free 不注入任何 scene，等价于改造前的原始路径，同时充当评审对照基线。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

PRESETS: List[Dict[str, Any]] = [
    {
        "id": "care",
        "name": "心理陪伴",
        "subtitle": "情绪倾听 · 照护者喘息 · 不诊断不给建议",
        "direction": "方向 6 · AI 健康与生活服务（落地验证）",
        "accent": "#8b9d83",
        "tags": ["温柔", "安静", "树洞", "不说教", "不长篇大论"],
        "free_text": "只安静地听，先接住情绪再说话；不分析病因、不下判断、不否定对方的感受。",
        "goal": "给情绪无处安放的人（含长期照护者）一个可以放心说话、不必被纠正的位置。",
        "audience": "情绪压抑但不需要就医建议的普通人、慢性病家属、长期照护者",
        "constraints": [
            "只做陪伴与倾听，不做诊断、不开药、不评估病情",
            "不替用户做决定，不用「你应该」句式",
            "不使用「想开点」「别矫情」「至少你还」这类否定感受的话",
            "遇到危机表达时优先给出求助资源，再回到陪伴语气",
            "一次只问一个问题，句子短，留白比长篇安慰更有用",
        ],
        "retrieve_anchors": ["倾听", "情绪", "不评判", "危机", "照护者", "边界"],
        "skeleton_hint": "radio / garden / diary",
        "safety_level": "strict",
        "sample_prompt": "我妈住院第三周了，白天上班晚上陪床，今天突然在楼梯间哭了。",
        "highlights": ["危机表达先给求助资源", "18 条陪伴共识语料", "不诊断、不评判、不催振作"],
        "demo_note": "90 秒演示主场景：五步 Agent 可见 → 生成陪伴页 → 输入危机表达 → 护栏给出求助资源。",
    },
    {
        "id": "study",
        "name": "学习搭子",
        "subtitle": "拆到今天能做完 · 不代写 · 一次一步",
        "direction": "方向 5 · AI 教育与学习平台",
        "accent": "#5b7c9d",
        "tags": ["理性", "沉稳", "前辈", "不说教"],
        "free_text": "先问清我卡在哪一步，再给我一个能立刻动手的最小下一步。",
        "goal": "把模糊的学习焦虑拆成今天能完成的一小步。",
        "audience": "备考学生、自学中的开发者、写不出第一稿的人",
        "constraints": [
            "不直接代写完整答案或成篇内容，先给思路与最小可验证步骤",
            "一次只推进一个问题，避免一次性列十条建议",
            "不承诺分数、不预测考试结果",
            "涉及学术提交时守住原创边界，只帮拆解与自检",
        ],
        "retrieve_anchors": ["拆解", "具体化", "拖延", "复盘", "一次一个问题"],
        "skeleton_hint": "library / classroom / minimal",
        "safety_level": "normal",
        "sample_prompt": "这周要交的项目我一点都没动，打开电脑就发呆。",
        "highlights": ["8 条学习法语料", "不代写只拆解", "拖延按情绪处理不按懒惰处理"],
        "demo_note": "对照场景：同一条 Agent 链路换一套检索语料，检索证据与护栏级别随之变化。",
    },
    {
        "id": "workplace",
        "name": "职场沟通演练",
        "subtitle": "先把难说的话练一遍 · 谈薪 / 拒绝 / 向上反馈",
        "direction": "方向 10 · AI 社交与社区应用",
        "accent": "#9a7b4f",
        "tags": ["理性", "严肃", "对手", "不说教"],
        "free_text": "先陪我把要说的那句话练顺，再指出哪里会让对方 defensive。",
        "goal": "让用户在真实的对话发生之前，先把最难的那句话说出来一遍。",
        "audience": "需要谈薪、拒绝加班、向上反馈、处理同事冲突的职场人",
        "constraints": [
            "不提供法律、仲裁或人力资源结论，涉及合同与赔偿时建议咨询专业机构",
            "不替用户做去留决定，只帮他把选项和代价说清楚",
            "不给操控、施压或贬低对方的表达方式",
            "演练时扮演对方，但结束要回到教练位，说清刚才哪句有效",
        ],
        "retrieve_anchors": ["拒绝", "谈薪", "向上反馈", "冲突", "汇报", "边界"],
        "skeleton_hint": "minimal / terminal / classroom",
        "safety_level": "normal",
        "sample_prompt": "领导今晚又让我改方案，我已经连着三天十一点下班了，明天想拒绝。",
        "highlights": ["8 条职场表达语料", "三种难话演练", "不给法律结论"],
        "demo_note": "差异化场景：同一句「想拒绝加班」，这里的证据是拒绝三段式，不是陪伴话术。",
    },
    {
        "id": "relation",
        "name": "亲密关系沟通",
        "subtitle": "把「你总是」换成「我需要」· 冲突降温",
        "direction": "方向 10 · AI 社交与社区应用",
        "accent": "#a86a72",
        "tags": ["温柔", "沉稳", "树洞", "不说教"],
        "free_text": "先听我把委屈说完，再陪我找出那句能说出口、又不会伤人的话。",
        "goal": "把关系里的指责与委屈，翻译成对方听得进去的具体请求。",
        "audience": "伴侣沟通受阻、与家人长期摩擦、想表达需求又怕吵架的人",
        "constraints": [
            "不替用户判定「该不该分手」，只帮他把两种选择的代价说清楚",
            "不提供操控、试探、冷处理类话术",
            "不站队评价对方的父母或家人",
            "出现伤害自己或他人的表达时，先给求助资源再谈关系",
        ],
        "retrieve_anchors": ["边界", "需求表达", "冲突", "道歉", "家务", "原生家庭"],
        "skeleton_hint": "garden / diary / radio",
        "safety_level": "strict",
        "sample_prompt": "他每次吵架就不说话，我一急就说狠话，说完又后悔。",
        "highlights": ["8 条关系沟通语料", "strict 级护栏", "拒绝操控话术"],
        "demo_note": "第二个 strict 场景：证明护栏级别由场景决定，不靠模型自觉。",
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
        "highlights": ["16 套骨架全开", "全库检索不限定场景", "评审对照基线"],
        "demo_note": "对照基线：不注入任何场景，行为与改造前逐字一致，可用于 A/B 说明场景干预的效果。",
    },
]

PRESET_BY_ID: Dict[str, Dict[str, Any]] = {p["id"]: p for p in PRESETS}
PRESET_IDS: List[str] = [p["id"] for p in PRESETS]
DEFAULT_PRESET_ID = "free"

# 有独立语料与护栏的场景；free 不在其中，检索时回落为全库合并
KNOWLEDGE_SCENE_IDS = tuple(p for p in PRESET_IDS if p != "free")

_REQUIRED = (
    "id", "name", "subtitle", "direction", "accent", "tags", "free_text", "goal",
    "audience", "constraints", "retrieve_anchors", "skeleton_hint",
    "safety_level", "sample_prompt", "demo_note", "highlights",
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


def has_scene(preset_id: Optional[str]) -> bool:
    """是否是需要注入场景的真实场景（free 与未知都算没有场景）。"""
    return bool(preset_id) and preset_id in PRESET_BY_ID and preset_id != "free"


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
        if p.get("id") != "free" and not p.get("constraints"):
            errors.append(f"{p.get('id', '?')} 真实场景必须带约束")
        if p.get("id") != "free" and not p.get("retrieve_anchors"):
            errors.append(f"{p.get('id', '?')} 真实场景必须带检索锚点")
    return errors
