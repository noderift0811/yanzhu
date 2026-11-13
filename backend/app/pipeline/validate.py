from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from ..schemas import SpecModel
from .engineer_prompt import build_engineer_messages


def parse_spec(raw: Any) -> SpecModel:
    """容错解析：兼容 ```json 围栏与前后废话。"""
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        raw = json.loads(text)
    return SpecModel.model_validate(raw)


async def generate_spec(adapter, brief: Dict[str, Any]) -> Tuple[SpecModel, bool]:
    """S2/S3：工程师 AI 生成 spec。校验失败带错重试 1 次，再失败走确定性兜底。

    返回 (spec, needs_review)。
    """
    from .assemble import fallback_spec

    messages: List[Dict[str, str]] = build_engineer_messages(brief)
    last_err = ""
    for attempt in (0, 1):
        try:
            msgs = messages
            if attempt == 1:
                msgs = messages + [
                    {"role": "user", "content": f"上次输出未通过校验：{last_err}。请严格按 schema 重新输出 JSON。"}
                ]
            raw = await adapter.chat_json(msgs)
            return parse_spec(raw), False
        except Exception as e:  # noqa: BLE001 - 兜底需要兜住一切
            last_err = f"{type(e).__name__}: {e}"
    return fallback_spec(brief), True
