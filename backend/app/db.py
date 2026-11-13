from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from .config import get_settings


def connect() -> sqlite3.Connection:
    settings = get_settings()
    settings.db_file.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False：请求级短连接，允许依赖线程池与事件循环线程交接使用
    conn = sqlite3.connect(str(settings.db_file), timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


@contextmanager
def db_session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_db():
    """FastAPI 依赖：请求级连接，成功即提交。"""
    with db_session() as conn:
        yield conn
