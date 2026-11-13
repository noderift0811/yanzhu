from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .tag_rules import TOTAL_MAX, sanitize_tags

CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
NAME_MAX = 20
# 防御性上限：超过这个数量说明调用方有问题，先砍再交给 sanitize_tags 精修
RAW_TAG_CAP = 24


def normalize_brief(
    tags: List[str], free_text: str, name: Optional[str] = None
) -> Dict[str, Any]:
    """S1 输入净化：去控制字符、去重、截断、消解互斥，产出规整 brief。

    name 非空表示用户自己指定了角色名——工程师 AI 必须原样使用，
    不再自由起名（这是硬约束，落库时还会再强制覆盖一次做兜底）。

    标签互斥在这里兜底：前端已经置灰拦截，但重新生成弹窗、历史数据、
    直接调 API 三条路都绕得过去。被丢弃的标签写进 brief["dropped_tags"]，
    随详情接口回传，不做静默删改。
    """
    clean_tags: List[str] = []
    for t in tags:
        t = CONTROL_RE.sub("", str(t)).strip()
        if t and t not in clean_tags and len(t) <= 12:
            clean_tags.append(t)
        if len(clean_tags) >= RAW_TAG_CAP:
            break

    kept, dropped = sanitize_tags(clean_tags)
    text = CONTROL_RE.sub("", str(free_text or "")).strip()[:200]
    brief: Dict[str, Any] = {"tags": kept, "free_text": text, "lang": "zh"}
    if dropped:
        brief["dropped_tags"] = dropped[:TOTAL_MAX]

    clean_name = CONTROL_RE.sub("", str(name or "")).strip()[:NAME_MAX]
    if clean_name:
        brief["name"] = clean_name
    return brief
