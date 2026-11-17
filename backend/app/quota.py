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
    """记录一次 LLM 调用。观测性日志——写入失败必须静默，绝不能打断业务。

    SQLite 单写者下，chat 的 SSE 长事务尚未提交时，并发装修/生成写 llm_calls
    会撞上 `database is locked`（busy_timeout 对「读事务升级为写」不生效）。
    日志丢一条无妨，让请求 500 才是真问题。
    """
    from datetime import datetime, timezone

    try:
        conn.execute(
            "INSERT INTO llm_calls (user_id, purpose, adapter, model, latency_ms, status, error, created_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (user_id, purpose, adapter, model or "mock", latency_ms, status, error or None,
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
    except sqlite3.Error:
        # 不做 rollback：同一连接上可能还有本次请求的业务写入（如 chat 的消息），
        # rollback 会把它们一起回滚。吞掉异常即可，get_db 退出时会正常 commit 其余写入。
        pass
