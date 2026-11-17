from __future__ import annotations

import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from .pipeline.engineer_prompt import SKELETON_IDS

COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
# 头像图片：只接受前端 canvas 压缩后的 data URL（PNG/JPEG/WebP）。
# 上限按 base64 长度算，约 180KB 二进制——足以放 160×160 高清头像，又不让 SQLite/导出体积失控。
AVATAR_DATA_RE = re.compile(r"^data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$")
AVATAR_MAX_CHARS = 240_000


class AvatarModel(BaseModel):
    """头像显示方式：auto=首字渐变 / hidden=不显示 / image=自定义图片。跟随人格存储。"""
    mode: str = "auto"
    image: Optional[str] = None

    @field_validator("mode")
    @classmethod
    def _mode(cls, v: str) -> str:
        if v not in ("auto", "hidden", "image"):
            raise ValueError("avatar.mode 须为 auto/hidden/image 之一")
        return v

    @field_validator("image")
    @classmethod
    def _image(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if len(v) > AVATAR_MAX_CHARS:
            raise ValueError("头像图片过大，请先压缩")
        if not AVATAR_DATA_RE.match(v):
            raise ValueError("头像图片格式非法，须为 png/jpeg/webp 的 data URL")
        return v


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
    # 专属网站模式「重建」：传了就是覆盖这个已有的人格（保留 id/会话/created_at，只换规格与限定词），
    # 不传就是新建。归属校验在路由层做，前端改参数绕不过去。
    target_persona_id: Optional[str] = Field(default=None, max_length=36)


# 摆件覆盖层：骨架之上叠加的用户自装饰元件。只存类型/百分比坐标/内容，
# 不存 HTML/脚本——前端按类型白名单渲染，避免用户数据变成 XSS 入口。
DECORATION_TYPES = ("note", "quote", "photo", "badge")
DECORATION_MAX = 12


class DecorationModel(BaseModel):
    """单个摆件：type 决定渲染样式，x/y 为相对聊天区的百分比左上角坐标。"""
    id: str = Field(min_length=1, max_length=40)
    type: str
    x: float = Field(ge=0, le=95)
    y: float = Field(ge=0, le=95)
    text: Optional[str] = Field(default=None, max_length=120)
    image: Optional[str] = Field(default=None, max_length=240_000)

    @field_validator("type")
    @classmethod
    def _type(cls, v: str) -> str:
        if v not in DECORATION_TYPES:
            raise ValueError(f"摆件类型须为 {', '.join(DECORATION_TYPES)} 之一")
        return v

    @field_validator("image")
    @classmethod
    def _image(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not AVATAR_DATA_RE.match(v):
            raise ValueError("摆件图片须为压缩后的 png/jpeg/webp data URL")
        return v


# 伙伴角界面设置：显示开关 + 相对默认右下角的像素偏移。存人格 spec，确定性、不调 LLM。
class PetUiModel(BaseModel):
    hidden: bool = False
    x: float = Field(default=0, ge=-2000, le=2000)
    y: float = Field(default=0, ge=-2000, le=2000)


class PersonaPatchIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=20)
    theme: Optional[ThemeModel] = None
    # 头像设置：跟随人格，就地生效；不调 LLM、不耗生成配额
    avatar: Optional[AvatarModel] = None
    # 用户在设置页自行补充的人格描述：确定性拼进 system_prompt，不重生成、不耗配额
    extra_prompt: Optional[str] = Field(default=None, max_length=300)
    # 换骨架不调 LLM、不耗生成配额；不传 theme 时自动套用该骨架的成套主题预设
    skeleton_id: Optional[str] = None
    # 专属网站模式：把这个人格设为登录落点（主页面）。星标切换，不调 LLM、不耗配额。
    set_primary: Optional[bool] = None
    # 自由装饰层：整组替换摆件（增删拖拽后一次性保存）。确定性存储，不调 LLM。
    decorations: Optional[List[DecorationModel]] = Field(default=None, max_length=DECORATION_MAX)
    # 伙伴角界面：显示开关 + 拖动位置。确定性存储，不调 LLM。
    pet_ui: Optional[PetUiModel] = None

    @field_validator("skeleton_id")
    @classmethod
    def _skeleton(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in SKELETON_IDS:
            raise ValueError(f"skeleton_id 必须在 {SKELETON_IDS} 中")
        return v


class PetPatchIn(BaseModel):
    """宠物状态增量更新：名字/物种/心情/活力/连续天数。确定性存储，不调 LLM。"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=20)
    species: Optional[str] = Field(default=None, min_length=1, max_length=20)
    mood: Optional[str] = Field(default=None, max_length=20)
    energy: Optional[int] = Field(default=None, ge=0, le=100)
    streak: Optional[int] = Field(default=None, ge=0, le=9999)
    feed: Optional[bool] = None  # true = 喂一次，energy +25 并记 last_fed_at

    @field_validator("mood")
    @classmethod
    def _mood(cls, v: Optional[str]) -> Optional[str]:
        from .pets import MOODS

        if v is not None and v not in MOODS:
            raise ValueError(f"mood 须为 {', '.join(MOODS)} 之一")
        return v


class DecorateIn(BaseModel):
    """AI 装修：用户用自然语言描述想要的风格，AI 只产出主题参数（不写代码、不重写人设）。

    带上当前 theme / skeleton_id 作为上下文，AI 在现有基础上调整而非凭空换一套；
    骨架底色固定时提示 AI 注意明暗方向。装修不耗生成配额。
    """

    request: str = Field(min_length=2, max_length=200)
    theme: ThemeModel
    skeleton_id: Optional[str] = Field(default=None, max_length=36)


class DecorateOut(BaseModel):
    theme: ThemeModel
    note: str
    model: str
    mock: bool = False


class ConversationCreateIn(BaseModel):
    title: Optional[str] = Field(default=None, max_length=40)


class MessageCreateIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
