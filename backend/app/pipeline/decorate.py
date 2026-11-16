from __future__ import annotations

"""AI 装修师：把用户的自然语言审美需求翻译成一套可预览的主题参数。

与工程师 AI 的区别：
- 工程师 AI 产整份 spec（system_prompt / 骨架 / 文案），慢、耗生成配额；
- 装修 AI 只产主题（五色 + 字体 + 装饰），快、不耗配额、不碰人设与聊天记录。

安全边界：
- 输出严格走 ThemeModel 校验（色值 / 字体 / 装饰枚举），非法值触发重试；
- 对比度护栏：AI 给的正文色若与底色对比度不足，自动推到可读，避免"改完看不清"；
- 两层兜底：校验失败重试 1 次，再失败用确定性的关键词规则，保证接口永不 500。
"""

import colorsys
import json
import re
from typing import Any, Dict, List, Tuple

from ..schemas import DecorateIn, DecorateOut, ThemeModel
from ..llm.base import BaseAdapter
from .engineer_prompt import SKELETON_IDS
from .skeleton_presets import SKELETON_PRESETS

SYSTEM_PROMPT = """你是「言筑」的界面装修师。用户会用自然语言描述想要的页面视觉风格，你把它翻译成一套配色和排版参数。

只输出一个 JSON 对象，不要任何解释文字、不要 markdown 代码块，格式严格如下：
{
  "theme": {
    "primary": "#RRGGBB",
    "bg": "#RRGGBB",
    "surface": "#RRGGBB",
    "text": "#RRGGBB",
    "accent": "#RRGGBB",
    "font_style": "system 或 rounded 或 serif 或 mono",
    "decoration": "none 或 paper 或 petal 或 stars 或 grid"
  },
  "note": "一句话中文说明你做了什么，20字以内"
}

字段含义：
- primary 主色：按钮、强调、光标
- bg 页面底色；surface 卡片与气泡底色（必须与 bg 有明暗层次）
- text 正文色：必须与 bg 和 surface 都有足够对比度，浅底配深字、深底配浅字
- accent 点缀色：分隔线、标签、装饰，与 primary 区分开
- font_style：system 清朗 / rounded 圆润 / serif 书卷衬线 / mono 机械等宽
- decoration：none 无 / paper 纸纹 / petal 花瓣 / stars 星点 / grid 网格

硬性要求：
1. 五个颜色都必须是 #RRGGBB 十六进制，不要简写。
2. bg 与 surface 要同明暗方向但明度不同（差 8%~18%），不能相同。
3. text 必须与 bg 反向：浅底(bg 亮度高)用深 text，深底用浅 text，保证清晰可读。
4. 只能从给定的枚举里选 font_style 和 decoration，不要发明新值。
5. 尊重用户的描述：说"暗色/深夜/酷"就做深底，说"暖/米黄/纸感"就往暖色调走，说"清爽/冷/蓝"就往冷色调走。
6. note 用中文，简短说明改动气质，例如"换成深夜暖橙的电台质感"。

你会拿到当前主题和骨架信息。在它基础上调整，而不是每次都推倒重来。如果骨架底色是固定的深色，请把整套配色做成深色系。"""


def _rgb(hex_color: str) -> Tuple[float, float, float]:
    h = (hex_color or "").lstrip("#")
    if len(h) != 6:
        return (1.0, 1.0, 1.0)
    try:
        return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return (1.0, 1.0, 1.0)


def _hex(r: float, g: float, b: float) -> str:
    p = lambda v: max(0, min(255, round(v * 255)))
    return f"#{p(r):02x}{p(g):02x}{p(b):02x}"


