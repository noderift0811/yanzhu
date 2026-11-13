"""场景预设 + 本地检索知识库验收（A 纯函数，B 提示词兼容，C 可选 HTTP）。

不依赖外部服务与 API Key：MockAdapter 路径必须照样跑通，
否则无密钥的评审机上整条 Agent 链路会直接崩。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 环境里 HTTP_PROXY 会把 127.0.0.1 的探活也劫到代理上，返回 502；
# 本地接口一律走空代理的 opener（与 share_keep.py 同一处理）。
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

from app.llm.base import LLMConfig
from app.llm.mock import MockAdapter
from app.pipeline.brief import normalize_brief
from app.pipeline.engineer_prompt import build_engineer_messages
from app.pipeline.knowledge import (
    build_query,
    format_for_prompt,
    knowledge_stats,
    retrieve,
    retrieve_for_brief,
)
from app.pipeline.presets import (
    DEFAULT_PRESET_ID,
    PRESETS,
    enrich_brief,
    get_preset,
    is_known,
    list_presets,
    validate_presets,
)
from app.pipeline.validate import parse_spec
from app.schemas import SpecModel

BASE = os.environ.get("YANZHU_API", "http://127.0.0.1:8100/api")
passed = failed = 0


def check(label, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"[ok] {label}")
    else:
        failed += 1
        print(f"[FAIL] {label} -> {detail}")


def http_json(path):
    with OPENER.open(BASE + path, timeout=5) as r:
        return json.load(r)


print("=== A 预设表 ===")
errs = validate_presets()
check("启动期自检通过", errs == [], errs)
check("预设数量 3", len(PRESETS) == 3, len(PRESETS))
check("id 唯一", len({p["id"] for p in PRESETS}) == len(PRESETS))
check("默认预设是 free", DEFAULT_PRESET_ID == "free")
check("未知 id 回落 free", get_preset("nope")["id"] == "free")
check("is_known 判定", is_known("care") and is_known(None) and not is_known("nope"))
check("公开视图不泄露检索锚点", all("retrieve_anchors" not in p for p in list_presets()))

raw = {"tags": ["温柔"], "free_text": "听我说会儿", "lang": "zh"}
free_brief = enrich_brief(raw, "free")
check("free 不注入 scene", "scene" not in free_brief)
check("enrich 不改入参", raw == {"tags": ["温柔"], "free_text": "听我说会儿", "lang": "zh"})
care_brief = enrich_brief(raw, "care")
scene = care_brief.get("scene") or {}
check("care 注入 scene", scene.get("preset_id") == "care")
check("scene 含边界与受众", bool(scene.get("constraints")) and bool(scene.get("audience")))
check("scene 含安全级别", scene.get("safety_level") == "strict")

print("\n=== B 标签规则兼容 ===")
for p in PRESETS:
    b = normalize_brief(list(p["tags"]), p["free_text"])
    check(f"{p['id']} 预设标签全保留", b["tags"] == p["tags"], b["tags"])
    check(f"{p['id']} 无 dropped_tags", "dropped_tags" not in b, b.get("dropped_tags"))

print("\n=== C 检索器 ===")
stats = knowledge_stats()
check("知识条目 12", stats["count"] == 12, stats["count"])
check("免责声明存在", bool(stats.get("disclaimer")))
check("检索器标注", "bm25" in stats["retriever"])

h1 = retrieve("照护者每天都在陪床，累到撑不住，还觉得不该喊累")
check("照护者查询有命中", len(h1) > 0)
check("照护者查询 top3 命中照护条目", any(h["id"] == "caregiver-burnout" for h in h1), [h["id"] for h in h1])
h2 = retrieve("别说想开点，也别说我矫情")
check("禁用语查询命中毒性积极", h2 and h2[0]["id"] == "toxic-positivity", [h["id"] for h in h2])
h3 = retrieve("他说不想活了，我该怎么回应")
check("危机查询命中求助资源", any(h["id"] == "crisis-resources" for h in h3), [h["id"] for h in h3])
check("空查询不硬凑", retrieve("") == [] and retrieve("   ") == [])
check("top_k 生效", len(retrieve("情绪 倾听 陪伴 共情", top_k=2)) <= 2)
check("分数降序", all(h1[i]["score"] >= h1[i + 1]["score"] for i in range(len(h1) - 1)))
check("命中带 id/title/text/score", all({"id", "title", "text", "score"} <= set(h) for h in h1))
unrelated = retrieve("量子拓扑绝缘体晶格常数")
check("无关查询分数低于相关查询", (unrelated[0]["score"] if unrelated else 0) < h1[0]["score"],
      (unrelated[0]["score"] if unrelated else 0, h1[0]["score"]))
check("format_for_prompt 不泄露分数", all("score" not in x for x in format_for_prompt(h1)))
check("build_query 带场景锚点", "照护者" in build_query({"tags": [], "free_text": "", "scene": scene}))
check("retrieve_for_brief 可用", len(retrieve_for_brief(care_brief)) > 0)

print("\n=== D 提示词与 Mock 兼容 ===")
brief = normalize_brief(["温柔", "安静", "树洞"], "只安静地听")
brief = enrich_brief(brief, "care")
msgs_plain = build_engineer_messages(brief)
check("基础消息两条", len(msgs_plain) == 2)
plain_content = json.loads(msgs_plain[1]["content"])
check("基础消息含 brief + skeletons", "brief" in plain_content and "skeletons" in plain_content)
check("基础消息不含 context/plan", "retrieved_knowledge" not in plain_content and "plan" not in plain_content)
check("场景边界写进 system", "不做诊断" in msgs_plain[0]["content"])

hits = retrieve_for_brief(brief, top_k=3)
plan = {"tone": "短句、留白", "skeleton_hint": "radio", "steps": ["检索", "规划"]}
msgs_full = build_engineer_messages(brief, context=hits, plan=plan)
full_content = json.loads(msgs_full[1]["content"])
check("带 context 注入证据", len(full_content.get("retrieved_knowledge") or []) == len(hits))
check("证据不含内部分数", all("score" not in h for h in full_content["retrieved_knowledge"]))
check("带 plan 注入决策", full_content.get("plan") == plan)
check("Mock 仍能提取 brief", MockAdapter._extract_brief(msgs_full) == plain_content["brief"])

adapter = MockAdapter("engineer", LLMConfig("mock", "", "", "mock"))


async def mock_roundtrip(messages):
    return await adapter.chat_json(messages)


for label, msgs in (("基础路径", msgs_plain), ("Agent 路径", msgs_full)):
    raw_spec = asyncio.run(mock_roundtrip(msgs))
    try:
        spec = parse_spec(raw_spec)
        check(f"{label} Mock 产出合法 SpecModel", isinstance(spec, SpecModel))
    except Exception as e:  # noqa: BLE001
        check(f"{label} Mock 产出合法 SpecModel", False, f"{type(e).__name__}: {e}")

print("\n=== E HTTP（服务不可达则跳过） ===")
try:
    d = http_json("/meta/presets")
    check("GET /meta/presets", d.get("default") == "free" and len(d.get("items", [])) == 3, d)
    k = http_json("/meta/knowledge?q=%E7%85%A7%E6%8A%A4%E8%80%85%E5%BE%88%E7%B4%AF&top_k=2")
    check("GET /meta/knowledge 带查询", len(k.get("hits", [])) <= 2 and k["stats"]["count"] == 12, k)
except Exception as e:  # noqa: BLE001
    print(f"[skip] HTTP 部分未运行：{type(e).__name__}: {e}")

print(f"\n结果: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
