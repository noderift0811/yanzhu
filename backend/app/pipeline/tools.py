"""MCP 风格工具注册表：Agent 每一步都走同一个工具入口，调用可查、参数可解释。

工具描述采用 MCP 的 name / description / inputSchema(JSON Schema) 口径，
通过 GET /api/meta/tools 完整暴露——评委可以直接看到 Agent 能调用哪些能力、
每个能力的参数契约，而不是只在 PPT 里写"我们用了 MCP"。

`call_tool` 统一处理同步与异步 handler；两步需要 LLM 的能力
（plan_generation / generate_spec）由 agent.py 通过 ctx["runners"] 注入，
避免 tools 与编排层循环依赖，也让这两步能边跑边推 SSE 中间状态。
"""
from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, List

from ..schemas import SpecModel
from .assemble import fallback_spec
from .engineer_prompt import SKELETONS
from .guard import SAFETY_TOOL, guard_spec, inject_safety
from .knowledge import RETRIEVE_TOOL, retrieve

PLAN_TOOL = {
    "name": "plan_generation",
    "description": "依据场景、检索证据与护栏报告，规划这次界面生成的语气、骨架倾向与安全策略。优先由 LLM 决策，失败降级为确定性规则。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "brief": {"type": "object", "description": "已归一化的用户输入与场景"},
            "evidence": {"type": "array", "description": "retrieve 命中的证据条目"},
            "guard": {"type": "object", "description": "输入护栏报告"},
        },
        "required": ["brief"],
    },
}
GENERATE_TOOL = {
    "name": "generate_spec",
    "description": "调用工程师 LLM 产出结构化 spec JSON（人设 + 骨架 + 主题 + 文案），LLM 只产数据不产代码。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "brief": {"type": "object"},
            "evidence": {"type": "array"},
            "plan": {"type": "object"},
        },
        "required": ["brief"],
    },
}
VALIDATE_TOOL = {
    "name": "validate_spec",
    "description": "按 SpecModel 校验结构，扫描医疗越界/否定感受措辞，并把安全边界确定性注入 system_prompt。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "spec": {"type": "object"},
            "level": {"type": "string", "enum": ["normal", "strict"], "default": "normal"},
        },
        "required": ["spec"],
    },
}
FALLBACK_TOOL = {
    "name": "fallback_spec",
    "description": "生成失败或校验越界时，构造确定性兜底 spec 并标记 needs_review，保证链路永不空手而归。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "brief": {"type": "object"},
            "level": {"type": "string", "enum": ["normal", "strict"], "default": "normal"},
        },
        "required": ["brief"],
    },
}
SKELETON_TOOL = {
    "name": "pick_skeleton",
    "description": "按标签与场景从 16 套骨架目录里挑视觉隐喻最贴切的一套，供规划步骤参考。",
    "inputSchema": {
        "type": "object",
        "properties": {"tags": {"type": "array", "items": {"type": "string"}}, "hint": {"type": "string"}},
        "required": ["tags"],
    },
}

TOOL_DESCRIPTORS: List[Dict[str, Any]] = [
    RETRIEVE_TOOL, SAFETY_TOOL, SKELETON_TOOL,
    PLAN_TOOL, GENERATE_TOOL, VALIDATE_TOOL, FALLBACK_TOOL,
]


def list_tools() -> Dict[str, Any]:
    return {"protocol": "MCP-style tool descriptors / JSON Schema", "count": len(TOOL_DESCRIPTORS), "tools": TOOL_DESCRIPTORS}


# ---- 确定性 handler ----

def _h_retrieve(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    hits = retrieve(args.get("query", ""), top_k=int(args.get("top_k", 3)), preset_id=args.get("preset_id"))
    return {"count": len(hits), "top_ids": [h["id"] for h in hits], "hits": hits}


def _h_screen(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from .guard import scan

    return scan(
        args.get("text", ""),
        level=args.get("level", "normal"),
        scene_id=args.get("scene") or None,
    ).as_dict()


def _h_skeleton(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    tags = [str(t) for t in (args.get("tags") or []) if t]
    hint = str(args.get("hint") or "")
    scored = []
    for s in SKELETONS:
        # 按标签词而不是逐字匹配：逐字会让「温柔」的「柔」和任何含「柔」的
        # 描述偶然撞上，选出来的骨架不可解释。
        score = sum(1 for t in tags if t and t in s["fit"]) + (2 if s["id"] in hint else 0)
        scored.append((score, s["id"], s["name"]))
    scored.sort(key=lambda x: (-x[0], x[1]))
    best = scored[0]
    return {"picked": best[1], "name": best[2], "candidates": [x[1] for x in scored[:3]]}


def _h_validate(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    level = args.get("level", "normal")
    scene_id = args.get("scene") or None
    spec = SpecModel.model_validate(args.get("spec") or {})
    report = guard_spec(spec, level=level, scene_id=scene_id)
    safe = inject_safety(spec, level=level, scene_id=scene_id)
    # 注入后再校验一次：护栏自己也必须产出合法 spec
    safe = SpecModel.model_validate(safe.model_dump())
    return {
        "valid": not report.blocked,
        "guard": report.as_dict(),
        "spec": safe.model_dump(),
        "safety_injected": "【安全边界" in safe.system_prompt,
        "scene_clause": bool(scene_id),
    }


def _h_fallback(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    level = args.get("level", "normal")
    scene_id = args.get("scene") or None
    spec = inject_safety(fallback_spec(args.get("brief") or {}), level=level, scene_id=scene_id)
    return {"spec": SpecModel.model_validate(spec.model_dump()).model_dump(), "needs_review": True}


HANDLERS: Dict[str, Callable] = {
    "retrieve_scene_knowledge": _h_retrieve,
    "screen_text": _h_screen,
    "pick_skeleton": _h_skeleton,
    "validate_spec": _h_validate,
    "fallback_spec": _h_fallback,
}


async def call_tool(name: str, args: Dict[str, Any], ctx: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """统一入口。返回 {tool, args, result}；未知工具抛 KeyError，由编排层转 error 事件。"""
    ctx = ctx or {}
    handler = HANDLERS.get(name) or (ctx.get("runners") or {}).get(name)
    if handler is None:
        raise KeyError(f"未注册的工具: {name}")
    result = handler(args, ctx)
    if inspect.isawaitable(result):
        result = await result
    return {"tool": name, "args": args, "result": result}
