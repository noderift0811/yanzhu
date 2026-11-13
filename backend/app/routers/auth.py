from __future__ import annotations

import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, Request

from ..config import get_settings
from ..db import get_db
from ..deps import get_current_user
from ..errors import ApiError
from ..ratelimit import LOGIN_LIMIT, REGISTER_LIMIT, check_limit_if_enabled
from ..schemas import LoginIn, RefreshIn, RegisterIn, TokenOut
from ..security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _issue_tokens(conn: sqlite3.Connection, user_id: str) -> TokenOut:
    access = create_access_token(user_id)
    refresh, jti = create_refresh_token(user_id)
    s = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(days=s.jwt_refresh_ttl_days)
    conn.execute(
        "INSERT INTO refresh_tokens (jti, user_id, expires_at, created_at) VALUES (?,?,?,?)",
        (jti, user_id, expires.isoformat(timespec="seconds"), _utcnow()),
    )
    return TokenOut(access_token=access, refresh_token=refresh)


@router.post("/register", response_model=TokenOut, status_code=201)
def register(
    body: RegisterIn,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> TokenOut:
    check_limit_if_enabled(request, *REGISTER_LIMIT, scope="register")
    exists = conn.execute("SELECT 1 FROM users WHERE username=?", (body.username,)).fetchone()
    if exists:
        raise ApiError(409, "USERNAME_TAKEN", "用户名已被注册")
    uid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO users (id, username, password_hash, quota_reset_at, created_at) VALUES (?,?,?,?,?)",
        (uid, body.username, hash_password(body.password), date.today().isoformat(), _utcnow()),
    )
    return _issue_tokens(conn, uid)


@router.post("/login", response_model=TokenOut)
async def login(
    body: LoginIn,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> TokenOut:
    check_limit_if_enabled(request, *LOGIN_LIMIT, scope="login")
    row = conn.execute("SELECT * FROM users WHERE username=?", (body.username,)).fetchone()
    if row is None or not await verify_password(body.password, row["password_hash"]):
        raise ApiError(401, "INVALID_CREDENTIALS", "用户名或密码错误")
    return _issue_tokens(conn, row["id"])


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, conn: sqlite3.Connection = Depends(get_db)) -> TokenOut:
    try:
        payload = decode_token(body.refresh_token)
    except jwt.PyJWTError:
        raise ApiError(401, "INVALID_REFRESH", "刷新令牌无效或已过期")
    if payload.get("type") != "refresh":
        raise ApiError(401, "INVALID_REFRESH", "刷新令牌类型错误")
    row = conn.execute("SELECT * FROM refresh_tokens WHERE jti=?", (payload.get("jti"),)).fetchone()
    if row is None:
        raise ApiError(401, "INVALID_REFRESH", "刷新令牌已吊销（可能已轮换），请重新登录")
    # 轮换：旧 jti 作废，顺带清理过期令牌
    conn.execute("DELETE FROM refresh_tokens WHERE expires_at < ?", (_utcnow(),))
    conn.execute("DELETE FROM refresh_tokens WHERE jti=?", (row["jti"],))
    return _issue_tokens(conn, row["user_id"])


@router.get("/me")
def me(user: sqlite3.Row = Depends(get_current_user)) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "quota_gen_daily": user["quota_gen_daily"],
        "quota_chat_daily": user["quota_chat_daily"],
        "quota_gen_used": user["quota_gen_used"],
        "quota_chat_used": user["quota_chat_used"],
        "quota_reset_at": user["quota_reset_at"],
        "created_at": user["created_at"],
    }
