"""宠物状态 → 人格提示词片段。

设计要点：
- 宠物不是独立聊天对象，而是"长进人格里"的伙伴——AI 用自己的口吻提到它。
- 片段拼在 system_prompt 末尾（和语气开关同一层），运行时读库生成，不落回 spec，
  所以改宠物状态不耗生成配额、也不需要重跑五步 Agent。
- 状态词刻意用"行为线索"而不是数值：说"它有点困、蹭你的信纸"比"energy=30"
  更能让模型自然接话。
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Optional

MOODS = {
    "happy": "心情不错，尾巴一直摇",
    "hungry": "有点饿，围着你要吃的",
    "sleepy": "有点困，缩成一团打盹",
    "lonely": "有点想你，一直望着门口",
    "quiet": "安安静静地待着",
}
MOOD_KEYS = tuple(MOODS)


def pet_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "persona_id": row["persona_id"],
        "name": row["name"],
        "species": row["species"],
        "mood": row["mood"],
        "energy": row["energy"],
        "streak": row["streak"],
        "last_fed_at": row["last_fed_at"],
        "last_checkin": row["last_checkin"] if "last_checkin" in row.keys() else None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def load_pet(conn: sqlite3.Connection, persona_id: str) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM pets WHERE persona_id=?", (persona_id,)).fetchone()


def pet_clause(row: Optional[sqlite3.Row]) -> str:
    """把宠物状态翻译成一段可直接拼进 system_prompt 的中文指令。空则空串。"""
    if not row:
        return ""
    name = row["name"]
    species = row["species"]
    mood = row["mood"] if row["mood"] in MOODS else "quiet"
    energy = int(row["energy"])
    streak = int(row["streak"])
    parts = [
        f"【伙伴状态】你身边有一只叫{name}的{species}，已经陪你连续{streak}天。",
        f"它此刻{MOODS[mood]}。",
    ]
    if energy <= 25:
        parts.append("它没什么精神，你说话会不自觉地放慢、更温柔。")
    elif energy >= 80:
        parts.append("它很活泼，你说话时可以带点轻快的劲儿。")
    parts.append(f"它不一定是话题中心，但提到{name}时要用你现在的人格口吻，别像在播报数据。")
    return "".join(parts)


def ensure_pet(conn: sqlite3.Connection, persona_id: str, user_id: str, name: str = "团子", species: str = "猫") -> sqlite3.Row:
    """人格生成后幂等建宠物；已存在则原样返回。"""
    row = load_pet(conn, persona_id)
    if row:
        return row
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO pets (persona_id, user_id, name, species, mood, energy, streak, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (persona_id, user_id, name[:20], species[:20], "quiet", 70, 0, now, now),
    )
    return load_pet(conn, persona_id)
