from __future__ import annotations

import json
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from ..config import get_settings
from ..db import get_db
from ..deps import get_current_user
from ..errors import ApiError
from ..llm.registry import get_adapter
from ..pets import load_pet, pet_clause
from ..quota import check_quota, consume_quota, log_llm_call
from ..scenes import tone_clause, tone_of
from ..schemas import ConversationCreateIn, MessageCreateIn

router = APIRouter(tags=["chat"], dependencies=[Depends(get_current_user)])


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _owned_persona(conn: sqlite3.Connection, user_id: str, persona_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM personas WHERE id=? AND user_id=?", (persona_id, user_id)
    ).fetchone()
    if row is None:
        raise ApiError(404, "PERSONA_NOT_FOUND", "人格不存在")
    return row


def _owned_conversation(conn: sqlite3.Connection, user_id: str, cid: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM conversations WHERE id=? AND user_id=?", (cid, user_id)
    ).fetchone()
    if row is None:
        raise ApiError(404, "CONVERSATION_NOT_FOUND", "会话不存在")
    return row


def _message_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "role": row["role"],
        "content": row["content"],
        "tokens": row["tokens"],
        "created_at": row["created_at"],
    }


def _compose_system_prompt(conn: sqlite3.Connection, persona: sqlite3.Row, user: sqlite3.Row) -> str:
    """生成期 system_prompt + 运行时语气 + 宠物状态。三块都只拼接，不重写人设。

    语气与宠物状态都在对话时现算：点开关 / 喂宠物立刻生效，不重跑工程师模型、
    不耗生成配额。宠物状态放在语气之前，让语气修饰整个表达（包括提到宠物时）。
    """
    spec = json.loads(persona["spec_json"])
    pieces = [spec["system_prompt"]]
    pet = pet_clause(load_pet(conn, persona["id"]))
    if pet:
        pieces.append(pet)
    tone = tone_of(user)
    clause = tone_clause(tone)
    if any(tone.values()) and clause:
        pieces.append(clause)
    return "\n".join(pieces)


@router.get("/personas/{persona_id}/conversations")
def list_conversations(
    persona_id: str,
    user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> Dict[str, Any]:
    _owned_persona(conn, user["id"], persona_id)
    rows = conn.execute(
        "SELECT * FROM conversations WHERE user_id=? AND persona_id=? ORDER BY updated_at DESC",
        (user["id"], persona_id),
    ).fetchall()
    return {
        "items": [
            {
                "id": r["id"],
                "title": r["title"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]
    }


@router.post("/personas/{persona_id}/conversations", status_code=201)
def create_conversation(
    persona_id: str,
    body: ConversationCreateIn,
    user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> Dict[str, Any]:
    persona = _owned_persona(conn, user["id"], persona_id)
    cid, now = str(uuid.uuid4()), _utcnow()
    title = (body.title or "").strip() or "新会话"
    conn.execute(
        "INSERT INTO conversations (id, persona_id, user_id, title, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?)",
        (cid, persona_id, user["id"], title, now, now),
    )
    # 种子开场白：与建造揭晓中打出的内容一致
    spec = json.loads(persona["spec_json"])
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, tokens, created_at) VALUES (?,?,?,?,?)",
        (cid, "assistant", spec["opening_message"], 0, now),
    )
    return {"id": cid, "title": title, "created_at": now, "updated_at": now}


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: str,
    user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> None:
    """关闭会话：只删自己的，消息随会话一起清掉；人格与主页面不受影响。"""
    _owned_conversation(conn, user["id"], conversation_id)
    conn.execute("DELETE FROM messages WHERE conversation_id=?", (conversation_id,))
    conn.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))


