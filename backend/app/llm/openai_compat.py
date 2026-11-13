from __future__ import annotations

import json
from typing import AsyncIterator, Dict, List

import httpx

from .base import BaseAdapter


def _parse_json_content(content: str) -> dict:
    """容错解析：剥离 ```json 围栏。"""
    text = (content or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text)


class OpenAICompatAdapter(BaseAdapter):
    """OpenAI 兼容协议适配器：zeus 中继 / DeepSeek / 豆包 Ark 均适用。"""

    name = "openai_compat"

    def _url(self) -> str:
        return self.cfg.base_url.rstrip("/") + "/chat/completions"

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.cfg.api_key}", "Content-Type": "application/json"}

    def _payload(self, messages: List[Dict[str, str]], temperature: float, stream: bool = False) -> dict:
        return {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }

    async def chat_json(self, messages: List[Dict[str, str]], *, temperature: float = 0.7) -> dict:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(self._url(), headers=self._headers(), json=self._payload(messages, temperature))
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        return _parse_json_content(content)

    async def chat_text(self, messages: List[Dict[str, str]], *, temperature: float = 0.8) -> str:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(self._url(), headers=self._headers(), json=self._payload(messages, temperature))
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"] or ""

    async def chat_stream(self, messages: List[Dict[str, str]], *, temperature: float = 0.8) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=180) as client:
            async with client.stream(
                "POST", self._url(), headers=self._headers(), json=self._payload(messages, temperature, stream=True)
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                    if delta:
                        yield delta


class DeepSeekAdapter(OpenAICompatAdapter):
    name = "deepseek"


class DoubaoAdapter(OpenAICompatAdapter):
    """豆包 Ark（OpenAI 兼容端点）。"""

    name = "doubao"
