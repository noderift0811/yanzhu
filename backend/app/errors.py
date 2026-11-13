from __future__ import annotations

from typing import Optional

from fastapi.requests import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """业务错误：统一输出 {"code": ..., "message": ..., ...extra}。"""

    def __init__(self, status: int, code: str, message: str, extra: Optional[dict] = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra or {}


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    content = {"code": exc.code, "message": exc.message}
    content.update(exc.extra)
    return JSONResponse(status_code=exc.status, content=content)


def install_error_handlers(app) -> None:
    app.add_exception_handler(ApiError, api_error_handler)
