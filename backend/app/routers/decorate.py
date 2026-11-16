"""AI 装修师接口：自然语言 → 一套可预览的主题参数。

不落库、不耗生成配额——前端拿到 theme 先实时预览，用户点「采用」才走
PATCH /personas/{id} 持久化。这样 AI 多改几次也不产生副作用。
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from ..db import get_db
from ..deps import get_current_user
from ..llm.registry import get_adapter
from ..pipeline.decorate import generate_decoration
from ..pipeline.engineer_prompt import SKELETONS
from ..quota import log_llm_call
from ..schemas import DecorateIn, DecorateOut

router = APIRouter(prefix="/decorate", tags=["decorate"], dependencies=[Depends(get_current_user)])

_SKELETON_NAMES = {s["id"]: s["name"] for s in SKELETONS}


@router.post("", response_model=DecorateOut)
async def decorate(body: DecorateIn, user=Depends(get_current_user), conn=Depends(get_db)) -> DecorateOut:
    adapter = get_adapter("decorate")
    started = time.time()
    try:
        result = await generate_decoration(
            adapter, body,
            model_label=getattr(adapter.cfg, "model", "mock"),
            is_mock=getattr(adapter, "name", "") == "mock",
            skeleton_name=_SKELETON_NAMES.get(body.skeleton_id or "", ""),
        )
        log_llm_call(
            conn, user["id"], "decorate", getattr(adapter, "name", "mock"),
            result.model, int((time.time() - started) * 1000), "ok",
        )
        return result
    except Exception as e:  # noqa: BLE001 - 装修是增值动作，失败不该冒泡成 500
        log_llm_call(
            conn, user["id"], "decorate", getattr(adapter, "name", "mock"),
            "error", int((time.time() - started) * 1000), "error", str(e)[:200],
        )
        return DecorateOut(theme=body.theme, note="AI 暂时开小差，配色保持不变", model="error", mock=True)
