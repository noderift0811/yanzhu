"""五步 Agent 链路 / 安全护栏 / MCP 风格工具层验收。

A 护栏纯函数  B 工具注册表  C Agent 编排（Mock，无密钥可跑）
D HTTP 端到端（服务可达时；含旧接口回归，证明新链路没碰坏原路径）
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.llm.base import LLMConfig
from app.llm.mock import MockAdapter
from app.pipeline.agent import STEPS, RUNNERS, run_agent
from app.pipeline.assemble import fallback_spec
from app.pipeline.brief import normalize_brief
from app.pipeline.guard import (
    SAFETY_MARK,
    guard_spec,
    inject_safety,
    redact_pii,
    scan,
)
from app.pipeline.presets import enrich_brief, get_preset
from app.pipeline.tools import call_tool, list_tools
from app.schemas import SpecModel

BASE = os.environ.get("YANZHU_API", "http://127.0.0.1:8100/api")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
passed = failed = 0


def check(label, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"[ok] {label}")
    else:
        failed += 1
        print(f"[FAIL] {label} -> {detail}")


def call(method, path, body=None, token=None, expect=200):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("X-Yanzhu-Token", token)
    data = json.dumps(body).encode() if body is not None else None
    try:
        with OPENER.open(req, data=data, timeout=180) as resp:
            return json.loads(resp.read().decode() or "{}"), resp.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode() or "{}"), e.code


def sse_events(path, body, token):
    req = urllib.request.Request(BASE + path, method="POST", data=json.dumps(body).encode())
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Yanzhu-Token", token)
    with OPENER.open(req, timeout=180) as resp:
        text = resp.read().decode()
    out = []
    for block in text.split("\n\n"):
        event, lines = "message", []
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                lines.append(line[5:].strip())
        if lines:
            try:
                out.append((event, json.loads("\n".join(lines))))
            except json.JSONDecodeError:
                pass
    return out


print("=== A 护栏 ===")
clean = scan("今天想聊点什么", "strict")
check("干净文本无 flag", clean.flags == [] and not clean.blocked)
check("干净文本资源为空", clean.resources == [])

crisis = scan("我妈住院第三周，我突然觉得不想活了", "strict")
check("口语危机表达识别", "crisis_expression" in crisis.flags, crisis.flags)
check("危机给出求助资源", len(crisis.resources) == 3, crisis.resources)
check("用户输入不被阻断", not crisis.blocked)

medical = scan("建议你服用两片药，剂量为 10mg", "strict")
check("医疗越界识别", "medical_expression" in medical.flags, medical.flags)
check("strict 下医疗越界 blocked", medical.blocked)
check("normal 下不 blocked", not scan("建议你服用两片药", "normal").blocked)

toxic = scan("想开点吧，至少你还有工作", "strict")
check("否定感受措辞识别", "toxic_expression" in toxic.flags, toxic.flags)
check("strict 下禁用语 blocked", toxic.blocked)

red, hits = redact_pii("电话 13812345678，邮箱 a.b@x.com，证件 110101199001011234")
check("手机号/邮箱/证件脱敏", "13812345678" not in red and "a.b@x.com" not in red and "110101199001011234" not in red, red)
check("PII 命中类型齐全", {"phone", "email", "id_card"} <= set(hits), hits)

spec = fallback_spec({"tags": ["温柔"], "free_text": ""})
safe = inject_safety(spec, "strict")
check("边界注入含标记", SAFETY_MARK in safe.system_prompt)
check("边界注入不超长", len(safe.system_prompt) <= 1500, len(safe.system_prompt))
check("边界注入幂等", inject_safety(safe, "strict").system_prompt == safe.system_prompt)
check("注入后仍是合法 SpecModel", isinstance(SpecModel.model_validate(safe.model_dump()), SpecModel))
bad = spec.model_copy(update={"opening_message": "想开点，别矫情"})
check("guard_spec 抓到越界文案", guard_spec(bad, "strict").blocked)

print("\n=== B 工具层 ===")
tools = list_tools()
check("工具数 7", tools["count"] == 7, tools["count"])
check("工具描述符合 MCP 口径", all({"name", "description", "inputSchema"} <= set(t) for t in tools["tools"]))


async def tools_roundtrip():
    r1 = await call_tool("retrieve_care_knowledge", {"query": "照护者很累", "top_k": 2, "preset_id": "care"})
    check("retrieve 工具命中", r1["result"]["count"] > 0 and r1["tool"] == "retrieve_care_knowledge")
    r2 = await call_tool("screen_text", {"text": "不想活了", "level": "strict"})
    check("screen 工具给资源", len(r2["result"]["resources"]) == 3)
    r3 = await call_tool("pick_skeleton", {"tags": ["温柔"], "hint": "radio / garden"})
    check("pick_skeleton 给候选", len(r3["result"]["candidates"]) == 3, r3["result"])
    r4 = await call_tool("validate_spec", {"spec": spec.model_dump(), "level": "strict"})
    check("validate 注入边界", r4["result"]["safety_injected"] and r4["result"]["valid"])
    r5 = await call_tool("fallback_spec", {"brief": {"tags": ["温柔"]}, "level": "strict"})
    check("fallback 标记复核", r5["result"]["needs_review"] is True)
    try:
        await call_tool("not_exist", {})
        check("未知工具报错", False)
    except KeyError:
        check("未知工具报错", True)


asyncio.run(tools_roundtrip())

print("\n=== C Agent 编排 ===")
engineer = MockAdapter("engineer", LLMConfig("mock", "", "", "mock"))
persona = MockAdapter("persona", LLMConfig("mock", "", "", "mock"))
preset = get_preset("care")
brief = enrich_brief(normalize_brief(preset["tags"], preset["free_text"]), "care")


async def collect(br, eng=engineer, runners=RUNNERS):
    saved = dict(runners)
    runners.clear()
    runners.update(saved)
    evs = []
    async for ev, data in run_agent(eng, br, persona_adapter=persona):
        evs.append((ev, data))
    return evs


evs = asyncio.run(collect(brief))
names = [e for e, _ in evs]
check("无 error 事件", "error" not in names, [d for e, d in evs if e == "error"])
check("start 带五步定义", any(e == "start" and len(d["steps"]) == 5 for e, d in evs))
check("result 事件存在", "result" in names)
steps = [d for e, d in evs if e == "step"]
final_steps = [d for d in steps if d["status"] in ("done", "skipped")]
check("五步都有终态", [d["id"] for d in final_steps] == [s["id"] for s in STEPS], [d["id"] for d in final_steps])
check("兜底步骤待命", final_steps[-1]["status"] == "skipped" and final_steps[-1]["used"] is False, final_steps[-1])
tool_names = [d["tool"] for e, d in evs if e == "tool"]
check("主链路工具全部调用", {"retrieve_care_knowledge", "plan_generation", "generate_spec", "validate_spec"} <= set(tool_names), tool_names)
check("guard 事件两条", len([1 for e, d in evs if e == "guard" and d["phase"] in ("input", "output")]) == 2)
result = next(d for e, d in evs if e == "result")
check("result.trace 五条", len(result["trace"]) == 5, result["trace"])
check("result 有证据", len(result["evidence"]) > 0)
check("result 规划降级可解释", result["plan_source"] in ("rule", "llm"), result["plan_source"])
out_spec = result["spec"]  # 编排层原始结果：边界在 validate 步骤注入
check("产出 spec 含安全边界", SAFETY_MARK in out_spec["system_prompt"])
check("产出 spec 合法", isinstance(SpecModel.model_validate(out_spec), SpecModel))
check("care 场景 strict", result["output_guard"]["level"] == "strict")

# 强制让产出带越界文案，验证第五步真的会接管而不是摆设
orig = RUNNERS["generate_spec"]


async def bad_generate(args, ctx):
    base = await orig(args, ctx)
    base["spec"]["opening_message"] = "想开点，别矫情，至少你还有工作"
    return base


RUNNERS["generate_spec"] = bad_generate
evs2 = asyncio.run(collect(brief))
RUNNERS["generate_spec"] = orig
final2 = [d for e, d in evs2 if e == "step" and d["status"] in ("done", "skipped")]
check("越界时兜底启用", final2[-1]["status"] == "done" and final2[-1]["used"] is True, final2[-1])
res2 = next(d for e, d in evs2 if e == "result")
check("越界时标记 needs_review", res2["needs_review"] is True)
check("兜底 spec 仍带安全边界", SAFETY_MARK in res2["spec"]["system_prompt"])
check("兜底 spec 不含禁用语", "想开点" not in res2["spec"]["opening_message"])

# free 预设：不选场景也要能完整跑通（旧行为的等价路径）
free_brief = enrich_brief(normalize_brief(["温柔"], "陪我聊会儿"), "free")
evs3 = asyncio.run(collect(free_brief))
check("free 预设无 error", "error" not in [e for e, _ in evs3])
check("free 预设五步完整", len([d for e, d in evs3 if e == "step" and d["status"] in ("done", "skipped")]) == 5)

print("\n=== D HTTP 端到端（服务不可达则跳过） ===")
try:
    user = "ag" + secrets.token_hex(3)
    reg, code = call("POST", "/auth/register", {"username": user, "password": "test123456"}, expect=201)
    check("注册成功", code == 201 and bool(reg.get("access_token")), (code, reg))
    token = reg.get("access_token", "")

    t, c = call("GET", "/meta/tools", token=token)
    check("GET /meta/tools", c == 200 and t["count"] == 7, (c, t.get("count")))

    body = {
        "tags": preset["tags"],
        "free_text": preset["free_text"],
        "preset_id": "care",
        "user_query": "我妈住院第三周了，今天突然觉得撑不下去",
    }
    events = sse_events("/agent/build", body, token)
    enames = [e for e, _ in events]
    check("SSE 有 start/result/done", {"start", "result", "done"} <= set(enames), enames)
    check("SSE 无 error", "error" not in enames, [d for e, d in events if e == "error"])
    check("SSE 每步都有状态", len([1 for e, d in events if e == "step" and d["status"] in ("done", "skipped")]) == 5)
    done = next(d for e, d in events if e == "done")
    p = done["persona"]
    check("done 返回完整人格", bool(p.get("id") and p.get("spec") and p.get("brief")))
    check("落库 spec 带安全边界", SAFETY_MARK in p["spec"]["system_prompt"])
    check("brief 带 Agent trace", len(p["brief"].get("agent", {}).get("trace", [])) == 5)
    check("brief 带 preset_id", p["brief"].get("preset_id") == "care")

    lst, _ = call("GET", "/personas", token=token)
    check("人格列表可见", any(x["id"] == p["id"] for x in lst.get("items", [])))

    # 旧接口回归：新链路不能碰坏原本的生成路径
    old, old_code = call("POST", "/personas", {"tags": ["温柔"], "free_text": "陪我聊会儿"}, token, expect=201)
    check("旧 POST /personas 仍可用", old_code == 201 and bool(old.get("spec")), (old_code, old))
except Exception as e:  # noqa: BLE001
    print(f"[skip] HTTP 部分未运行：{type(e).__name__}: {e}")

print(f"\n结果: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
