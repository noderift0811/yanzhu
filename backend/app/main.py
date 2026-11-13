from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .errors import install_error_handlers
from .models import init_db
from .pipeline.presets import validate_presets
from .routers import agent, auth, chat, meta, personas


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    # 场景预设是数据表，写错（字段缺失 / 标签互斥冲突）会静默生成互相打架的
    # 限定词，与骨架预设同理，启动期就红比运行时难查强。
    errors = validate_presets()
    if errors:
        raise RuntimeError("场景预设自检失败: " + "; ".join(errors))
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
    for r in (auth.router, personas.router, agent.router, chat.router, meta.router):
        app.include_router(r, prefix="/api")

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "app_env": get_settings().app_env}

    return app


app = create_app()
