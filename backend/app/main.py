from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .demo import ensure_demo_user
from .errors import install_error_handlers
from .models import init_db
from .pipeline.knowledge import validate_knowledge
from .pipeline.presets import validate_presets
from .routers import agent, auth, chat, decorate, meta, personas, pets


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    # 演示账号幂等播种：空库首启就存在，评委不必先注册（注册有 IP 限流）
    ensure_demo_user()
    # 场景预设与语料是数据表，写错（字段缺失 / 标签互斥冲突 / 某场景缺语料）
    # 会静默生成互相打架的限定词或检索不到证据，与骨架预设同理，启动期就红。
    errors = validate_presets() + validate_knowledge()
    if errors:
        raise RuntimeError("场景自检失败: " + "; ".join(errors))
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="言筑 YanZhu API — by 未命名者", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    for r in (auth.router, personas.router, agent.router, chat.router, meta.router, decorate.router, pets.router):
        app.include_router(r, prefix="/api")

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "app_env": get_settings().app_env}

    return app


app = create_app()
