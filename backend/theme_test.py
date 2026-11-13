"""主题微调接口验收：只改配色、不动骨架与消息、不耗配额、非法值一律拒。"""
import json
import os
import secrets
import sqlite3
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

BASE = os.environ.get("YANZHU_API", "http://127.0.0.1:8100/api")
DB = "data/yanzhu.db"
USER = "th" + secrets.token_hex(3)
PWD = "test123456"
passed = failed = 0


def call(method, path, body=None, token=None, expect=200):
    global passed, failed
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    payload = {}
    try:
        with urllib.request.urlopen(req, data=data) as resp:
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


def check(label, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"[ok] {label}")
    else:
        failed += 1
        print(f"[FAIL] {label} {detail}")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def quota_used(token):
    return call("GET", "/auth/me", token=token).get("quota", {})


def llm_count():
    conn = sqlite3.connect(DB)
    n = conn.execute("SELECT COUNT(*) FROM llm_calls").fetchone()[0]
    conn.close()
    return n


# ---------- 1. 干净用户 + 直接落一条深色骨架人格 ----------
tokens = call("POST", "/auth/register", {"username": USER, "password": PWD}, expect=201)
access = tokens["access_token"]
uid = call("GET", "/auth/me", token=access)["id"]

pid = str(uuid.uuid4())
cid = str(uuid.uuid4())
mid = str(uuid.uuid4())
spec = {
    "name": "霓虹测试",
    "system_prompt": "你说话简短，带点夜场口气。" * 3,
    "skeleton_id": "neon",
    "theme": {
        "primary": "#ff2d95", "bg": "#0a0a10", "surface": "#16101e",
        "text": "#f4eeff", "accent": "#22d3ee",
        "font_style": "mono", "decoration": "grid",
    },
    "page_copy": {"title": "夜街", "greeting": "来了。", "input_placeholder": "敲一下门…"},
    "opening_message": "门开着，进来吧。",
    "needs_review": False,
    "warnings": [],
}
conn = sqlite3.connect(DB)
conn.execute(
    "INSERT INTO personas (id,user_id,name,keywords_json,brief_json,skeleton_id,theme_json,spec_json,status,created_at,updated_at)"
    " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
    (pid, uid, "霓虹测试",
     json.dumps({"tags": ["夜场", "冷淡"], "free_text": "说话短"}, ensure_ascii=False),
     json.dumps({}, ensure_ascii=False),
     "neon", json.dumps(spec["theme"], ensure_ascii=False),
     json.dumps(spec, ensure_ascii=False), "active", now(), now()),
)
conn.execute(
    "INSERT INTO conversations (id,persona_id,user_id,title,created_at,updated_at) VALUES (?,?,?,?,?,?)",
    (cid, pid, uid, "会话一", now(), now()),
)
conn.execute(
    "INSERT INTO messages (conversation_id,role,content,created_at) VALUES (?,?,?,?)",
    (cid, "assistant", "门开着，进来吧。", now()),
)
conn.commit()
conn.close()
check("测试人格已落库", True)

# ---------- 2. meta 目录带上默认主题与输入框文案 ----------
meta = call("GET", "/meta/skeletons")
items = meta.get("items", [])
check("meta 返回 16 套", len(items) == 16, len(items))
check("每套都带 theme", all(isinstance(i.get("theme"), dict) for i in items))
check("每套都带 placeholder", all(isinstance(i.get("placeholder"), str) for i in items))
neon_meta = next((i for i in items if i["id"] == "neon"), {})
check("neon 默认主色为 #ff2d95", neon_meta.get("theme", {}).get("primary") == "#ff2d95")

