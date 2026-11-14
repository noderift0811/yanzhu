from __future__ import annotations

import json
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends

from ..db import get_db
from ..deps import get_current_user
from ..errors import ApiError
from ..llm.registry import get_adapter
from ..pipeline.assemble import spec_columns
from ..pipeline.brief import normalize_brief
from ..pipeline.guard import inject_safety
from ..pipeline.presets import enrich_brief, has_scene
from ..scenes import scene_of
from ..pipeline.engineer_prompt import SKELETONS
from ..pipeline.skeleton_presets import SKELETON_PRESETS
from ..pipeline.validate import generate_spec
from ..quota import check_quota, consume_quota, log_llm_call
from ..schemas import PersonaCreateIn, PersonaPatchIn, SpecModel, ThemeModel

router = APIRouter(prefix="/personas", tags=["personas"], dependencies=[Depends(get_current_user)])

_SKELETON_NAMES = {s["id"]: s["name"] for s in SKELETONS}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _summary(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "skeleton_id": row["skeleton_id"],
        "skeleton_name": _SKELETON_NAMES.get(row["skeleton_id"], row["skeleton_id"]),
        "scene_id": row["scene_id"] if "scene_id" in row.keys() else "free",
        "theme": json.loads(row["theme_json"]),
        # 卡片上要显示限定词标签、重新生成要回填标签，列表接口必须带上 keywords
        "keywords": json.loads(row["keywords_json"]),
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _detail(conn: sqlite3.Connection, persona_id: str, user_id: str) -> Dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM personas WHERE id=? AND user_id=?", (persona_id, user_id)
    ).fetchone()
    if row is None:
        raise ApiError(404, "PERSONA_NOT_FOUND", "人格不存在")
    data = _summary(row)
    data["spec"] = json.loads(row["spec_json"])
    data["brief"] = json.loads(row["brief_json"])
    data["keywords"] = json.loads(row["keywords_json"])
    return data


def _owned(conn: sqlite3.Connection, persona_id: str, user_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM personas WHERE id=? AND user_id=?", (persona_id, user_id)
    ).fetchone()
    if row is None:
        raise ApiError(404, "PERSONA_NOT_FOUND", "人格不存在")
    return row


def _apply_forced_name(spec: SpecModel, name: str) -> SpecModel:
    """用户自己指定了角色名：落库前强制改成该名字。

    提示词里已经要求 AI 直接使用，但模型仍可能"自作主张"改一个字，
    所以这里做一次确定性兜底——名字是用户的决定权，不该由模型二次判断。
    只补一句身份声明是不够的：模型写的 system_prompt 里通篇是它自己起的名字，
    不替换就会出现「你的名字是沈砚。你是陆沉，一个档案管理员」这种自相矛盾的人设。
    """
    old_name = spec.name or ""
    prompt = spec.system_prompt or ""
    if old_name and old_name != name:
        prompt = prompt.replace(old_name, name)
    if name not in prompt:
        prompt = f"你的名字是{name}。" + prompt
    return spec.model_copy(update={"name": name, "system_prompt": prompt[:1500]})


async def _run_pipeline(
    conn: sqlite3.Connection, user_id: str, body: PersonaCreateIn, scene_id: str
) -> Dict[str, str]:
    """S1-S3 管线：brief 归一化 → 场景注入 → 工程师 AI → 校验/兜底 → 待写入列。

    scene_id 由调用方从 users.primary_scene 读出来传入，**不接受请求参数**：
    「一个账号一个场景」如果由前端决定，改个请求就绕过了。
    """
    brief = enrich_brief(normalize_brief(body.tags, body.free_text, body.name), scene_id)
    adapter = get_adapter("engineer")
    started = time.monotonic()
    status, err = "ok", ""
    try:
        spec, needs_review = await generate_spec(adapter, brief)
    except Exception as e:  # noqa: BLE001 - generate_spec 已兜底，双保险
        from ..pipeline.assemble import fallback_spec

        spec, needs_review, status, err = fallback_spec(brief), True, "error", str(e)
    if brief.get("name"):
        spec = _apply_forced_name(spec, brief["name"])
    if has_scene(scene_id):
        # 老路径（POST /personas）此前没有确定性护栏，只有 Agent 链路的 validate 步骤有。
        # 场景账号必须补上：否则同一个人在两条入口生成，边界一个有一个没有。
        level = (brief.get("scene") or {}).get("safety_level", "normal")
        spec = SpecModel.model_validate(
            inject_safety(spec, level=level, scene_id=scene_id).model_dump()
        )
    latency = int((time.monotonic() - started) * 1000)
    log_llm_call(conn, user_id, "engineer", adapter.name, adapter.cfg.model, latency, status, err)
    row: Dict[str, str] = {
        # 存 kept 而不是 body.tags：被互斥规则丢弃的标签从未参与生成，
        # 存原始值会让卡片标签与"重新生成"回填复活这些冲突，等于规则失效
        "keywords_json": json.dumps(
            {"tags": brief["tags"], "free_text": brief["free_text"]}, ensure_ascii=False
        ),
        "brief_json": json.dumps(brief, ensure_ascii=False),
        "status": "needs_review" if needs_review else "active",
    }
    row.update(spec_columns(spec))
    return row


