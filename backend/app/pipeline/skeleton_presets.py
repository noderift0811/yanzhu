from __future__ import annotations

from typing import Any, Dict

# 换骨架时的「成套换装」配方：五色 + 字体气质 + 背景装饰 + 输入框文案。
#
# 为什么必须连主题一起换：16 套骨架里有 7 套的底色是写死的深色
#（terminal / radio / oracle / receipt / starship / neon / classroom），
# 而骨架正文色取的是主题里的 --pf-text。只换骨架不换主题，
# 浅色主题的深色文字落到深色骨架上就是黑底黑字看不见。
#
# 每套的色值取自该骨架自己的印记色（牛皮纸、墨绿板面、热敏纸、霓虹灯管等），
# 保证换过去第一眼就是那套骨架该有的样子，而不是「借了别人配色的皮」。
SKELETON_PRESETS: Dict[str, Dict[str, Any]] = {
    "minimal": {
        "placeholder": "说点什么吧…",
        "theme": {
            "primary": "#4f46e5", "bg": "#f7f7f8", "surface": "#ffffff",
            "text": "#1f2328", "accent": "#7c6cf0",
            "font_style": "system", "decoration": "none",
        },
    },
    "radio": {
        "placeholder": "点一首歌，或者说说话…",
        "theme": {
            "primary": "#d9744a", "bg": "#241a14", "surface": "#3a2c20",
            "text": "#f2e5d6", "accent": "#e0a458",
            "font_style": "rounded", "decoration": "none",
        },
    },
    "diary": {
        "placeholder": "想跟我说什么呢…",
        "theme": {
            "primary": "#8a7250", "bg": "#faf6ee", "surface": "#fffdf7",
            "text": "#4a3f33", "accent": "#c9a06a",
            "font_style": "serif", "decoration": "paper",
        },
    },
    "terminal": {
        "placeholder": "输入指令…",
        "theme": {
            "primary": "#5fd68c", "bg": "#0c1210", "surface": "#121a16",
            "text": "#d7f5e3", "accent": "#38bdf8",
            "font_style": "mono", "decoration": "grid",
        },
    },
    "letter": {
        "placeholder": "在页边写点什么…",
        "theme": {
            "primary": "#2f6fb3", "bg": "#faf7f1", "surface": "#fffdf8",
            "text": "#2f2a24", "accent": "#b08d57",
            "font_style": "serif", "decoration": "paper",
        },
    },
    "oracle": {
        "placeholder": "写下你想问的事…",
        "theme": {
            "primary": "#c9a227", "bg": "#15111f", "surface": "#1d1730",
            "text": "#ece7ff", "accent": "#8b5cf6",
            "font_style": "serif", "decoration": "stars",
        },
    },
    "clinic": {
        "placeholder": "描述你的症状…",
        "theme": {
            "primary": "#2f6fb3", "bg": "#f3f7fa", "surface": "#ffffff",
            "text": "#1f2d3d", "accent": "#6b8fa8",
            "font_style": "system", "decoration": "none",
        },
    },
    "receipt": {
        "placeholder": "今天想吃点什么…",
        "theme": {
            "primary": "#d9c9a3", "bg": "#1b1a16", "surface": "#232320",
            "text": "#efe9dc", "accent": "#e8a33d",
            "font_style": "mono", "decoration": "none",
        },
    },
    "library": {
        "placeholder": "写一句你想问这本书的话…",
        "theme": {
            "primary": "#8a6a3a", "bg": "#f3efe6", "surface": "#fffdf6",
            "text": "#3a2f22", "accent": "#b0834a",
            "font_style": "serif", "decoration": "paper",
        },
    },
    "starship": {
        "placeholder": "向舰载系统发送指令…",
        "theme": {
            "primary": "#22d3ee", "bg": "#060a11", "surface": "#0d1626",
            "text": "#c8dcf0", "accent": "#4f9cf9",
            "font_style": "mono", "decoration": "none",
        },
    },
    "potion": {
        "placeholder": "投入一份材料…",
        "theme": {
            "primary": "#5e7a4a", "bg": "#efe7d3", "surface": "#f8f2e2",
            "text": "#3c3a24", "accent": "#9c7b3f",
            "font_style": "serif", "decoration": "none",
        },
    },
    "neon": {
        "placeholder": "敲一下门…",
        "theme": {
            "primary": "#ff2d95", "bg": "#09090f", "surface": "#14101c",
            "text": "#efeaff", "accent": "#22d3ee",
            "font_style": "mono", "decoration": "none",
        },
    },
    "garden": {
        "placeholder": "记下你此刻看到的东西…",
        "theme": {
            "primary": "#5e7a4a", "bg": "#f2f1e6", "surface": "#fbfaf0",
            "text": "#3a4234", "accent": "#8fae6d",
            "font_style": "serif", "decoration": "none",
        },
    },
    "classroom": {
        "placeholder": "举手提问…",
        "theme": {
            "primary": "#e8e4d0", "bg": "#1f3a2e", "surface": "#2f3a33",
            "text": "#f2f4e8", "accent": "#cfe0a8",
            "font_style": "mono", "decoration": "none",
        },
    },
    "casefile": {
        "placeholder": "补充你掌握的情况…",
        "theme": {
            "primary": "#7a4a2b", "bg": "#c9b08a", "surface": "#efe6d0",
            "text": "#2e2a24", "accent": "#a83a2c",
            "font_style": "mono", "decoration": "none",
        },
    },
    "bbs": {
        "placeholder": "回帖…",
        "theme": {
            "primary": "#2f6fb3", "bg": "#eef1f6", "surface": "#ffffff",
            "text": "#1f2937", "accent": "#4f8fd6",
            "font_style": "system", "decoration": "none",
        },
    },
}

# 启动即校验：新增骨架若忘记配预设，这里直接炸掉，而不是等到用户换骨架时才 500
from .engineer_prompt import SKELETON_IDS  # noqa: E402 - 放在末尾避免与提示词模块的导入顺序纠缠

_missing = [sid for sid in SKELETON_IDS if sid not in SKELETON_PRESETS]
_extra = [sid for sid in SKELETON_PRESETS if sid not in SKELETON_IDS]
if _missing or _extra:
    raise RuntimeError(
        f"skeleton_presets 与骨架目录不一致：缺预设 {_missing}，多余 {_extra}"
    )
