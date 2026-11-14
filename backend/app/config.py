from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_ROOT = Path(__file__).resolve().parent.parent  # backend/


class Settings(BaseSettings):
    """双密钥分离：ENGINEER_LLM_* 管生成，PERSONA_LLM_* 管聊天；留空走 Mock。"""

    model_config = SettingsConfigDict(
        env_file=str(APP_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "framework"
    jwt_secret: str = "dev-secret-please-change-me-in-production-0123456789abcdef"
    jwt_access_ttl_min: int = 15
    jwt_refresh_ttl_days: int = 7
    db_path: str = "data/yanzhu.db"

    # 工程师 AI（强模型，产 spec JSON）
    engineer_llm_adapter: str = "deepseek"
    engineer_llm_base_url: str = "https://api.deepseek.com/v1"
    engineer_llm_api_key: str = ""
    engineer_llm_model: str = "deepseek-v4-pro"

    # 人格 AI（轻量模型，聊天运行时）
    persona_llm_adapter: str = "deepseek"
    persona_llm_base_url: str = "https://api.deepseek.com/v1"
    persona_llm_api_key: str = ""
    persona_llm_model: str = "deepseek-flash"

    # 配额与上下文窗口
    quota_gen_daily: int = 20
    quota_chat_daily: int = 100
    chat_history_window: int = 20

    # 场景锁定：一个账号一个主场景，切换受确认 + 冷却约束（见 scenes.py）
    scene_switch_cooldown_days: int = 30

    # 演示 / 评审账号：固定账号让评委绕过注册限流直接登录（见 demo.py）。
    # 上线想关掉就设 DEMO_USER_ENABLED=false，登录页的填充入口会自动隐藏。
    demo_user_enabled: bool = True
    demo_username: str = "demo"
    demo_password: str = "yanzhu2026"
    demo_quota_gen: int = 200
    demo_quota_chat: int = 2000
    # 演示账号的初始场景（care = 心理陪伴，与 90 秒演示动线一致）
    demo_scene: str = "care"

    # 限流开关：仅供反复跑验收时使用（注册 15min/5IP 连跑几套测试就打满）。
    # app_env=prod 时无论怎么设都强制开启，见 ratelimit.py。
    rate_limit_disabled: bool = False

    @property
    def rate_limit_active(self) -> bool:
        return not (self.rate_limit_disabled and self.app_env != "prod")

    @property
    def db_file(self) -> Path:
        p = Path(self.db_path)
        return p if p.is_absolute() else APP_ROOT / p


@lru_cache
def get_settings() -> Settings:
    return Settings()