@router.get("/conversations/{conversation_id}/messages")
def get_messages(
    conversation_id: str,
    before_id: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> Dict[str, Any]:
    _owned_conversation(conn, user["id"], conversation_id)
    if before_id is not None:
        rows = conn.execute(
            "SELECT * FROM messages WHERE conversation_id=? AND id<? ORDER BY id DESC LIMIT ?",
            (conversation_id, before_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?",
            (conversation_id, limit),
        ).fetchall()
    return {"items": [_message_dict(r) for r in reversed(rows)]}


@router.post("/conversations/{conversation_id}/messages/stream")
async def send_message_stream(
    conversation_id: str,
    body: MessageCreateIn,
    user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> StreamingResponse:
    """M1：SSE 流式。事件序列 meta → token* → done；失败时 error（并回滚用户消息，与 M0 语义一致）。"""
    conv = _owned_conversation(conn, user["id"], conversation_id)
    persona = _owned_persona(conn, user["id"], conv["persona_id"])
    check_quota(conn, user, "chat")

    now = _utcnow()
    cur = conn.execute(
        "INSERT INTO messages (conversation_id, role, content, tokens, created_at) VALUES (?,?,?,?,?)",
        (conversation_id, "user", body.content, 0, now),
    )
    user_msg = {"id": cur.lastrowid, "role": "user", "content": body.content, "tokens": 0, "created_at": now}

    s = get_settings()
    history = conn.execute(
        "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?",
        (conversation_id, s.chat_history_window),
    ).fetchall()
    system_prompt = _compose_system_prompt(conn, persona, user)
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages += [{"role": h["role"], "content": h["content"]} for h in reversed(history)]

    adapter = get_adapter("persona")
    started = time.monotonic()

    async def event_gen():
        def sse(event: str, data: Dict[str, Any]) -> str:
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        # 语气状态属于账号级运行时数据，在这里现取。之前从外层作用域引用 tone，
        # 抽 _compose_system_prompt 后该局部变量被删，导致 async generator 首帧 NameError，
        # SSE 只建立连接却零事件，前端永久卡在加载态。
        yield sse("meta", {"user_message": user_msg, "tone": tone_of(user)})
        chunks: List[str] = []
        try:
            async for delta in adapter.chat_stream(messages):
                if not delta:
                    continue
                chunks.append(delta)
                yield sse("token", {"text": delta})
        except Exception as e:  # noqa: BLE001 - 上游错误以 error 事件送达，并回滚用户消息
            log_llm_call(conn, user["id"], "persona", adapter.name, adapter.cfg.model, int((time.monotonic() - started) * 1000), "error", str(e))
            conn.execute("DELETE FROM messages WHERE id=?", (user_msg["id"],))
            yield sse("error", {"message": f"人格 AI 调用失败: {e}"})
            return

        reply = "".join(chunks).strip() or "……"
        log_llm_call(conn, user["id"], "persona", adapter.name, adapter.cfg.model, int((time.monotonic() - started) * 1000), "ok", "")
        tokens = max(1, len(reply) // 2)
        now2 = _utcnow()
        cur2 = conn.execute(
            "INSERT INTO messages (conversation_id, role, content, tokens, created_at) VALUES (?,?,?,?,?)",
            (conversation_id, "assistant", reply, tokens, now2),
        )
        conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now2, conversation_id))
        consume_quota(conn, user["id"], "chat")
        fresh = conn.execute("SELECT quota_chat_used, quota_chat_daily FROM users WHERE id=?", (user["id"],)).fetchone()
        yield sse(
            "done",
            {
                "assistant_message": {
                    "id": cur2.lastrowid,
                    "role": "assistant",
                    "content": reply,
                    "tokens": tokens,
                    "created_at": now2,
                },
                "quota": {
                    "chat_used": fresh["quota_chat_used"],
                    "chat_daily": fresh["quota_chat_daily"],
                },
            },
        )

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    body: MessageCreateIn,
    user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> Dict[str, Any]:
    """M0：非流式，整条返回。M1 升级点：改 SSE（chat_stream 逐 token 推送）。"""
    conv = _owned_conversation(conn, user["id"], conversation_id)
    persona = _owned_persona(conn, user["id"], conv["persona_id"])
    check_quota(conn, user, "chat")

    now = _utcnow()
    cur = conn.execute(
        "INSERT INTO messages (conversation_id, role, content, tokens, created_at) VALUES (?,?,?,?,?)",
        (conversation_id, "user", body.content, 0, now),
    )
    user_msg = {"id": cur.lastrowid, "role": "user", "content": body.content, "tokens": 0, "created_at": now}

    # 上下文：system_prompt + 最近 N 条历史（含刚插入的用户消息）
    s = get_settings()
    history = conn.execute(
        "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?",
        (conversation_id, s.chat_history_window),
    ).fetchall()
    system_prompt = _compose_system_prompt(conn, persona, user)
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages += [{"role": h["role"], "content": h["content"]} for h in reversed(history)]

    adapter = get_adapter("persona")
    started = time.monotonic()
    try:
        reply = await adapter.chat_text(messages)
        status, err = "ok", ""
    except Exception as e:  # noqa: BLE001 - 上游错误统一转 502
        raise ApiError(502, "LLM_UPSTREAM_ERROR", f"人格 AI 调用失败: {e}")
    latency = int((time.monotonic() - started) * 1000)
    log_llm_call(conn, user["id"], "persona", adapter.name, adapter.cfg.model, latency, status, err)

    tokens = max(1, len(reply) // 2)
    now2 = _utcnow()
    cur2 = conn.execute(
        "INSERT INTO messages (conversation_id, role, content, tokens, created_at) VALUES (?,?,?,?,?)",
        (conversation_id, "assistant", reply, tokens, now2),
    )
    conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now2, conversation_id))
    consume_quota(conn, user["id"], "chat")
    return {
        "user_message": user_msg,
        "assistant_message": {
            "id": cur2.lastrowid,
            "role": "assistant",
            "content": reply,
            "tokens": tokens,
            "created_at": now2,
        },
    }
