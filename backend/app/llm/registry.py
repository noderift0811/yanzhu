from __future__ import annotations

from typing import Dict, Type

from .base import BaseAdapter, LLMConfig
from .mock import MockAdapter
from .openai_compat import DeepSeekAdapter, DoubaoAdapter, OpenAICompatAdapter
from ..config import get_settings

REGISTRY: Dict[str, Type[BaseAdapter]] = {
    "openai_compat": OpenAICompatAdapter,
    "deepseek": DeepSeekAdapter,
    "doubao": DoubaoAdapter,
}


def get_adapter(purpose: str) -> BaseAdapter:
    """purpose: engineer | persona | decorate。未配置密钥 → MockAdapter（框架期全流程可跑）。

    decorate 复用 persona 的快模型配置（flash，秒级返回）；装修只产主题 JSON，
    不重写人设，用轻模型即可——真实适配器不看 purpose，mock 用 purpose 分流。
    """
    s = get_settings()
    if purpose == "engineer":
        cfg = LLMConfig(s.engineer_llm_adapter, s.engineer_llm_base_url, s.engineer_llm_api_key, s.engineer_llm_model)
    elif purpose in ("persona", "decorate"):
        cfg = LLMConfig(s.persona_llm_adapter, s.persona_llm_base_url, s.persona_llm_api_key, s.persona_llm_model)
    else:
        raise ValueError(f"未知 purpose: {purpose}")
    if not cfg.api_key:
        return MockAdapter(purpose, cfg)
    cls = REGISTRY.get(cfg.adapter)
    if cls is None:
        raise ValueError(f"未注册的 adapter: {cfg.adapter}，可选: {list(REGISTRY)}")
    return cls(cfg)
