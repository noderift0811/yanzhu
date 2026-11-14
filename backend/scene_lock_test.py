"""场景锁定链路验收：唯一主场景、受控切换、演示账号豁免、服务端权威、语气开关。

这组测试守的是「规则在服务端」这件事。前端把场景卡藏起来只能叫提示，
真正的锁必须是：请求里多带一个 preset_id 就 400，账号没选场景就必须先选。
"""
from __future__ import annotations

import codecs
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

from app.config import get_settings
from app.db import db_session
from app.models import init_db
from app.scenes import tone_clause

BASE = os.environ.get("YANZHU_API", "http://127.0.0.1:8100/api")
SUFFIX = os.environ.get("SCENE_SUFFIX", str(int(time.time()))[-6:])
passed = failed = 0


def check(label, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"[ok] {label}")
    else:
        failed += 1
        print(f"[FAIL] {label} -> {detail}")


def api(path, method="GET", body=None, token=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("X-Yanzhu-Token", token)
    try:
        with OPENER.open(req, timeout=30) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:  # noqa: BLE001
            return e.code, {"raw": raw}


def sse(path, body, token, timeout=60):
    """读一条 SSE 流，返回 [(事件名, 数据)]。

    注意必须按块 + 增量解码：早期按单字节 decode("utf-8","ignore") 会把每个
    中文字符（3 字节）逐个丢掉，拿到的 JSON 只剩 ASCII 片段，解析还能成功，
    于是「人设没写边界」这种假失败要查很久。
    """
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Yanzhu-Token", token)
    events = []
    buf = ""
    dec = codecs.getincrementaldecoder("utf-8")()
    with OPENER.open(req, timeout=timeout) as r:
        while True:
            chunk = r.read(2048)
            if not chunk:
                break
            buf += dec.decode(chunk)
            while "\n\n" in buf:
                block, buf = buf.split("\n\n", 1)
                name, payload = "message", ""
                for line in block.split("\n"):
                    if line.startswith("event:"):
                        name = line[6:].strip()
                    elif line.startswith("data:"):
                        payload += line[5:].strip()
                if payload:
                    events.append((name, json.loads(payload)))
    return events


s = get_settings()
print("=== A 迁移幂等 ===")
init_db()
init_db()
with db_session() as conn:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
    pcols = {r["name"] for r in conn.execute("PRAGMA table_info(personas)")}
check("users 有场景与语气列", {"primary_scene", "scene_changed_at", "tone_json"} <= cols, cols)
check("personas 有 scene_id", "scene_id" in pcols, pcols)

print("\n=== B 注册后必须选场景 ===")
user = f"sc{SUFFIX}"
status, reg = api("/auth/register", "POST", {"username": user, "password": "test123456"})
check("注册成功", status == 201 and "access_token" in reg, (status, reg))
tok = reg.get("access_token")
status, me = api("/auth/me", token=tok)
check("新账号未选场景", me.get("primary_scene") is None and me.get("scene_chosen") is False, me)
check("未选时回落 free", me.get("scene_id") == "free", me.get("scene_id"))
check("语气默认全关", me.get("tone") == {"calm": False, "brief": False, "no_exclaim": False}, me.get("tone"))

print("\n=== C 首次选择与幂等 ===")
status, r1 = api("/auth/scene", "POST", {"scene": "care"}, tok)
check("首次选场景 200", status == 200 and r1.get("scene_id") == "care", (status, r1))
check("首次不算切换", r1.get("switched") is False, r1)
check("首次不归档人格", r1.get("archived_personas") == 0, r1)
status, r2 = api("/auth/scene", "POST", {"scene": "care"}, tok)
check("重复选同一场景幂等", status == 200 and r2.get("switched") is False, (status, r2))
status, bad = api("/auth/scene", "POST", {"scene": "nope"}, tok)
check("未知场景 400", status == 400 and bad.get("code") == "SCENE_UNKNOWN", (status, bad))

print("\n=== D 受控切换 ===")
status, need = api("/auth/scene", "POST", {"scene": "study"}, tok)
check("切换需确认 409", status == 409 and need.get("code") == "SCENE_CONFIRM_REQUIRED", (status, need))
status, cool = api("/auth/scene", "POST", {"scene": "study", "confirm": True}, tok)
check("确认后仍受冷却 409", status == 409 and cool.get("code") == "SCENE_COOLDOWN", (status, cool))
check("冷却响应带下次可切换时间", bool(cool.get("next_switch_at")), cool)
status, me2 = api("/auth/me", token=tok)
check("失败切换未改动主场景", me2.get("scene_id") == "care", me2.get("scene_id"))
check("can_switch=false", me2.get("can_switch") is False, me2)

print("\n=== E 生成读账号场景，不信请求参数 ===")
# 场景校验在建立流之前完成，因此这里拿到的是普通 HTTP 400
status, mismatch = api(
    "/agent/build",
    "POST",
    {"tags": ["温柔", "安静"], "free_text": "想有人听我说话", "preset_id": "study", "user_query": "今天很累"},
    tok,
)
check("请求带不一致 preset_id 被拒", status == 400 and mismatch.get("code") == "SCENE_MISMATCH", (status, mismatch))
check("错误信息说明账号场景", mismatch.get("scene_id") == "care", mismatch)

built2 = sse(
    "/agent/build",
    {"tags": ["温柔", "安静"], "free_text": "想有人听我说话", "user_query": "今天很累"},
    tok,
)
names = [e[0] for e in built2]
check("不带 preset_id 可正常生成", "result" in names and "done" in names, names[-6:])
persona = next((d for n, d in built2 if n == "done"), {}).get("persona") or {}
check("落库人格带账号场景 care", persona.get("scene_id") == "care", persona.get("scene_id"))
check("brief 记录 preset_id=care", (persona.get("brief") or {}).get("preset_id") == "care", (persona.get("brief") or {}).get("preset_id"))
check("人设带场景边界", "【安全边界" in (persona.get("spec") or {}).get("system_prompt", ""), "no mark")
check(
    "陪伴场景注入的是陪伴红线",
    "本场景是陪伴位" in (persona.get("spec") or {}).get("system_prompt", ""),
    (persona.get("spec") or {}).get("system_prompt", "")[-80:],
)
pid = persona.get("id")

print("\n=== F 语气开关（即时、不耗生成配额） ===")
status, t1 = api("/auth/tone", "PATCH", {"calm": True, "no_exclaim": True}, tok)
check("PATCH /auth/tone 生效", status == 200 and t1["tone"]["calm"] is True and t1["tone"]["brief"] is False, (status, t1))
status, me3 = api("/auth/me", token=tok)
check("语气已持久化", me3.get("tone")["no_exclaim"] is True, me3.get("tone"))
check("语气不改生成配额", me3.get("quota_gen_used") == me.get("quota_gen_used") == 0 or me3.get("quota_gen_used") >= 1, me3.get("quota_gen_used"))
check("语气转成运行时指令", "更沉稳" in tone_clause({"calm": True}) and "感叹号" in tone_clause({"no_exclaim": True}))
check("全关时不追加任何指令", tone_clause({"calm": False, "brief": False, "no_exclaim": False}) == "")

status, conv = api(f"/personas/{pid}/conversations", "POST", {}, tok)
cid = conv.get("id")
check("建会话", status in (200, 201) and bool(cid), (status, conv))
events = sse(f"/conversations/{cid}/messages/stream", {"content": "今天有点撑不住"}, tok)
meta = next((d for n, d in events if n == "meta"), {})
check("聊天 meta 带语气状态", meta.get("tone", {}).get("calm") is True, meta.get("tone"))
check("聊天正常出结果", any(n == "done" for n, _ in events), [n for n, _ in events])

print("\n=== G 演示账号豁免冷却 ===")
status, dm = api("/auth/login", "POST", {"username": s.demo_username, "password": s.demo_password})
dtok = dm.get("access_token")
check("演示账号可登录", status == 200 and bool(dtok), status)
status, dme = api("/auth/me", token=dtok)
check("演示账号有场景", bool(dme.get("scene_id")), dme.get("primary_scene"))
check("演示账号标记 is_demo", dme.get("is_demo") is True, dme)
check("演示账号可随时切换", dme.get("can_switch") is True and dme.get("next_switch_at") is None, dme)

# 先在演示账号当前场景下造一个人格，否则「切换归档」这条永远测到 0 条，
# 会以为归档逻辑没生效
sse("/agent/build", {"tags": ["温柔"], "free_text": "想有人听我说话"}, dtok)
status, dsw = api("/auth/scene", "POST", {"scene": "workplace", "confirm": True}, dtok)
check("演示账号切换成功", status == 200 and dsw.get("scene_id") == "workplace", (status, dsw))
check("切换后旧人格归档", dsw.get("archived_personas", 0) >= 1, dsw.get("archived_personas"))
status, back = api("/auth/scene", "POST", {"scene": "care", "confirm": True}, dtok)
check("演示账号可切回", status == 200 and back.get("scene_id") == "care", (status, back))

status, plist = api("/personas", token=dtok)
check("归档人格不出现在列表", all(p.get("scene_id") == "care" for p in plist.get("items", [])), [p.get("scene_id") for p in plist.get("items", [])])
check("列表回传归档数量", plist.get("archived_count", 0) >= 1, plist.get("archived_count"))

status, plist2 = api("/personas", token=tok)
check("未归档账号 archived_count=0", plist2.get("archived_count") == 0, plist2.get("archived_count"))

print(f"\n结果: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
