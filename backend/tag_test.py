"""标签互斥验收：前后端规则必须一致，冲突标签在四条路径上都进不去。

A. 一致性（不联网）：从 tagGroups.js 抽分组与轴，与后端 tag_rules.py 逐项比对
B. 纯函数（不联网）：同轴去重、组配额、总数上限、幂等性
C. HTTP：9 个标签被 schema 挡、真模型生成时 dropped_tags 回传且 keywords 存 kept
"""
import json
import os
import re
import secrets
import sqlite3
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.pipeline.brief import normalize_brief
from app.pipeline.tag_rules import (
    AXES,
    GROUP_QUOTA,
    TAG_GROUPS,
    TENSIONS,
    TOTAL_MAX,
    sanitize_tags,
)

BASE = os.environ.get("YANZHU_API", "http://127.0.0.1:8100/api")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, "frontend", "src", "data", "tagGroups.js")
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "yanzhu.db")
USER = "tg" + secrets.token_hex(3)
PWD = "test123456"
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
    global passed, failed
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=180) as resp:
            payload = json.loads(resp.read().decode() or "{}")
            ok = resp.status == expect
    except urllib.error.HTTPError as e:
        payload = json.loads(e.read().decode() or "{}")
        ok = e.code == expect
    if ok:
        passed += 1
    else:
        failed += 1
        print(f"[FAIL] {method} {path} 期望 {expect} 实际 {payload}")
    return payload


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ============ A. 前后端规则一致性 ============
src = open(JS, encoding="utf-8").read()

# 分组：key: "xxx" ... tags: ["a", "b"]
js_groups = {}
for key, body in re.findall(r'key:\s*"(\w+)",\s*label:\s*"[^"]*",\s*tags:\s*\[([^\]]*)\]', src):
    js_groups[key] = re.findall(r'"([^"]+)"', body)
check("前端解析出 4 个分组", len(js_groups) == 4, list(js_groups))
check("分组标签集合与后端一致", js_groups == {k: v for k, (_, v) in TAG_GROUPS.items()},
      {k: (js_groups.get(k), v) for k, (_, v) in TAG_GROUPS.items() if js_groups.get(k) != v})

# 轴：{ key: "xxx", label: "...", members: [...] }
js_axes = {}
for key, body in re.findall(r'key:\s*"(\w+)",\s*label:\s*"[^"]*",\s*members:\s*\[([^\]]*)\]', src):
    js_axes[key] = re.findall(r'"([^"]+)"', body)
check("前端解析出 4 条互斥轴", len(js_axes) == 4, list(js_axes))
check("互斥轴与后端一致", js_axes == AXES, {k: (js_axes.get(k), v) for k, v in AXES.items() if js_axes.get(k) != v})

# 张力对：{ pair: ["a", "b"], ... }
js_tension = {tuple(re.findall(r'"([^"]+)"', body)) for body in re.findall(r'pair:\s*\[([^\]]*)\]', src)}
check("反差张力对与后端一致", js_tension == set(TENSIONS),
      js_tension ^ set(TENSIONS))

js_total = re.search(r"TOTAL_MAX\s*=\s*(\d+)", src)
check("总上限一致", js_total and int(js_total.group(1)) == TOTAL_MAX, js_total)
js_quota = dict((k, int(v)) for k, v in re.findall(r'(\w+):\s*(\d+)', src.split("GROUP_QUOTA = {")[1].split("}")[0]))
check("组配额一致", js_quota == GROUP_QUOTA, f"js={js_quota} py={GROUP_QUOTA}")

# 每个轴成员都必须是一个真实存在的标签，否则轴永远不生效
all_tags = {t for _, tags in TAG_GROUPS.values() for t in tags}
orphan = [(k, m) for k, members in AXES.items() for m in members if m not in all_tags]
check("轴成员都在标签表内", not orphan, orphan)

# ============ B. 纯函数 ============
b = normalize_brief(["内向", "外向", "活泼", "沉稳", "前辈", "不长篇大论"], "")
check("截图里的那组冲突只剩 4 个", b["tags"] == ["内向", "活泼", "前辈", "不长篇大论"], b["tags"])
check("被丢弃的标签带原因回传", len(b.get("dropped_tags", [])) == 2, b.get("dropped_tags"))
check("丢弃原因指明互斥对象",
      any("内向" in d["reason"] for d in b["dropped_tags"])
      and any("活泼" in d["reason"] for d in b["dropped_tags"]), b["dropped_tags"])

