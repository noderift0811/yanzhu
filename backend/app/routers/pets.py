"""宠物角接口：跟随人格的伙伴状态。确定性读写，不调 LLM、不耗配额。

- GET  /personas/{id}/pet        读状态；首次访问幂等创建（人格生成后不必单独播种）
- PATCH /personas/{id}/pet       改名字/物种/心情/活力/连续天数，或喂一次
- POST /personas/{id}/pet/checkin 每日续火花：同一天重复调用不累加
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends

from ..db import get_db
from ..deps import get_current_user
from ..errors import ApiError
from ..pets import ensure_pet, load_pet, pet_clause, pet_dict
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


@router.get("/personas/{persona_id}/pet")
def get_pet(
    persona_id: str,
    user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> Dict[str, Any]:
    _owned(conn, persona_id, user["id"])
    row = ensure_pet(conn, persona_id, user["id"])
    data = pet_dict(row)
    # 前端宠物角和「导出提示词」都显示同一段，保证所见即所得
    data["prompt_clause"] = pet_clause(row)
    return data


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
    data = pet_dict(load_pet(conn, persona_id))
    data["prompt_clause"] = pet_clause(load_pet(conn, persona_id))
    return data


@router.post("/personas/{persona_id}/pet/checkin")
def checkin_pet(
    persona_id: str,
    user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> Dict[str, Any]:
    """续火花：按 UTC 日期去重，同一天只加一次；断签超过 1 天则重置为 1。"""
    _owned(conn, persona_id, user["id"])
    row = ensure_pet(conn, persona_id, user["id"])
    today = datetime.now(timezone.utc).date().isoformat()
    keys = row.keys()
    last = (row["last_checkin"] or "")[:10] if "last_checkin" in keys else ""
    if last == today:
        data = pet_dict(row)
        data["prompt_clause"] = pet_clause(row)
        data["checked_in"] = False
        return data
    from datetime import date

    gap = (datetime.now(timezone.utc).date() - date.fromisoformat(last)).days if last else 999
    streak = int(row["streak"]) + 1 if gap <= 1 else 1
    now = _utcnow()
    conn.execute(
        "UPDATE pets SET streak=?, last_checkin=?, updated_at=? WHERE persona_id=?",
        (streak, now, now, persona_id),
    )
    fresh = load_pet(conn, persona_id)
    data = pet_dict(fresh)
    data["prompt_clause"] = pet_clause(fresh)
    data["checked_in"] = True
    return data
