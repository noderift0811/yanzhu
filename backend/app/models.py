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
        created_at TEXT NOT NULL,
        primary_scene TEXT,
        scene_changed_at TEXT,
        tone_json TEXT NOT NULL DEFAULT '{}',
        primary_persona_id TEXT
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
        scene_id TEXT NOT NULL DEFAULT 'free',
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


def _columns(conn, table: str) -> set:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _backfill_legacy_scene(conn) -> None:
    """老用户统一视为 free（改造前他们本来就走的无场景路径）。

    演示账号排除在外：它由 demo.ensure_demo_user 播种成预设场景，
    如果这里先填成 free，播种逻辑看到"已选"就不会再纠正，
    评委拿到的账号就会落在没有语料的自由场景里。
    """
    from .config import get_settings

    conn.execute(
        "UPDATE users SET primary_scene='free' WHERE primary_scene IS NULL AND username<>?",
        (get_settings().demo_username,),
    )


# 场景锁定是改造后新增的列。老库必须能直接起来：SQLite 的 ALTER TABLE ADD COLUMN
# 不能加无默认值的 NOT NULL，所以 primary_scene 允许为空，而「空」在这里有明确含义
# ——还没选场景（注册后强制引导），与老用户的 free 区分开。
# 回填只在「本次才加上这一列」时执行，否则每次启动都会把新注册用户的空值填成 free，
# 强制选场景的引导就永远不会出现。
_MIGRATIONS = {
    "users": [
        ("primary_scene", "TEXT", _backfill_legacy_scene),
        ("scene_changed_at", "TEXT", None),
        ("tone_json", "TEXT NOT NULL DEFAULT '{}'", None),
        # 专属网站模式：登录后的落点人格。空 = 还没建过人格 → 落开站页。
        ("primary_persona_id", "TEXT", None),
    ],
    "personas": [
        ("scene_id", "TEXT NOT NULL DEFAULT 'free'", None),
    ],
}


def _migrate(conn) -> None:
    for table, additions in _MIGRATIONS.items():
        have = _columns(conn, table)
        for name, ddl, backfill in additions:
            if name in have:
                continue
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
            if backfill:
                backfill(conn)


def init_db() -> None:
    with db_session() as conn:
        for stmt in SCHEMA_SQL:
            conn.execute(stmt)
        _migrate(conn)