@router.get("")
def list_personas(
    user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> Dict[str, Any]:
    rows = conn.execute(
        "SELECT * FROM personas WHERE user_id=? AND status!='archived' ORDER BY created_at DESC",
        (user["id"],),
    ).fetchall()
    archived = conn.execute(
        "SELECT COUNT(*) c FROM personas WHERE user_id=? AND status='archived'", (user["id"],)
    ).fetchone()["c"]
    return {"items": [_summary(r) for r in rows], "archived_count": archived}


@router.post("", status_code=201)
async def create_persona(
    body: PersonaCreateIn,
    user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> Dict[str, Any]:
    check_quota(conn, user, "gen")
    if not body.tags and not body.free_text.strip():
        raise ApiError(400, "EMPTY_BRIEF", "请至少选择一个标签或填写描述")
    scene_id = scene_of(user)
    row = await _run_pipeline(conn, user["id"], body, scene_id)
    pid, now = str(uuid.uuid4()), _utcnow()
    conn.execute(
        "INSERT INTO personas (id, user_id, name, keywords_json, brief_json, spec_json,"
        " skeleton_id, theme_json, status, scene_id, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            pid, user["id"], row["name"], row["keywords_json"], row["brief_json"],
            row["spec_json"], row["skeleton_id"], row["theme_json"], row["status"],
            scene_id, now, now,
        ),
    )
    consume_quota(conn, user["id"], "gen")
    return _detail(conn, pid, user["id"])


@router.get("/{persona_id}")
def get_persona(
    persona_id: str,
    user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> Dict[str, Any]:
    return _detail(conn, persona_id, user["id"])


@router.patch("/{persona_id}")
def patch_persona(
    persona_id: str,
    body: PersonaPatchIn,
    user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> Dict[str, Any]:
    """局部更新：改名 / 改主题 / 换骨架。全程不调 LLM、不耗生成配额。"""
    row = _owned(conn, persona_id, user["id"])
    updates: Dict[str, Any] = {}
    spec = json.loads(row["spec_json"])
    spec_touched = False

    if body.name:
        updates["name"] = body.name
        # 改名不只是改列表里的显示名：人设提示词里写着旧名字，不同步就会出现
        # 「卡片叫沈砚、开口自称陆沉」的分裂，所以连 spec 一起改。
        # 两步与 _apply_forced_name 保持一致：先整体替换旧名，替换不到就补一句身份声明。
        # 只做替换是不够的——提示词里本来就没写名字的人格（老数据、手工样本）
        # 改完仍然是"无名之人"，测出来的表现就是头像换了名、开口不自称。
        old_name = spec.get("name") or ""
        prompt = spec.get("system_prompt") or ""
        if old_name and old_name != body.name:
            prompt = prompt.replace(old_name, body.name)
        if body.name not in prompt:
            prompt = f"你的名字是{body.name}。" + prompt
        spec["name"] = body.name
        spec["system_prompt"] = prompt[:1500]
        spec_touched = True

    # 显式传入的 theme 优先级最高；换骨架且未指定主题时，套用该骨架的成套预设
    theme = body.theme
    if body.skeleton_id and not theme:
        preset = SKELETON_PRESETS[body.skeleton_id]
        theme = ThemeModel(**preset["theme"])
        page_copy = spec.get("page_copy") or {}
        page_copy["input_placeholder"] = preset["placeholder"]
        spec["page_copy"] = page_copy

    if body.skeleton_id:
        updates["skeleton_id"] = body.skeleton_id
        spec["skeleton_id"] = body.skeleton_id
        spec_touched = True

    if theme:
        updates["theme_json"] = theme.model_dump_json()
        spec["theme"] = theme.model_dump()
        spec_touched = True

    if spec_touched:
        updates["spec_json"] = json.dumps(spec, ensure_ascii=False)

    if updates:
        updates["updated_at"] = _utcnow()
        sets = ", ".join(f"{k}=?" for k in updates)
        conn.execute(
            f"UPDATE personas SET {sets} WHERE id=?",
            (*updates.values(), persona_id),
        )
    return _detail(conn, persona_id, user["id"])


@router.delete("/{persona_id}", status_code=204)
def delete_persona(
    persona_id: str,
    user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> None:
    _owned(conn, persona_id, user["id"])
    conn.execute(
        "DELETE FROM messages WHERE conversation_id IN"
        " (SELECT id FROM conversations WHERE persona_id=?)",
        (persona_id,),
    )
    conn.execute("DELETE FROM conversations WHERE persona_id=?", (persona_id,))
    conn.execute("DELETE FROM personas WHERE id=?", (persona_id,))


@router.post("/{persona_id}/regenerate")
async def regenerate_persona(
    persona_id: str,
    body: PersonaCreateIn,
    user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> Dict[str, Any]:
    _owned(conn, persona_id, user["id"])
    check_quota(conn, user, "gen")
    if not body.tags and not body.free_text.strip():
        raise ApiError(400, "EMPTY_BRIEF", "请至少选择一个标签或填写描述")
    row = await _run_pipeline(conn, user["id"], body, scene_of(user))
    row["updated_at"] = _utcnow()
    sets = ", ".join(f"{k}=?" for k in row)
    conn.execute(
        f"UPDATE personas SET {sets} WHERE id=?",
        (*row.values(), persona_id),
    )
    consume_quota(conn, user["id"], "gen")
    return _detail(conn, persona_id, user["id"])
