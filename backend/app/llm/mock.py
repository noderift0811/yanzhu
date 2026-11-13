from __future__ import annotations

import asyncio
import json
import re
from typing import Any, AsyncIterator, Dict, List

from .base import BaseAdapter, LLMConfig

# 关键词 → 骨架（有序规则，先命中先返回）
_SKELETON_RULES = [
    (("内向", "害羞", "腼腆", "文艺", "安静", "日记"), "diary"),
    (("温柔", "陪伴", "治愈", "树洞", "倾听"), "radio"),
    (("毒舌", "极客", "理性", "高冷", "冷淡", "傲娇"), "terminal"),
]

_PALETTES = {
    "diary": {"primary": "#e8a0bf", "bg": "#fdf6f4", "surface": "#ffffff", "text": "#5c4a4a", "accent": "#c98bb0", "font_style": "rounded", "decoration": "petal"},
    "radio": {"primary": "#e0913f", "bg": "#2b2118", "surface": "#3a2c20", "text": "#f3e6d8", "accent": "#f0b95c", "font_style": "rounded", "decoration": "stars"},
    "terminal": {"primary": "#3fd68c", "bg": "#101418", "surface": "#171d23", "text": "#d6e2dc", "accent": "#5eead4", "font_style": "mono", "decoration": "grid"},
    "minimal": {"primary": "#4f46e5", "bg": "#f6f7fb", "surface": "#ffffff", "text": "#1f2328", "accent": "#7c6cf0", "font_style": "system", "decoration": "none"},
}

_NAMES = {
    "diary": ["苏桃", "林蕨", "夏茧", "知语"],
    "radio": ["晚风", "阿盏", "南栀", "枕月"],
    "terminal": ["老K", "零一", "阿尔法", "比特"],
    "minimal": ["青", "屿", "白", "序"],
}

_OPENINGS = {
    "diary": "…你好…我是{name}…请、请多关照……",
    "radio": "晚上好，这里是{name}的电波时间，今天想听点什么？",
    "terminal": "{name} online. 输入 help 查看可用指令。开玩笑的，直接聊。",
    "minimal": "你好，我是{name}。",
}

_PLACEHOLDERS = {
    "diary": "想跟我说什么呢…",
    "radio": "点一首歌，或者说说话…",
    "terminal": "$ 输入消息…",
    "minimal": "说点什么吧…",
}


def _stable(text: str) -> int:
    import zlib

    return zlib.crc32(text.encode("utf-8"))


def _pick_skeleton(tags: List[str], free_text: str) -> str:
    text = " ".join(tags) + " " + (free_text or "")
    for keywords, sid in _SKELETON_RULES:
        if any(k in text for k in keywords):
            return sid
    return "minimal"


class MockAdapter(BaseAdapter):
    """框架期确定性假数据：未配置密钥时自动启用，保证全流程可跑通、可复现。"""

    name = "mock"

    def __init__(self, purpose: str, cfg: LLMConfig):
        super().__init__(cfg)
        self.purpose = purpose

    # ---- 工程师 AI ----

    @staticmethod
    def _extract_brief(messages: List[Dict[str, str]]) -> Dict[str, Any]:
        for msg in reversed(messages):
            if msg.get("role") != "user":
                continue
            try:
                data = json.loads(msg.get("content") or "")
                if isinstance(data, dict) and "brief" in data:
                    return data["brief"]
            except (json.JSONDecodeError, TypeError):
                continue
        return {}

    def _engineer_spec(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        tags = brief.get("tags") or []
        free_text = brief.get("free_text") or ""
        skeleton = _pick_skeleton(tags, free_text)
        palette = dict(_PALETTES[skeleton])
        seed = _stable(" ".join(tags) + free_text)
        name = _NAMES[skeleton][seed % len(_NAMES[skeleton])]
        style = "、".join(tags[:3]) or "温和"
        extra = f" 补充设定：{free_text}" if free_text else ""
        system_prompt = (
            f"你是{name}，性格关键词：{style}。{extra}"
            "说话保持人设，不承认自己是 AI，不跳出角色。"
            "示例：『嗯，我在听。』『……今天也有点累了呢。』"
        )
        return {
            "name": name,
            "system_prompt": system_prompt,
            "skeleton_id": skeleton,
            "theme": palette,
            "page_copy": {
                "title": f"{name}的小天地",
                "greeting": _OPENINGS[skeleton].format(name=name),
                "input_placeholder": _PLACEHOLDERS[skeleton],
            },
            "opening_message": _OPENINGS[skeleton].format(name=name),
        }

    # ---- 人格 AI ----

    @staticmethod
    def _persona_name(messages: List[Dict[str, str]]) -> str:
        system = next((m.get("content", "") for m in messages if m.get("role") == "system"), "")
        m = re.search(r"你是([^\s，。,.，]{1,8})", system)
        return m.group(1) if m else "人格"

    def _persona_reply(self, messages: List[Dict[str, str]]) -> str:
        name = self._persona_name(messages)
        last_user = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
        snippet = last_user.strip().replace("\n", " ")[:24] or "……"
        skeleton = _pick_skeleton([], last_user)
        suffix = {
            "diary": "……我都记在本子上了。",
            "radio": "这段点播我收到了，循环播放中。",
            "terminal": "指令已解析。",
            "minimal": "我明白了。",
        }[skeleton]
        return f"（Mock·{name}）关于「{snippet}」……{suffix}"

    # ---- 契约实现 ----

    async def chat_json(self, messages: List[Dict[str, str]], *, temperature: float = 0.7) -> dict:
        if self.purpose == "engineer":
            return self._engineer_spec(self._extract_brief(messages))
        raise ValueError("MockAdapter.chat_json 仅支持 engineer purpose")

    async def chat_text(self, messages: List[Dict[str, str]], *, temperature: float = 0.8) -> str:
        return self._persona_reply(messages)

    async def chat_stream(self, messages: List[Dict[str, str]], *, temperature: float = 0.8) -> AsyncIterator[str]:
        text = self._persona_reply(messages)
        for i in range(0, len(text), 4):
            yield text[i : i + 4]
            await asyncio.sleep(0.02)
