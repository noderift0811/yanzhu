from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from ..pipeline.engineer_prompt import SKELETONS
from ..pipeline.knowledge import knowledge_stats, retrieve
from ..pipeline.presets import DEFAULT_PRESET_ID, list_presets
from ..pipeline.skeleton_presets import SKELETON_PRESETS

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/skeletons")
def skeletons() -> Dict[str, Any]:
    # 目录里额外带上每套骨架的默认主题（五色 + 字体 + 装饰）与输入框文案，
    # 供前端「换骨架」预览色带与「恢复这套骨架的默认配色」使用。
    items: List[Dict[str, Any]] = []
    for item in SKELETONS:
        preset = SKELETON_PRESETS.get(item["id"], {})
        items.append({**item, "theme": preset.get("theme"), "placeholder": preset.get("placeholder")})
    return {"items": items}


@router.get("/presets")
def presets() -> Dict[str, Any]:
    """场景预设目录：前端卡片、Agent 检索语料与护栏级别的唯一来源。"""
    return {"default": DEFAULT_PRESET_ID, "items": list_presets()}


@router.get("/knowledge")
def knowledge(
    q: Optional[str] = Query(default=None, description="给一个查询即可现场验证检索结果"),
    top_k: int = Query(default=3, ge=1, le=8),
    preset_id: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """本地知识库的可查证入口：评委可直接传 q 看 BM25-lite 命中的证据。"""
    out: Dict[str, Any] = {"stats": knowledge_stats()}
    if q:
        out["query"] = q
        out["hits"] = retrieve(q, top_k=top_k, preset_id=preset_id)
    return out