b2 = normalize_brief(["外向", "内向"], "")
check("保留先出现的那个（顺序敏感）", b2["tags"] == ["外向"], b2["tags"])

kept, dropped = sanitize_tags(["活泼", "沉稳", "安静", "冷淡"])
check("能量轴四选一", kept == ["活泼"], kept)

kept, dropped = sanitize_tags(["前辈", "同桌"])
check("关系定位单选", kept == ["前辈"] and dropped[0]["reason"].startswith("「关系定位"), f"{kept} {dropped}")

kept, dropped = sanitize_tags(["内向", "高冷", "毒舌", "温柔", "理性"])
check("性格组最多 3 个", len([k for k in kept if k in dict(TAG_GROUPS)["temperament"][1]]) == 3, kept)

kept, dropped = sanitize_tags(
    ["内向", "高冷", "毒舌", "腼腆", "活泼", "前辈", "不说教", "不玩梗", "不客气", "不主动提问"]
)
check("总数卡在 8", len(kept) == TOTAL_MAX, kept)
check("多出的都记了原因", all(d["reason"] for d in dropped), dropped)

check("同轴不误伤不同组的标签", sanitize_tags(["内向", "理性"])[0] == ["内向", "理性"])
check("自由标签不受配额约束", sanitize_tags(["古板", "档案管理员", "民国", "冷幽默"])[0]
      == ["古板", "档案管理员", "民国", "冷幽默"])

once = sanitize_tags(["内向", "外向", "活泼", "沉稳"])
again = sanitize_tags(once[0])
check("校正幂等（跑两次结果相同）", again[0] == once[0] and not again[1], f"{once[0]} -> {again}")

b3 = normalize_brief(["毒舌", "温柔"], "他嘴上不留情，但只在对方真的做错时才说重话")
check("反差组合不被禁用", b3["tags"] == ["毒舌", "温柔"], b3["tags"])
check("反差组合不产生丢弃记录", "dropped_tags" not in b3, b3)

# 提示词里不该出现审计信息
from app.pipeline.engineer_prompt import build_engineer_messages

msgs = build_engineer_messages({"tags": ["内向"], "free_text": "", "dropped_tags": [{"tag": "外向", "reason": "x"}]})
check("dropped_tags 不进提示词", "dropped_tags" not in msgs[-1]["content"], msgs[-1]["content"][:80])
check("正常 brief 字段还在提示词里", "内向" in msgs[-1]["content"])

# ============ C. HTTP ============
tokens = call("POST", "/auth/register", {"username": USER, "password": PWD}, expect=201)
access = tokens["access_token"]
uid = call("GET", "/auth/me", token=access)["id"]

nine = ["内向", "外向", "高冷", "温柔", "毒舌", "粘人", "理性", "感性", "傲娇"]
call("POST", "/personas", {"tags": nine, "free_text": ""}, token=access, expect=422)

print("... 真模型生成中（约 30 秒）")
created = call(
    "POST",
    "/personas",
    {"tags": ["内向", "外向", "活泼", "沉稳", "前辈", "不长篇大论"], "free_text": ""},
    token=access,
    expect=201,
)
check("冲突标签在生成前已被消解", created["keywords"]["tags"] == ["内向", "活泼", "前辈", "不长篇大论"],
      created["keywords"]["tags"])
check("详情里能查到被丢弃的标签", len(created["brief"].get("dropped_tags", [])) == 2,
      created["brief"].get("dropped_tags"))

conn = sqlite3.connect(DB)
row = conn.execute("SELECT keywords_json, brief_json FROM personas WHERE id=?", (created["id"],)).fetchone()
conn.close()
kw, bf = json.loads(row[0]), json.loads(row[1])
check("落库 keywords 存的是去冲突后的值", kw["tags"] == ["内向", "活泼", "前辈", "不长篇大论"], kw["tags"])
check("落库 brief 保留审计记录", len(bf.get("dropped_tags", [])) == 2, bf.get("dropped_tags"))
check("人格确实生成出来了", bool(created["spec"]["system_prompt"]), created["status"])

print(f"\nRESULT: {passed} passed, {failed} failed")
print(f"[cleanup] user={USER} persona={created['id']}")
sys.exit(1 if failed else 0)
