from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter

from ..pipeline.engineer_prompt import SKELETONS
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
