"""宠物角接口：跟随人格的伙伴状态。确定性读写，不调 LLM、不耗配额。

- GET  /personas/{id}/pet        读状态 + 28 天打卡日历（首次访问幂等建宠物）
- PATCH /personas/{id}/pet       改名字/物种/心情/活力/连续天数，或喂一次
- POST /personas/{id}/pet/checkin 每日续火花：同一天重复调用不累加；断签后回来算"召回"
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends

from ..db import get_db
from ..deps import get_current_user
from ..errors import ApiError
from ..pets import (
    backfill_checkins,
    ensure_pet,
    load_pet,
    pet_calendar,
    pet_clause,
    pet_dict,
    pet_stage,
)
from ..schemas import PetPatchIn

router = APIRouter(tags=["pets"], dependencies=[Depends(get_current_user)])


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _owned(conn: sqlite3.Connection, persona_id: str, user_id: str) -> None:
    row = conn.execute(
        "SELECT 1 FROM personas WHERE id=? AND user_id=?", (persona_id, user_id)
    ).fetchone()
    if row is None:
        raise ApiError(404, "PERSONA_NOT_FOUND", "人格不存在")


def _payload(conn: sqlite3.Connection, persona_id: str, extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """统一组装返回：状态 + 提示词片段 + 日历，保证三个接口字段一致。"""
    row = load_pet(conn, persona_id)
    data = pet_dict(row)
    data["prompt_clause"] = pet_clause(row)
    data["calendar"] = pet_calendar(conn, persona_id)
    if extra:
        data.update(extra)
    return data


@router.get("/personas/{persona_id}/pet")
def get_pet(
    persona_id: str,
    user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> Dict[str, Any]:
    _owned(conn, persona_id, user["id"])
    row = ensure_pet(conn, persona_id, user["id"])
    backfill_checkins(conn, row)
    return _payload(conn, persona_id)


@router.patch("/personas/{persona_id}/pet")
def patch_pet(
    persona_id: str,
    body: PetPatchIn,
    user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> Dict[str, Any]:
    _owned(conn, persona_id, user["id"])
    row = ensure_pet(conn, persona_id, user["id"])
    updates: Dict[str, Any] = {}
    for key in ("name", "species", "mood", "energy", "streak"):
        value = getattr(body, key)
        if value is not None:
            updates[key] = value
            if key == "streak":
                # 手动改当前连续天数时，历史最高取较大者（不因手动调低而缩水）
                updates["best_streak"] = max(int(value), int(row["best_streak"] or 0))
    if body.feed:
        updates["energy"] = min(100, int(row["energy"]) + 25)
        updates["last_fed_at"] = _utcnow()
        if body.mood is None:
            updates["mood"] = "happy"
    if updates:
        updates["updated_at"] = _utcnow()
        sets = ", ".join(f"{k}=?" for k in updates)
        conn.execute(
            f"UPDATE pets SET {sets} WHERE persona_id=?", (*updates.values(), persona_id)
        )
    return _payload(conn, persona_id)


@router.post("/personas/{persona_id}/pet/checkin")
def checkin_pet(
    persona_id: str,
    user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> Dict[str, Any]:
    """续火花：按 UTC 日期去重。

    - gap=1（昨晚续过）→ streak+1，正常续上
    - gap>=2（断签）→ streak 重置为 1，但 best_streak 保留；返回 recalled=True
      让前端走"召回"剧情，把损失变成可挽回的故事而不是冷冰冰的清零。
    """
    _owned(conn, persona_id, user["id"])
    row = ensure_pet(conn, persona_id, user["id"])
    today = datetime.now(timezone.utc).date()
    today_s = today.isoformat()
    if (row["last_checkin"] or "")[:10] == today_s:
        return _payload(conn, persona_id, {"checked_in": False, "recalled": False})

    last = (row["last_checkin"] or "")[:10]
    gap = (today - date.fromisoformat(last)).days if last else 999
    streak = int(row["streak"]) + 1 if gap <= 1 else 1
    recalled = gap >= 2 and int(row["streak"]) > 0
    best = max(streak, int(row["best_streak"] or 0))
    now = _utcnow()
    conn.execute(
        "UPDATE pets SET streak=?, best_streak=?, last_checkin=?, mood=?, updated_at=? WHERE persona_id=?",
        (streak, best, now, "happy" if recalled or gap <= 1 else row["mood"], now, persona_id),
    )
    # 补写断签期间缺失的"今天"这一格（历史格子保留，热力图看得到断档）
    conn.execute(
        "INSERT OR IGNORE INTO pet_checkins (persona_id, checkin_date, created_at) VALUES (?,?,?)",
        (persona_id, today_s, now),
    )
    return _payload(
        conn,
        persona_id,
        {
            "checked_in": True,
            "recalled": recalled,
            "missed_days": gap - 1 if recalled else 0,
        },
    )
