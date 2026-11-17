"""宠物状态 → 人格提示词片段 / 续火花剧情。

设计要点：
- 宠物不是独立聊天对象，而是"长进人格里"的伙伴——AI 用自己的口吻提到它。
- 片段拼在 system_prompt 末尾（和语气开关同一层），运行时读库生成，不落回 spec，
  所以改宠物状态不耗生成配额、也不需要重跑五步 Agent。
- 状态词刻意用"行为线索"而不是数值：说"它有点困、蹭你的信纸"比"energy=30"
  更能让模型自然接话。
- 续火花（st streak）用日期差算剧情阶段：等信 → 打盹 → 走失。断签不清零历史
  （best_streak 保留），首次回来走"召回"文案，让损失有挽回入口而不是单纯惩罚。
- 打卡历史单独存 pet_checkins（每天一行），日历热力图只读这张表；首次读时若历史
  为空但 streak>0，按 last_checkin 往前补，老数据无需迁移脚本也能显示日历。
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

MOODS = {
    "happy": "心情不错，尾巴一直摇",
    "hungry": "有点饿，围着你要吃的",
    "sleepy": "有点困，缩成一团打盹",
    "lonely": "有点想你，一直望着门口",
    "quiet": "安安静静地待着",
}
MOOD_KEYS = tuple(MOODS)

# 剧情阶段：由"距上次续火花的日期差"推导，不落库（每天自动变化）。
# waiting 是张力点——昨天续过、今天还没续，宠物在等你的信。
STAGES = {
    "new": "刚来到你身边，还带着一点陌生",
    "together": "今天一直陪着你，安心地蜷在旁边",
    "waiting": "今晚一直在等你的信，时不时望向门口",
    "dozing": "两天没等到你，趴在窗台打盹，偶尔抬眼",
    "lost": "几天没见，有点生疏了，需要你多陪一会儿",
}
STAGE_KEYS = tuple(STAGES)


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _gap_days(last_checkin: Optional[str]) -> Optional[int]:
    """距上次打卡的天数：0=今天，1=昨天，None=从未打卡。"""
    if not last_checkin:
        return None
    try:
        last = date.fromisoformat(last_checkin[:10])
    except ValueError:
        return None
    return (_today() - last).days


def pet_stage(row: Optional[sqlite3.Row]) -> str:
    if not row:
        return "new"
    gap = _gap_days(row["last_checkin"] if "last_checkin" in row.keys() else None)
    if gap is None:
        return "new"
    if gap <= 0:
        return "together"
    if gap == 1:
        return "waiting"
    if gap == 2:
        return "dozing"
    return "lost"


def pet_dict(row: sqlite3.Row) -> Dict[str, Any]:
    keys = row.keys()
    gap = _gap_days(row["last_checkin"] if "last_checkin" in keys else None)
    stage = pet_stage(row)
    return {
        "persona_id": row["persona_id"],
        "name": row["name"],
        "species": row["species"],
        "mood": row["mood"],
        "energy": row["energy"],
        "streak": row["streak"],
        "best_streak": row["best_streak"] if "best_streak" in keys else row["streak"],
        "last_fed_at": row["last_fed_at"],
        "last_checkin": row["last_checkin"] if "last_checkin" in keys else None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        # 剧情派生字段：前端直接渲染，不必自己算日期
        "stage": stage,
        "stage_text": STAGES[stage],
        "days_away": gap if gap is not None and gap > 0 else 0,
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
    stage = pet_stage(row)
    parts = [
        f"【伙伴状态】你身边有一只叫{name}的{species}，已经陪你连续{streak}天。",
        f"它此刻{MOODS[mood]}。",
    ]
    # 剧情线索比数值更能让模型接住"聊聊它现在怎么样"这类问题。
    parts.append({
        "new": f"{name}刚到你身边不久，你们还在熟悉彼此。",
        "together": f"今天你和{name}待在一起，它很安心。",
        "waiting": f"{name}今晚一直在等你，你落笔时会不自觉地提到它。",
        "dozing": f"{name}这两天没等到你，有点蔫，你说话时会放轻、带点惦记。",
        "lost": f"{name}几天没见你了，你提起它时会有点愧疚和牵挂，语气更软。",
    }[stage])
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
        "INSERT INTO pets (persona_id, user_id, name, species, mood, energy, streak, best_streak, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (persona_id, user_id, name[:20], species[:20], "quiet", 70, 0, 0, now, now),
    )
    return load_pet(conn, persona_id)


def backfill_checkins(conn: sqlite3.Connection, row: sqlite3.Row) -> None:
    """老数据兼容：从未记过打卡历史但 streak>0 时，按 last_checkin 往前补日历。

    INSERT OR IGNORE 保证重复读不会累加；只在历史为空时补，避免用户刻意清空后又被写回。
    """
    if int(row["streak"] or 0) <= 0:
        return
    if conn.execute("SELECT 1 FROM pet_checkins WHERE persona_id=? LIMIT 1", (row["persona_id"],)).fetchone():
        return
    last = (row["last_checkin"] or "")[:10]
    if not last:
        return
    try:
        end = date.fromisoformat(last)
    except ValueError:
        return
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for i in range(int(row["streak"])):
        d = (end - timedelta(days=i)).isoformat()
        conn.execute(
            "INSERT OR IGNORE INTO pet_checkins (persona_id, checkin_date, created_at) VALUES (?,?,?)",
            (row["persona_id"], d, now),
        )


def pet_calendar(conn: sqlite3.Connection, persona_id: str, days: int = 28) -> List[Dict[str, Any]]:
    """最近 days 天的打卡格子（旧→新），用于日历热力图。"""
    today = _today()
    marked = {
        r["checkin_date"]
        for r in conn.execute(
            "SELECT checkin_date FROM pet_checkins WHERE persona_id=? AND checkin_date>=?",
            (persona_id, (today - timedelta(days=days - 1)).isoformat()),
        )
    }
    return [
        {
            "date": (today - timedelta(days=days - 1 - i)).isoformat(),
            "checked": (today - timedelta(days=days - 1 - i)).isoformat() in marked,
            "is_today": i == days - 1,
        }
        for i in range(days)
    ]
