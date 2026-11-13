"""五步 Agent 主链路：retrieve → plan → generate → validate → fallback。

这是本届「AI 技术深度」里 Agent 8 分的主体，也是把 RAG / AI 安全 / MCP
串进主链路的地方——不是在外挂面板里各做一个按钮，而是每一步都决定下一步的输入：

  检索证据 → 写进规划约束 → 决定生成提示词 → 校验产出并注入护栏 → 失败才兜底

每一步都通过 tools.call_tool 统一调用并产出 SSE 事件，前端时间线可见
「调用了什么工具、传了什么参数、得到什么结论」。LLM 只负责规划与产出结构化
spec JSON，不生成任何代码；规划器超时/失败会降级为确定性规则，
因此无 API Key 的评审机上整条链路依然完整可跑。
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncIterator, Dict, List, Tuple

from .knowledge import build_query, format_for_prompt
from .presets import scene_of
from .tools import call_tool, list_tools

STEPS: List[Dict[str, str]] = [
    {"id": "retrieve", "name": "检索", "tool": "retrieve_care_knowledge", "desc": "从本地知识库取回场景证据，并扫描输入风险"},
    {"id": "plan", "name": "规划", "tool": "plan_generation", "desc": "LLM 决定语气、骨架倾向与安全策略"},
    {"id": "generate", "name": "生成", "tool": "generate_spec", "desc": "工程师 AI 产出结构化 spec JSON（不产代码）"},
    {"id": "validate", "name": "校验", "tool": "validate_spec", "desc": "schema 校验 + 安全护栏 + 边界确定性注入"},
    {"id": "fallback", "name": "兜底", "tool": "fallback_spec", "desc": "异常或越界时确定性兜底并标记待复核"},
]

PLAN_SYSTEM = """你是言筑生成链路的规划器。只输出一个 JSON 对象，不要解释、不要 markdown 代码块。
字段（全部为短字符串）：
- tone：语气，不超过 20 字
- skeleton_hint：从给定的骨架 id 列表里挑一个最合适的
- safety_strategy：安全策略，不超过 30 字
- focus：本次最该强调的一件事，不超过 20 字
- avoid：必须避开的一类表达，不超过 20 字
硬约束：必须遵守 scene.constraints；若 evidence 里出现危机或求助相关条目，
safety_strategy 必须写明「危机表达优先给求助资源」。不得输出 JSON 之外的任何内容。"""

_PLAN_KEYS = ("tone", "skeleton_hint", "safety_strategy", "focus", "avoid")


def _strip_fence(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()


def _rule_plan(brief: Dict[str, Any], evidence: List[Dict[str, Any]], guard: Dict[str, Any]) -> Dict[str, Any]:
    """确定性规划：LLM 不可用时的降级结果，也是 LLM 输出的字段底稿。"""
    scene = scene_of(brief)
    tags = brief.get("tags") or []
    ids = [h.get("id", "") for h in evidence]
    crisis = "crisis_expression" in (guard.get("flags") or []) or "crisis-resources" in ids
    hint = scene.get("skeleton_hint") or "全部 16 套骨架"
    preferred = next((x.strip() for x in hint.split("/") if x.strip()), "minimal")
    if "crisis-resources" in ids and not crisis:
        crisis = True
    return {
        "tone": "短句、留白、不追问" if scene.get("safety_level") == "strict" else "、".join(tags[:2]) or "自然",
        "skeleton_hint": preferred,
        "safety_strategy": "危机表达优先给求助资源；不做诊断、不开药" if crisis else "不做诊断、不收集隐私",
        "focus": scene.get("goal") or "贴合限定词的人设与界面",
        "avoid": "想开点 / 别矫情 / 至少你还" if scene.get("safety_level") == "strict" else "空泛套话",
        "scene_constraints": list(scene.get("constraints") or []),
        "evidence_ids": ids,
        "guard_flags": list(guard.get("flags") or []),
    }


async def _plan_runner(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    brief = args.get("brief") or {}
    evidence = args.get("evidence") or []
    guard = args.get("guard") or {}
    rule = _rule_plan(brief, evidence, guard)
    adapter = ctx.get("persona_adapter")
    if adapter is None:
        return {"plan": rule, "source": "rule", "note": "未配置人格模型，使用确定性规划"}

    from .engineer_prompt import SKELETON_IDS

    payload = {
        "brief": {k: v for k, v in brief.items() if k != "dropped_tags"},
        "evidence": format_for_prompt(evidence),
        "guard": {"flags": guard.get("flags") or []},
        "rule_plan": rule,
        "skeleton_ids": SKELETON_IDS,
    }
    messages = [
        {"role": "system", "content": PLAN_SYSTEM},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    try:
        raw = await asyncio.wait_for(adapter.chat_text(messages), timeout=12)
        data = json.loads(_strip_fence(raw))
        if not isinstance(data, dict):
            raise ValueError("规划输出不是 JSON 对象")
        merged = dict(rule)
        for key in _PLAN_KEYS:
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                merged[key] = val.strip()[:60]
        return {"plan": merged, "source": "llm", "model": adapter.cfg.model}
    except Exception as e:  # noqa: BLE001 - 规划失败必须降级，不能拖垮主链路
        return {"plan": rule, "source": "rule", "note": f"LLM 规划不可用，已降级：{type(e).__name__}"}


async def _generate_runner(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from .validate import generate_spec

    adapter = ctx["engineer_adapter"]
    spec, needs_review = await generate_spec(
        adapter,
        args.get("brief") or {},
        context=args.get("evidence") or [],
        plan=args.get("plan") or {},
    )
    return {
        "spec": spec.model_dump(),
        "needs_review": needs_review,
        "adapter": adapter.name,
        "model": adapter.cfg.model,
    }


RUNNERS = {"plan_generation": _plan_runner, "generate_spec": _generate_runner}


def _short_args(args: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in (args or {}).items():
        if isinstance(v, (dict, list)):
            out[k] = f"<{type(v).__name__} len={len(v)}>"
        elif isinstance(v, str) and len(v) > 80:
            out[k] = v[:80] + "…"
        else:
            out[k] = v
    return out


def _tool_summary(name: str, result: Dict[str, Any]) -> str:
    if name == "retrieve_care_knowledge":
        return f"命中 {result.get('count', 0)} 条证据：{' / '.join(result.get('top_ids') or []) or '无'}"
    if name == "screen_text":
        return result.get("summary") or "扫描完成"
    if name == "pick_skeleton":
        return f"骨架倾向 {result.get('picked')}（{result.get('name')}）"
    if name == "plan_generation":
        p = result.get("plan") or {}
        return f"规划来源 {result.get('source')}；语气 {p.get('tone', '')}；骨架 {p.get('skeleton_hint', '')}"
    if name == "generate_spec":
        s = result.get("spec") or {}
        return f"{result.get('adapter')} 产出 spec：{s.get('name', '')} / {s.get('skeleton_id', '')}"
    if name == "validate_spec":
        g = result.get("guard") or {}
        return f"valid={result.get('valid')}；边界注入={result.get('safety_injected')}；{g.get('summary', '')}"
    if name == "fallback_spec":
        return "已构造确定性兜底 spec，标记 needs_review"
    return "工具调用完成"


async def run_agent(
    engineer_adapter,
    brief: Dict[str, Any],
    *,
    persona_adapter=None,
    user_query: str = "",
) -> AsyncIterator[Tuple[str, Dict[str, Any]]]:
    """产出 (event, data) 元组；路由层包装成 SSE。

    event: start / step / tool / guard / result / error
    """
    scene = scene_of(brief)
    level = scene.get("safety_level", "normal")
    ctx: Dict[str, Any] = {
        "engineer_adapter": engineer_adapter,
        "persona_adapter": persona_adapter,
        "runners": RUNNERS,
    }
    trace: List[Dict[str, Any]] = []
    tools_called: List[str] = []
    started = time.monotonic()

    yield "start", {
        "steps": STEPS,
        "preset": scene.get("preset_id", "free"),
        "safety_level": level,
        "engineer_adapter": engineer_adapter.name,
        "persona_adapter": getattr(persona_adapter, "name", "none"),
        "tools": [t["name"] for t in list_tools()["tools"]],
    }

    async def invoke(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        r = await call_tool(name, args, ctx)
        tools_called.append(name)
        yield_event = {
            "tool": name,
            "args": _short_args(args),
            "summary": _tool_summary(name, r["result"]),
        }
        return r, yield_event

    def step_event(step: Dict[str, str], status: str, summary: str, t0: float, **extra):
        entry = {
            "id": step["id"], "name": step["name"], "tool": step["tool"],
            "status": status, "summary": summary,
            "elapsed_ms": int((time.monotonic() - t0) * 1000),
            **extra,
        }
        if status in ("done", "skipped", "error"):
            trace.append({k: entry[k] for k in ("id", "name", "status", "summary", "elapsed_ms")})
        return entry

    try:
        # ---- 1 retrieve ----
        s0 = STEPS[0]
        t0 = time.monotonic()
        yield "step", step_event(s0, "running", "正在检索场景证据…", t0)
        r, ev = await invoke("retrieve_care_knowledge", {
            "query": build_query(brief, user_query or brief.get("free_text", "")),
            "top_k": 3,
            "preset_id": scene.get("preset_id", "free"),
        })
        evidence = r["result"]["hits"]
        yield "tool", ev

        input_text = " ".join([
            user_query or "", brief.get("free_text") or "", " ".join(brief.get("tags") or []),
        ])
        gr, gev = await invoke("screen_text", {"text": input_text, "level": level})
        input_guard = gr["result"]
        yield "tool", gev
        yield "guard", {"phase": "input", **{k: input_guard.get(k) for k in ("level", "flags", "resources", "summary")}}
        yield "step", step_event(
            s0, "done",
            f"取回 {len(evidence)} 条证据，输入护栏：{input_guard.get('summary', '')}",
            t0, evidence_ids=[h["id"] for h in evidence],
        )

        # ---- 2 plan ----
        s1 = STEPS[1]
        t1 = time.monotonic()
        yield "step", step_event(s1, "running", "正在规划语气与安全策略…", t1)
        sk, skev = await invoke("pick_skeleton", {
            "tags": brief.get("tags") or [],
            "hint": scene.get("skeleton_hint", ""),
        })
        yield "tool", skev
        pr, pev = await invoke("plan_generation", {
            "brief": brief, "evidence": evidence, "guard": input_guard,
        })
        plan = pr["result"]["plan"]
        plan_source = pr["result"]["source"]
        plan["skeleton_candidates"] = sk["result"]["candidates"]
        yield "tool", pev
        yield "step", step_event(
            s1, "done", f"规划完成（{plan_source}）：{plan.get('tone', '')}", t1,
            plan=plan, plan_source=plan_source,
        )

        # ---- 3 generate ----
        s2 = STEPS[2]
        t2 = time.monotonic()
        yield "step", step_event(s2, "running", "工程师 AI 正在产出结构化 spec…", t2)
        gen, gev2 = await invoke("generate_spec", {"brief": brief, "evidence": evidence, "plan": plan})
        spec = gen["result"]["spec"]
        needs_review = bool(gen["result"].get("needs_review"))
        yield "tool", gev2
        yield "step", step_event(
            s2, "done",
            f"spec 已生成：{spec.get('name', '')} / {spec.get('skeleton_id', '')}", t2,
        )

        # ---- 4 validate ----
        s3 = STEPS[3]
        t3 = time.monotonic()
        yield "step", step_event(s3, "running", "校验结构并注入安全边界…", t3)
        val, vev = await invoke("validate_spec", {"spec": spec, "level": level})
        spec = val["result"]["spec"]
        valid = bool(val["result"].get("valid"))
        output_guard = val["result"]["guard"]
        yield "tool", vev
        yield "guard", {"phase": "output", **{k: output_guard.get(k) for k in ("level", "flags", "resources", "summary", "blocked")}}
        yield "step", step_event(
            s3, "done", vev["summary"], t3,
            valid=valid, safety_injected=val["result"].get("safety_injected"),
        )

        # ---- 5 fallback ----
        s4 = STEPS[4]
        t4 = time.monotonic()
        need_fallback = (not valid) or needs_review
        yield "step", step_event(
            s4, "running",
            "检测到越界，正在构造兜底…" if need_fallback else "检查是否需要兜底…",
            t4,
        )
        if need_fallback:
            fb, fev = await invoke("fallback_spec", {"brief": brief, "level": level})
            spec = fb["result"]["spec"]
            needs_review = True
            yield "tool", fev
            yield "step", step_event(s4, "done", "兜底已启用：确定性 spec + 待复核标记", t4, used=True)
        else:
            yield "step", step_event(s4, "skipped", "兜底未触发（五步链路完整走通）", t4, used=False)

        yield "result", {
            "spec": spec,
            "needs_review": needs_review,
            "plan": plan,
            "plan_source": plan_source,
            "evidence": format_for_prompt(evidence),
            "input_guard": input_guard,
            "output_guard": output_guard,
            "trace": trace,
            "tools_called": tools_called,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }
    except Exception as e:  # noqa: BLE001 - SSE 链路内部错误统一转 error 事件
        yield "error", {"message": f"Agent 链路失败: {type(e).__name__}: {e}", "trace": trace}
