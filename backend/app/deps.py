from __future__ import annotations

import sqlite3

import jwt
from fastapi import Depends, Request

from .db import get_db
from .errors import ApiError
from .security import decode_token

# JWT 从自定义头 X-Yanzhu-Token 读取，而不是 Authorization。
# 原因：公网分享时给隧道挂 HTTP Basic 认证（cpolar -httpauth）会占用
# Authorization 头，一个头装不下 Basic 与 Bearer 两种凭据；一旦前端在
# 已带 Bearer 的请求上被要求 Basic，cpolar 会直接 401，所有接口失效。
# 保留 Bearer 作为兜底：curl / 冒烟脚本 / 旧客户端仍可用。
TOKEN_HEADER = "x-yanzhu-token"


def _extract_token(request: Request) -> str:
    token = request.headers.get(TOKEN_HEADER)
    if token:
        return token.strip()
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


async def get_current_user(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> sqlite3.Row:
    token = _extract_token(request)
    if not token:
        raise ApiError(401, "UNAUTHORIZED", "未登录")
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise ApiError(401, "UNAUTHORIZED", "无效的访问令牌")
    except jwt.PyJWTError:
        raise ApiError(401, "UNAUTHORIZED", "登录已过期，请重新登录")
    row = conn.execute("SELECT * FROM users WHERE id=?", (payload["sub"],)).fetchone()
    if row is None:
        raise ApiError(401, "UNAUTHORIZED", "账号不存在")
    return row
