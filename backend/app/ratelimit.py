from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict, Tuple

from fastapi.requests import Request

from .config import get_settings
from .errors import ApiError

# 沿用美食地图实测档位
REGISTER_LIMIT: Tuple[int, int] = (5, 900)   # 注册 15min/5 次每 IP
LOGIN_LIMIT: Tuple[int, int] = (20, 900)    # 登录 15min/20 次每 IP


class SlidingWindowLimiter:
    """进程内滑动窗口限流器。单实例部署够用；多实例需换 Redis（M3 评估）。"""

    def __init__(self) -> None:
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True


_limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_limit(request: Request, limit: int, window_seconds: int, scope: str = "default") -> None:
    # 每个类别的计数必须分开：注册与登录曾共用同一个 key，
    # 结果是同一 IP 登录 5 次后注册会被误判为「操作过于频繁」。
    key = f"{scope}:{client_ip(request)}"
    if not _limiter.allow(key, limit, window_seconds):
        raise ApiError(429, "RATE_LIMITED", "操作过于频繁，请稍后再试")


def check_limit_if_enabled(
    request: Request, limit: int, window_seconds: int, scope: str = "default"
) -> None:
    """带总开关的入口：只在非生产环境允许关闭（验收脚本连跑会打满注册额度）。

    app_env=prod 时 rate_limit_active 恒为 True，开关失效，避免误关到线上。
    """
    if not get_settings().rate_limit_active:
        return
    check_limit(request, limit, window_seconds, scope)