# ---------- 3. 只改主题：骨架、消息、状态都不动，零 LLM 调用 ----------
before_llm = llm_count()
before_quota = quota_used(access)
new_theme = {
    "primary": "#4f46e5", "bg": "#f7f7f8", "surface": "#ffffff",
    "text": "#1f2328", "accent": "#7c6cf0",
    "font_style": "serif", "decoration": "paper",
}
detail = call("PATCH", f"/personas/{pid}", {"theme": new_theme}, token=access)
check("PATCH 成功", detail.get("id") == pid)
check("spec.theme.primary 已更新", detail["spec"]["theme"]["primary"] == "#4f46e5")
check("spec.theme.font_style 已更新", detail["spec"]["theme"]["font_style"] == "serif")
check("spec.theme.decoration 已更新", detail["spec"]["theme"]["decoration"] == "paper")
check("skeleton_id 未被动过", detail["spec"]["skeleton_id"] == "neon")
check("summary 的 theme 同步", detail["theme"]["bg"] == "#f7f7f8")
check("人设 system_prompt 未动", detail["spec"]["system_prompt"] == spec["system_prompt"])
check("开场白未动", detail["spec"]["opening_message"] == spec["opening_message"])
check("页面文案未动", detail["spec"]["page_copy"]["title"] == "夜街")
check("零 LLM 调用", llm_count() == before_llm)
check("配额零消耗", quota_used(access) == before_quota, (before_quota, quota_used(access)))
msgs = call("GET", f"/conversations/{cid}/messages", token=access)
check("消息未受影响", len(msgs.get("items", [])) == 1)

# ---------- 4. 数据库层面主题已落盘 ----------
conn = sqlite3.connect(DB)
row = conn.execute("SELECT theme_json, spec_json, skeleton_id FROM personas WHERE id=?", (pid,)).fetchone()
conn.close()
check("theme_json 已落盘", json.loads(row[0])["primary"] == "#4f46e5")
check("spec_json 里的主题已同步", json.loads(row[1])["theme"]["accent"] == "#7c6cf0")
check("库里的 skeleton_id 仍是 neon", row[2] == "neon")

# ---------- 5. 非法输入一律 422 ----------
bad_colors = ["#GGGGGG", "red", "#12345", "#1234567", "", "rgb(1,2,3)"]
for c in bad_colors:
    t = dict(new_theme, primary=c)
    call("PATCH", f"/personas/{pid}", {"theme": t}, token=access, expect=422)
check("非法色值全部 422", True)

for field, bad in [("font_style", "handwriting"), ("decoration", "confetti"), ("font_style", "")]:
    t = dict(new_theme)
    t[field] = bad
    call("PATCH", f"/personas/{pid}", {"theme": t}, token=access, expect=422)
check("非法字体/装饰全部 422", True)

call("PATCH", f"/personas/{pid}", {"theme": {"primary": "#ffffff"}}, token=access, expect=422)
check("缺字段的主题被拒", True)

# 全大写十六进制应被规范化成小写
d = call("PATCH", f"/personas/{pid}", {"theme": dict(new_theme, primary="#AABBCC")}, token=access)
check("十六进制规范化为小写", d["spec"]["theme"]["primary"] == "#aabbcc")

# ---------- 6. 改名不影响配色 ----------
d = call("PATCH", f"/personas/{pid}", {"name": "改个名"}, token=access)
check("改名成功", d["name"] == "改个名")
check("改名后配色未变", d["spec"]["theme"]["primary"] == "#aabbcc")

# ---------- 7. 换骨架仍会成套换装（不被旧主题卡住） ----------
d = call("PATCH", f"/personas/{pid}", {"skeleton_id": "diary"}, token=access)
check("换骨架后 skeleton_id 生效", d["spec"]["skeleton_id"] == "diary")
check("换骨架后套用日记预设底色", d["spec"]["theme"]["bg"] == "#faf6ee")

# ---------- 8. 他人人格一律 404 ----------
tokens2 = call("POST", "/auth/register", {"username": USER + "b", "password": PWD}, expect=201)
other = tokens2["access_token"]
call("PATCH", f"/personas/{pid}", {"theme": new_theme}, token=other, expect=404)
check("他人人格改配色 404", True)

# ---------- 9. 未登录 401 ----------
call("PATCH", f"/personas/{pid}", {"theme": new_theme}, expect=401)
check("未登录 401", True)

print(f"\n通过 {passed} / 失败 {failed}")
sys.exit(1 if failed else 0)
