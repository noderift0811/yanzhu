"""标签规则：互斥轴 + 分组配额 + 反差张力。

后端这份是权威表——前端拦不住的三条路（重新生成弹窗、老数据、直接调 API）
都要在这里兜住。前端 `tagGroups.js` 有同名的一份用于同步渲染，两边的
分组与轴由 `backend/tag_test.py` 做集合比对锁死，改一边不改另一边测试会红。
"""
from __future__ import annotations

from typing import Dict, List, Tuple

TAG_GROUPS: Dict[str, Tuple[str, List[str]]] = {
    "temperament": (
        "性格基调",
        ["内向", "外向", "高冷", "温柔", "毒舌", "粘人", "理性", "感性", "傲娇", "慢热"],
    ),
    "tone": ("语气", ["活泼", "沉稳", "腼腆", "冷淡", "撒娇", "严肃", "俏皮", "安静"]),
    "relation": ("关系定位", ["笔友", "前辈", "青梅竹马", "管家", "同桌", "树洞", "对手"]),
    "taboo": ("禁区", ["不说教", "不玩梗", "不主动提问", "不长篇大论", "不客气"]),
}

# 同一轴最多选一个：轴内成员是同一维度的不同位置，不可能同时成立
AXES: Dict[str, List[str]] = {
    "social": ["内向", "外向"],
    "judge": ["理性", "感性"],
    "energy": ["活泼", "安静", "沉稳", "冷淡"],
    "measure": ["严肃", "俏皮", "撒娇"],
}

# 反差张力：不禁用，只在前端提示（嘴硬心软是加分项，不是缺陷）
TENSIONS: List[Tuple[str, str]] = [
    ("毒舌", "温柔"),
    ("高冷", "粘人"),
    ("高冷", "温柔"),
    ("慢热", "粘人"),
    ("腼腆", "撒娇"),
    ("傲娇", "粘人"),
    ("内向", "活泼"),
]

# 组配额上限（下限不强制，交给"至少选一个标签"的整体校验）
# 禁区不进配额：那几条是叠加的约束，彼此不冲突，多选只会更准确
GROUP_QUOTA: Dict[str, int] = {"temperament": 3, "tone": 2, "relation": 1}
TOTAL_MAX = 8


def group_of(tag: str):
    for key, (_label, tags) in TAG_GROUPS.items():
        if tag in tags:
            return key
    return None


def axes_of(tag: str) -> List[str]:
    return [key for key, members in AXES.items() if tag in members]


def sanitize_tags(tags: List[str]) -> Tuple[List[str], List[Dict[str, str]]]:
    """确定性校正：同轴保留先出现的，组配额与总数超出的丢弃靠后的。

    返回 (保留的标签, 被丢弃的标签及原因)。丢弃原因会随 brief 回传给前端，
    不做静默删改——用户选了六个只剩三个，必须知道少的是哪三个、为什么。
    """
    kept: List[str] = []
    dropped: List[Dict[str, str]] = []
    used_axes: set = set()

    for tag in tags:
        if tag in kept:
            continue
        # 互斥优先判断：先说清"和谁冲突"，比只说"满了"有用
        hit_axis = next((a for a in axes_of(tag) if a in used_axes), None)
        if hit_axis:
            winner = next(m for m in AXES[hit_axis] if m in kept)
            dropped.append({"tag": tag, "reason": f"与「{winner}」互斥"})
            continue

        key = group_of(tag)
        if key and key in GROUP_QUOTA:
            used = sum(1 for k in kept if group_of(k) == key)
            if used >= GROUP_QUOTA[key]:
                label = TAG_GROUPS[key][0]
                dropped.append({"tag": tag, "reason": f"「{label}」最多 {GROUP_QUOTA[key]} 个"})
                continue

        if len(kept) >= TOTAL_MAX:
            dropped.append({"tag": tag, "reason": f"最多选 {TOTAL_MAX} 个标签"})
            continue

        kept.append(tag)
        used_axes.update(axes_of(tag))

    return kept, dropped
