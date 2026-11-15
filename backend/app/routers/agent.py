"""Agent 五步链路的 SSE 接口。

与既有 POST /personas 并行存在：旧接口一行没改，前端「自由创作」与
人格库的重新生成继续走原路径；选了场景预设才走这里。
两者最终写入同一张 personas 表，因此聊天、换骨架、导出全部复用。

事件序列：start → step*/tool*/guard* → result → done（含完整 persona）
失败时 error 事件 + 不落库、不扣配额。
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ..db import get_db
from ..deps import get_current_user
from ..errors import ApiError
from ..llm.registry import get_adapter
from ..pipeline.agent import run_agent
from ..pipeline.brief import normalize_brief
from ..pipeline.guard import SAFETY_MARK
from ..pipeline.presets import enrich_brief, scene_of
from ..quota import check_quota, consume_quota, log_llm_call
from ..scenes import scene_of as account_scene
from ..schemas import AgentBuildIn, SpecModel
from .personas import _detail, _owned, _utcnow

router = APIRouter(prefix="/agent", tags=["agent"], dependencies=[Depends(get_current_user)])


def _force_name_keep_safety(spec: SpecModel, name: str) -> SpecModel:
    """用户指定名字时强制覆盖，但不把末尾的安全边界截断掉。

    personas._apply_forced_name 会把 system_prompt 直接切到 1500 字，
    Agent 链路的边界写在末尾，照搬会让护栏从生成结果里消失。
    """
    prompt = spec.system_prompt or ""
    idx = prompt.find(SAFETY_MARK)
    base, safety = (prompt[:idx], prompt[idx:]) if idx >= 0 else (prompt, "")
    old = spec.name or ""
    if old and old != name:
        base = base.replace(old, name)
    if name not in base:
        base = f"你的名字是{name}。" + base
    budget = max(0, 1500 - len(safety) - (1 if safety else 0))
    body = base[:budget].rstrip()
    merged = body + ("\n" + safety if safety else "")
    return spec.model_copy(update={"name": name, "system_prompt": merged})


@router.post("/build")
async def build_with_agent(
    body: AgentBuildIn,
    user=Depends(get_current_user),
    conn=Depends(get_db),
) -> StreamingResponse:
    check_quota(conn, user, "gen")
    if not body.tags and not body.free_text.strip():
        raise ApiError(400, "EMPTY_BRIEF", "请至少选择一个标签或填写描述")

    # 场景由账号决定，不由请求决定；只接受与账号一致的取值，否则 400。
    # 这条校验是「一个账号一个场景」的服务端落点，前端改参数绕不过去。
    scene_id = account_scene(user)
    if body.preset_id and body.preset_id != scene_id:
        raise ApiError(
            400,
            "SCENE_MISMATCH",
            f"当前账号的场景是 {scene_id}，不能按 {body.preset_id} 生成",
            {"scene_id": scene_id},
        )

    brief = normalize_brief(body.tags, body.free_text, body.name)
    brief = enrich_brief(brief, scene_id)
    scene = scene_of(brief)
    engineer = get_adapter("engineer")
    persona = get_adapter("persona")
    started = time.monotonic()

    async def event_gen():
        def sse(event: str, data: Dict[str, Any]) -> str:
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        result: Dict[str, Any] | None = None
        try:
            async for event, data in run_agent(
                engineer, brief, persona_adapter=persona, user_query=body.user_query
            ):
                if event == "result":
                    result = data
                    # 整包 spec 只落库，不重复推给前端；时间线用精简版
                    yield sse("result", {k: v for k, v in data.items() if k != "spec"})
                else:
                    yield sse(event, data)
                if event == "error":
                    return
        except Exception as e:  # noqa: BLE001 - 流内异常统一转 error 事件
            yield sse("error", {"message": f"Agent 链路异常: {type(e).__name__}: {e}"})
            return

        if result is None:
            yield sse("error", {"message": "Agent 未产出结果"})
            return

        try:
            spec = SpecModel.model_validate(result["spec"])
            if brief.get("name"):
                spec = _force_name_keep_safety(spec, brief["name"])
                spec = SpecModel.model_validate(spec.model_dump())
            needs_review = bool(result.get("needs_review"))

            # Agent 元数据存进 brief_json：详情接口会回传，供前端展示链路与证据，
            # 不必为参赛新增数据库表，也不破坏现有字段语义。
            stored_brief = {
                **brief,
                "preset_id": scene.get("preset_id", scene_id),
                "agent": {
                    "trace": result.get("trace") or [],
                    "tools_called": result.get("tools_called") or [],
                    "plan_source": result.get("plan_source"),
                    "evidence_ids": [h["id"] for h in (result.get("evidence") or [])],
                    "guard_flags": (result.get("output_guard") or {}).get("flags") or [],
                    "elapsed_ms": result.get("elapsed_ms"),
                },
            }
            row = {
                "keywords_json": json.dumps(
                    {"tags": brief["tags"], "free_text": brief["free_text"]}, ensure_ascii=False
                ),
                "brief_json": json.dumps(stored_brief, ensure_ascii=False),
                "status": "needs_review" if needs_review else "active",
            }
            from ..pipeline.assemble import spec_columns

            row.update(spec_columns(spec))
            now = _utcnow()
            target = body.target_persona_id
            if target:
                # 覆盖重建：先校验归属（非本人 404），再只换规格/限定词/状态，
                # 保留 id、scene_id、created_at、会话与消息。主页面落点不变。
                _owned(conn, target, user["id"])
                pid = target
                row["updated_at"] = now
                sets = ", ".join(f"{k}=?" for k in row)
                conn.execute(
                    f"UPDATE personas SET {sets} WHERE id=?", (*row.values(), pid)
                )
            else:
                pid = str(uuid.uuid4())
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
                # 专属网站模式：第一个生成的人格默认成为登录落点（主页面）
                if not user["primary_persona_id"]:
                    conn.execute(
                        "UPDATE users SET primary_persona_id=? WHERE id=?", (pid, user["id"])
                    )
            consume_quota(conn, user["id"], "gen")
            log_llm_call(
                conn, user["id"], "engineer", engineer.name, engineer.cfg.model,
                int((time.monotonic() - started) * 1000),
                "fallback" if needs_review else "ok", "",
            )
            detail = _detail(conn, pid, user["id"])
            fresh = conn.execute(
                "SELECT quota_gen_used, quota_gen_daily FROM users WHERE id=?", (user["id"],)
            ).fetchone()
            yield sse("done", {
                "persona": detail,
                "quota": {"gen_used": fresh["quota_gen_used"], "gen_daily": fresh["quota_gen_daily"]},
                "agent": stored_brief["agent"],
            })
        except Exception as e:  # noqa: BLE001 - 落库失败也要给前端明确结论
            yield sse("error", {"message": f"人格落库失败: {type(e).__name__}: {e}"})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
