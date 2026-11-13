from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Tuple

import bcrypt
import jwt
from fastapi.concurrency import run_in_threadpool

from .config import get_settings

ALGO = "HS256"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def verify_password(password: str, password_hash: str) -> bool:
    """bcrypt 是同步 CPU 操作，放线程池执行，避免阻塞事件循环。"""

    def _check() -> bool:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except ValueError:
            return False

    return await run_in_threadpool(_check)


def create_access_token(user_id: str) -> str:
    s = get_settings()
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": _now(),
        "exp": _now() + timedelta(minutes=s.jwt_access_ttl_min),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=ALGO)


def create_refresh_token(user_id: str) -> Tuple[str, str]:
    """返回 (token, jti)；jti 入库以支持轮换与吊销。"""
    s = get_settings()
    jti = uuid.uuid4().hex
    payload = {
        "sub": user_id,
        "type": "refresh",
        "jti": jti,
        "iat": _now(),
        "exp": _now() + timedelta(days=s.jwt_refresh_ttl_days),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=ALGO), jti


def decode_token(token: str) -> dict:
    return jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGO])
