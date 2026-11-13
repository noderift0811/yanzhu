from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from .errors import ApiError


def _today() -> str:
    return date.today().isoformat()


def check_quota(conn: sqlite3.Connection, user: Any, kind: str) -> None:
    """kind: gen | chat。跨日自动重置；超限抛 429 并带 quota_reset_at。"""
    today = _today()
    if user["quota_reset_at"] != today:
        conn.execute(
            "UPDATE users SET quota_gen_used=0, quota_chat_used=0, quota_reset_at=? WHERE id=?",
            (today, user["id"]),
        )
        fresh = conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
        if fresh is not None:
            user = fresh
    used = user["quota_gen_used"] if kind == "gen" else user["quota_chat_used"]
    limit = user["quota_gen_daily"] if kind == "gen" else user["quota_chat_daily"]
    if used >= limit:
        label = "生成" if kind == "gen" else "对话"
        raise ApiError(
            429,
            "QUOTA_EXCEEDED",
            f"今日{label}次数已用尽（{limit} 次/日）",
            {"quota_reset_at": user["quota_reset_at"]},
        )


def consume_quota(conn: sqlite3.Connection, user_id: str, kind: str) -> None:
    field = "quota_gen_used" if kind == "gen" else "quota_chat_used"
    conn.execute(f"UPDATE users SET {field} = {field} + 1 WHERE id=?", (user_id,))


def log_llm_call(
    conn: sqlite3.Connection,
    user_id: str,
    purpose: str,
    adapter: str,
    model: str,
    latency_ms: int,
    status: str,
    error: str = "",
) -> None:
    from datetime import datetime, timezone

    conn.execute(
        "INSERT INTO llm_calls (user_id, purpose, adapter, model, latency_ms, status, error, created_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (user_id, purpose, adapter, model or "mock", latency_ms, status, error or None,
         datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )
