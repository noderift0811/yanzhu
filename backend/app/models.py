from __future__ import annotations

from .db import db_session

# 业务表 UUID VARCHAR(36) 主键；高频写入的 messages / llm_calls 用 BIGINT 自增
SCHEMA_SQL = [
    """CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        quota_gen_daily INTEGER NOT NULL DEFAULT 20,
        quota_chat_daily INTEGER NOT NULL DEFAULT 100,
        quota_gen_used INTEGER NOT NULL DEFAULT 0,
        quota_chat_used INTEGER NOT NULL DEFAULT 0,
        quota_reset_at TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS refresh_tokens (
        jti TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS personas (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        keywords_json TEXT NOT NULL,
        brief_json TEXT NOT NULL,
        spec_json TEXT NOT NULL,
        skeleton_id TEXT NOT NULL,
        theme_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        persona_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '新会话',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        tokens INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS llm_calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        purpose TEXT NOT NULL,
        adapter TEXT NOT NULL,
        model TEXT NOT NULL,
        latency_ms INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL,
        error TEXT,
        created_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_personas_user ON personas(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, persona_id)",
    "CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id, id)",
    "CREATE INDEX IF NOT EXISTS idx_llm_calls_user ON llm_calls(user_id, created_at)",
]


def init_db() -> None:
    with db_session() as conn:
        for stmt in SCHEMA_SQL:
            conn.execute(stmt)
