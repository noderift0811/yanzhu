from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .errors import install_error_handlers
from .models import init_db
from .routers import auth, chat, meta, personas


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
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
    for r in (auth.router, personas.router, chat.router, meta.router):
        app.include_router(r, prefix="/api")

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "app_env": get_settings().app_env}

    return app


app = create_app()
