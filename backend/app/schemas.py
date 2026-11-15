from __future__ import annotations

import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from .pipeline.engineer_prompt import SKELETON_IDS

COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class ThemeModel(BaseModel):
    primary: str
    bg: str
    surface: str
    text: str
    accent: str
    font_style: str = "system"
    decoration: str = "none"

    @field_validator("primary", "bg", "surface", "text", "accent")
    @classmethod
    def _color(cls, v: str) -> str:
        if not COLOR_RE.match(v or ""):
            raise ValueError(f"非法色值 {v!r}，须为 #RRGGBB")
        return v.lower()

    @field_validator("font_style")
    @classmethod
    def _font(cls, v: str) -> str:
        if v not in ("rounded", "serif", "mono", "system"):
            raise ValueError("font_style 须为 rounded/serif/mono/system 之一")
        return v

    @field_validator("decoration")
    @classmethod
    def _deco(cls, v: str) -> str:
        if v not in ("none", "petal", "stars", "grid", "paper"):
            raise ValueError("decoration 须为 none/petal/stars/grid/paper 之一")
        return v


class PageCopyModel(BaseModel):
    title: str = Field(min_length=1, max_length=30)
    greeting: str = Field(min_length=1, max_length=60)
    input_placeholder: str = Field(min_length=1, max_length=40)


class SpecModel(BaseModel):
    """工程师 AI 的唯一合法产出格式。LLM 不生成代码，只产此 JSON。"""

    name: str = Field(min_length=1, max_length=20)
    system_prompt: str = Field(min_length=20, max_length=1500)
    skeleton_id: str
    theme: ThemeModel
    page_copy: PageCopyModel
    opening_message: str = Field(min_length=1, max_length=200)

    @field_validator("skeleton_id")
    @classmethod
    def _skeleton(cls, v: str) -> str:
        if v not in SKELETON_IDS:
            raise ValueError(f"skeleton_id 必须在 {SKELETON_IDS} 中")
        return v


# ---------- 请求 / 响应 ----------

class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=20, pattern=r"^[A-Za-z0-9_\u4e00-\u9fa5]+$")
    password: str = Field(min_length=6, max_length=64)


class LoginIn(BaseModel):
    username: str
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class SceneIn(BaseModel):
    """选场景 / 换场景。confirm 只在「已有场景再换」时必填。"""

    scene: str = Field(min_length=2, max_length=20)
    confirm: bool = False


class ToneIn(BaseModel):
    """语气开关：三项都可空，只改传了的那些（悬浮球逐项点击）。"""

    calm: Optional[bool] = None
    brief: Optional[bool] = None
    no_exclaim: Optional[bool] = None


class PersonaCreateIn(BaseModel):
    # 上限 8：标签越多模型越难收敛，六七个互不冲突的标签已经足够描述一个人。
    # 互斥与组配额由 pipeline/tag_rules.py 进一步消解（这里只挡明显超量）。
    tags: List[str] = Field(default_factory=list, max_length=8)
    free_text: str = Field(default="", max_length=200)
    # 用户指定的角色名：给了就原样使用（工程师 AI 不得另起名字），留空则由 AI 起名
    name: Optional[str] = Field(default=None, min_length=1, max_length=20)


class AgentBuildIn(PersonaCreateIn):
    """五步 Agent 链路入参：与自由生成同一套字段，额外带场景预设与演示原话。

    preset_id 未知时后端回落到 free，不报错——外部直接调 API 也不该打断生成。
    user_query 只用于检索与护栏演示，不写入人格。
    """

    preset_id: Optional[str] = Field(default=None, max_length=20)
    user_query: str = Field(default="", max_length=200)


class PersonaPatchIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=20)
    theme: Optional[ThemeModel] = None
    # 换骨架不调 LLM、不耗生成配额；不传 theme 时自动套用该骨架的成套主题预设
    skeleton_id: Optional[str] = None
    # 专属网站模式：把这个人格设为登录落点（主页面）。星标切换，不调 LLM、不耗配额。
    set_primary: Optional[bool] = None

    @field_validator("skeleton_id")
    @classmethod
    def _skeleton(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in SKELETON_IDS:
            raise ValueError(f"skeleton_id 必须在 {SKELETON_IDS} 中")
        return v


class ConversationCreateIn(BaseModel):
    title: Optional[str] = Field(default=None, max_length=40)


class MessageCreateIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