def _luminance(hex_color: str) -> float:
    r, g, b = _rgb(hex_color)
    def ch(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def _contrast(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _push_lightness(hex_color: str, bg: str, target: float = 4.5) -> str:
    """保色相与饱和，只调明度，把前景色推到与底色对比度达标。"""
    r, g, b = _rgb(hex_color)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    step = -0.02 if _luminance(bg) > 0.3 else 0.02
    cur = l
    for _ in range(60):
        cur += step
        if cur <= 0.02 or cur >= 0.98:
            break
        cand = _hex(*colorsys.hls_to_rgb(h, cur, s))
        if _contrast(cand, bg) >= target:
            return cand
    return hex_color


def guard_contrast(theme: ThemeModel) -> ThemeModel:
    """对比度护栏：正文 text 对 bg / surface 至少 4.5:1，primary / accent 对 bg 至少 3:1。"""
    data = theme.model_dump()
    bg = data["bg"]
    data["text"] = _push_lightness(data["text"], bg, 4.5)
    data["text"] = _push_lightness(data["text"], data["surface"], 4.5)
    data["primary"] = _push_lightness(data["primary"], bg, 3.0)
    data["accent"] = _push_lightness(data["accent"], bg, 3.0)
    return ThemeModel.model_validate(data)


def build_messages(payload: DecorateIn, skeleton_name: str = "") -> List[Dict[str, str]]:
    current = payload.theme.model_dump()
    skeleton_hint = ""
    if payload.skeleton_id:
        preset = SKELETON_PRESETS.get(payload.skeleton_id, {})
        preset_theme = preset.get("theme") or {}
        # 固定深色骨架（见前端 SKELETON_TONE）：提示 AI 别做浅底
        DARK_SKELETONS = {"oracle", "receipt", "starship", "neon", "classroom"}
        if payload.skeleton_id in DARK_SKELETONS:
            skeleton_hint = f"\n当前骨架「{skeleton_name or payload.skeleton_id}」是固定深色底，请务必做深色系配色。"
        elif preset_theme:
            skeleton_hint = f"\n当前骨架「{skeleton_name or payload.skeleton_id}」的默认气质是 {preset_theme.get('font_style')} 字体、{preset_theme.get('decoration')} 装饰，可作参考。"
    user = (
        f"当前主题：{json.dumps(current, ensure_ascii=False)}\n"
        f"{skeleton_hint}\n"
        f"用户想要的风格：{payload.request}\n\n"
        "请输出新的 theme 与一句 note，只在用户要求改变那些维度上做明显调整，其余维度保持接近当前主题。"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def _parse_decoration(raw: Any) -> Tuple[ThemeModel, str]:
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        raw = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError("装修结果不是对象")
    theme = ThemeModel.model_validate(raw.get("theme"))
    note = str(raw.get("note") or "已调整配色").strip()[:20]
    return theme, note


# ---- 确定性兜底 ----

_FALLBACK = [
    (("暗", "深夜", "夜", "酷", "黑", "咖啡", "酒", "神秘", "赛博", "霓虹"),
     {"primary": "#d9a441", "bg": "#141821", "surface": "#1e2532", "text": "#f0e9dc", "accent": "#e0744f",
      "font_style": "serif", "decoration": "stars"}, "换成深夜暖金的沉静质感"),
    (("暖", "温柔", "米", "纸", "书卷", "复古", "怀旧", "奶茶", "木", "秋"),
     {"primary": "#8a6a3a", "bg": "#f6efe2", "surface": "#fffdf6", "text": "#3a2f22", "accent": "#ab7f48",
      "font_style": "serif", "decoration": "paper"}, "换成暖纸书卷的质感"),
    (("清爽", "冷", "蓝", "海", "薄荷", "干净", "极简", "科技", "冰"),
     {"primary": "#0e7490", "bg": "#eefafb", "surface": "#ffffff", "text": "#12343b", "accent": "#3a9bac",
      "font_style": "system", "decoration": "none"}, "换成清爽冷调的极简感"),
    (("可爱", "粉", "甜", "花瓣", "少女", "圆润", "软"),
     {"primary": "#d4738f", "bg": "#fdf3f5", "surface": "#fffafb", "text": "#4a2f38", "accent": "#e0a0b2",
      "font_style": "rounded", "decoration": "petal"}, "换成柔和粉调的圆润感"),
]


def fallback_decoration(payload: DecorateIn) -> Tuple[ThemeModel, str]:
    text = payload.request
    for keywords, theme_data, note in _FALLBACK:
        if any(k in text for k in keywords):
            return ThemeModel.model_validate(theme_data), note
    # 无关键词命中：在现有主题上把主色往暖色轻推一点，给一个"我动了"的真实反馈
    data = payload.theme.model_dump()
    r, g, b = _rgb(data["primary"])
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    r2, g2, b2 = colorsys.hls_to_rgb((h + 0.04) % 1.0, l, min(1.0, s + 0.06))
    data["primary"] = _hex(r2, g2, b2)
    return ThemeModel.model_validate(data), "在原配色上做了一点微调"


async def generate_decoration(
    adapter: BaseAdapter,
    payload: DecorateIn,
    *,
    model_label: str,
    is_mock: bool = False,
    skeleton_name: str = "",
) -> DecorateOut:
    """调 AI 装修；校验失败重试 1 次，仍失败走确定性兜底。永不抛异常给路由层。"""
    messages = build_messages(payload, skeleton_name)
    last_err = ""
    for attempt in (0, 1):
        try:
            msgs = messages
            if attempt == 1:
                msgs = messages + [
                    {"role": "user", "content": f"上次输出未通过校验：{last_err}。请严格按 schema 重新输出 JSON，不要解释文字。"}
                ]
            raw = await adapter.chat_json(msgs, temperature=0.8)
            theme, note = _parse_decoration(raw)
            return DecorateOut(theme=guard_contrast(theme), note=note, model=model_label, mock=is_mock)
        except Exception as e:  # noqa: BLE001 - 兜底需要兜住一切
            last_err = f"{type(e).__name__}: {e}"
    theme, note = fallback_decoration(payload)
    return DecorateOut(
        theme=guard_contrast(theme), note=note + "（AI 暂不可用，已用推荐配色）",
        model="fallback", mock=True,
    )
