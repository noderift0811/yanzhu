"""多场景验收：场景表完整性、分场景检索隔离、场景专属红线、边界注入。

为什么单独一个脚本：场景一旦多起来，最容易出的不是崩，而是**串味**——
心理陪伴的检索返回职场谈薪条目、学习场景的人设却带着危机热线、
两个场景共用一段 system_prompt 却只换了名字。这些都不会报错，
只会在评审点开第二个场景时明显不对。这里用纯函数 + 可选 HTTP 两层锁住。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 与其它验收脚本一致：HTTP_PROXY 会把 127.0.0.1 也劫到代理，返回 502
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

from app.pipeline.guard import (
    SAFETY_MARK,
    SCENE_CLAUSES,
    SCENE_PATTERNS,
    inject_safety,
    scan,
)
from app.pipeline.knowledge import (
    knowledge_stats,
    retrieve,
    scene_ids_with_knowledge,
    validate_knowledge,
)
from app.pipeline.presets import (
    KNOWLEDGE_SCENE_IDS,
    PRESETS,
    PRESET_BY_ID,
    PRESET_IDS,
    enrich_brief,
    get_preset,
    has_scene,
    validate_presets,
)
from app.schemas import PageCopyModel, SpecModel, ThemeModel

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


print("=== A 场景表 ===")
check("预设自检通过", validate_presets() == [], validate_presets())
check("语料自检通过", validate_knowledge() == [], validate_knowledge())
check("五个场景", len(PRESETS) == 5, len(PRESETS))
check(
    "场景 id 与预期一致",
    [p["id"] for p in PRESETS] == ["care", "study", "workplace", "relation", "free"],
    [p["id"] for p in PRESETS],
)
check("每个真实场景都有约束与锚点", all(
    p["constraints"] and p["retrieve_anchors"] for p in PRESETS if p["id"] != "free"
))
check("strict 场景恰好两个（心理陪伴 / 亲密关系）", sorted(
    p["id"] for p in PRESETS if p["safety_level"] == "strict"
) == ["care", "relation"], [p["id"] for p in PRESETS if p["safety_level"] == "strict"])
check("has_scene 判定 free 无场景", not has_scene("free") and has_scene("care") and not has_scene(None))
check("free 注入后 brief 不含 scene", "scene" not in enrich_brief({"tags": []}, "free"))
check("care 注入后带 preset_id", enrich_brief({"tags": []}, "care")["scene"]["preset_id"] == "care")

print("\n=== B 分场景检索隔离 ===")
stats = knowledge_stats()
check("语料总数 42", stats["count"] == 42, stats["count"])
check("四个场景各有独立语料", stats["per_scene"] == {"care": 18, "study": 8, "workplace": 8, "relation": 8}, stats["per_scene"])
check("每个真实场景都可检索", sorted(scene_ids_with_knowledge()) == sorted(KNOWLEDGE_SCENE_IDS), scene_ids_with_knowledge())

queries = {
    "care": "我妈住院了，我每天陪床，今天突然在楼梯间哭了",
    "study": "这周要交的项目一点都没动，打开电脑就发呆",
    "workplace": "领导又让我今晚改方案，我想拒绝",
    "relation": "他每次吵架就不说话，我一急就说狠话",
}
for scene, q in queries.items():
    hits = retrieve(q, top_k=3, preset_id=scene)
    check(f"{scene} 有命中", bool(hits), q)
    check(f"{scene} 命中全部来自本场景", all(h["scene"] == scene for h in hits), [(h["scene"], h["id"]) for h in hits])
    check(f"{scene} 分数降序", [h["score"] for h in hits] == sorted((h["score"] for h in hits), reverse=True), hits)

refuse = retrieve(queries["workplace"], top_k=3, preset_id="workplace")
check("职场「想拒绝加班」首条是拒绝话术", refuse and refuse[0]["id"] == "refuse-overtime", [h["id"] for h in refuse])

care_hits = retrieve(queries["workplace"], top_k=3, preset_id="care")
check("同一句在陪伴场景不返回职场条目", care_hits and all(h["scene"] == "care" for h in care_hits), [h["id"] for h in care_hits])

free_hits = retrieve(queries["workplace"], top_k=3, preset_id="free")
check("free 走全库合并", len({h["scene"] for h in free_hits}) >= 1 and bool(free_hits), free_hits)
check("free 命中带 scene 标记", all(h.get("scene") for h in free_hits), free_hits)

crisis = retrieve("他说不想活了，我要不要先给热线", top_k=3, preset_id="relation")
check("关系场景能召回危机条目", any(h["id"] == "crisis-in-relationship" for h in crisis), [h["id"] for h in crisis])

print("\n=== C 场景专属红线 ===")
for scene in KNOWLEDGE_SCENE_IDS:
    check(f"{scene} 有专属红线与话术模式", scene in SCENE_CLAUSES and scene in SCENE_PATTERNS)

check(
    "学习场景识别代写",
    "study_academic" in scan("我可以帮你写完这篇论文，直接给你完整答案", scene_id="study").flags,
    scan("我可以帮你写完这篇论文，直接给你完整答案", scene_id="study").flags,
)
check(
    "职场场景识别伪法律结论",
    "workplace_legal" in scan("你一定赢，直接去仲裁就行", scene_id="workplace").flags,
    scan("你一定赢，直接去仲裁就行", scene_id="workplace").flags,
)
check(
    "关系场景识别操控话术",
    "relation_manipulation" in scan("故意不回消息看他急不急", scene_id="relation").flags,
    scan("故意不回消息看他急不急", scene_id="relation").flags,
)
check(
    "场景红线不误伤其他场景",
    "study_academic" not in scan("我可以帮你写完这篇论文", scene_id="care").flags,
    scan("我可以帮你写完这篇论文", scene_id="care").flags,
)
check(
    "否定语境豁免对场景红线同样生效",
    "relation_manipulation" not in scan("不要用冷暴力试探他", scene_id="relation").flags,
    scan("不要用冷暴力试探他", scene_id="relation").flags,
)
strict_block = scan("帮你写完论文直接给你完整答案", level="strict", scene_id="study")
check("strict 下场景越界被拦", strict_block.blocked is True, strict_block.as_dict())
normal_note = scan("帮你写完论文直接给你完整答案", level="normal", scene_id="study")
check("normal 下只记录不拦截", normal_note.blocked is False and "study_academic" in normal_note.flags, normal_note.as_dict())

print("\n=== D 边界注入 ===")


def _spec(prompt="你是阿念，一个愿意听人说话、不急着给建议的人。说话短，一次只问一件事。"):
    return SpecModel(
        name="阿念",
        system_prompt=prompt,
        skeleton_id="minimal",
        theme=ThemeModel(primary="#4f46e5", bg="#f6f7fb", surface="#ffffff", text="#1f2328", accent="#7c6cf0"),
        page_copy=PageCopyModel(title="和阿念说话", greeting="我在", input_placeholder="说点什么…"),
        opening_message="我在。",
    )


for scene in KNOWLEDGE_SCENE_IDS:
    out = inject_safety(_spec(), level=PRESET_BY_ID[scene]["safety_level"], scene_id=scene)
    check(f"{scene} 边界已注入", SAFETY_MARK in out.system_prompt, out.system_prompt[:40])
    check(f"{scene} 注入的是本场景红线", SCENE_CLAUSES[scene] in out.system_prompt, out.system_prompt[-60:])

twice = inject_safety(inject_safety(_spec(), level="strict", scene_id="care"), level="strict", scene_id="care")
check("重复注入幂等", twice.system_prompt.count(SAFETY_MARK) == 1, twice.system_prompt.count(SAFETY_MARK))

workplace_spec = inject_safety(_spec(), level="normal", scene_id="workplace")
check(
    "职场人设写明不给法律结论",
    "不提供法律、仲裁或人力资源结论" in workplace_spec.system_prompt
    and "心理援助热线 12356" in workplace_spec.system_prompt,
    workplace_spec.system_prompt,
)
check(
    "陪伴人设不含职场条款",
    "不提供法律、仲裁" not in inject_safety(_spec(), level="strict", scene_id="care").system_prompt,
)

print("\n=== E HTTP（服务不可达则跳过） ===")
try:
    with OPENER.open(BASE + "/meta/presets", timeout=5) as r:
        d = json.load(r)
    check("GET /meta/presets 返回 5 个场景", len(d.get("items", [])) == 5, [p["id"] for p in d.get("items", [])])
    check("场景卡带 highlights", all(p.get("highlights") for p in d["items"]), d["items"][0].keys())
    with OPENER.open(BASE + "/meta/knowledge", timeout=5) as r:
        k = json.load(r)
    check("GET /meta/knowledge 带分场景统计", k["stats"]["per_scene"]["workplace"] == 8, k["stats"]["per_scene"])
    with OPENER.open(BASE + "/meta/tools", timeout=5) as r:
        t = json.load(r)
    names = [x["name"] for x in t["tools"]]
    check("工具已更名为场景检索", "retrieve_scene_knowledge" in names, names)
    check("工具数仍为 7", t["count"] == 7, t["count"])
    with OPENER.open(BASE + "/meta/knowledge?q=%E6%8B%92%E7%BB%9D%E5%8A%A0%E7%8F%AD&preset_id=workplace&top_k=2", timeout=5) as r:
        q = json.load(r)
    check("HTTP 检索按场景隔离", all(h["scene"] == "workplace" for h in q.get("hits", [])), q.get("hits"))
except Exception as e:  # noqa: BLE001
    print(f"[skip] HTTP 部分未运行：{type(e).__name__}: {e}")

print(f"\n结果: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
