from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Dict, List


@dataclass
class LLMConfig:
    adapter: str
    base_url: str
    api_key: str
    model: str
    extra: Dict[str, str] = field(default_factory=dict)


class BaseAdapter(ABC):
    """LLM 适配器契约：chat_json 产规格，chat_text 非流式，chat_stream 流式（M1）。"""

    name = "base"

    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg

    @abstractmethod
    async def chat_json(self, messages: List[Dict[str, str]], *, temperature: float = 0.7) -> dict:
        ...

    @abstractmethod
    async def chat_text(self, messages: List[Dict[str, str]], *, temperature: float = 0.8) -> str:
        ...

    @abstractmethod
    async def chat_stream(self, messages: List[Dict[str, str]], *, temperature: float = 0.8) -> AsyncIterator[str]:
        raise NotImplementedError
        yield  # pragma: no cover - 标记为异步生成器
