"""换骨架接口验收：不调 LLM、不耗配额、深浅主题成套换装。"""
import json
import os
import secrets
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

BASE = os.environ.get("YANZHU_API", "http://127.0.0.1:8100/api")
DB = "data/yanzhu.db"
USER = "sw" + secrets.token_hex(3)
PWD = "test123456"
passed = failed = 0


def call(method, path, body=None, token=None, expect=200):
    global passed, failed
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
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
    else:
        failed += 1
        print(f"[FAIL] {label} {detail}")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------- 1. 一个干净用户 ----------
tokens = call("POST", "/auth/register", {"username": USER, "password": PWD}, expect=201)
access = tokens["access_token"]
uid = call("GET", "/auth/me", token=access)["id"]

# ---------- 2. 直接落一条 minimal 人格，跳过 30 秒生成 ----------
pid = str(uuid.uuid4())
base_spec = {
    "name": "苏桃",
    "system_prompt": "你是苏桃，一个内向的笔友，说话很慢，句子短，句末常带省略号。" * 3,
    "skeleton_id": "minimal",
    "theme": {
        "primary": "#4f46e5", "bg": "#f7f7f8", "surface": "#ffffff",
        "text": "#1f2328", "accent": "#7c6cf0",
        "font_style": "system", "decoration": "none",
    },
    "page_copy": {"title": "苏桃的信箱", "greeting": "你来啦", "input_placeholder": "说点什么吧…"},
    "opening_message": "你来啦……我今天写了一点点东西，你要看吗。",
}
conn = sqlite3.connect(DB)
ts = now()
conn.execute(
    "INSERT INTO personas (id,user_id,name,keywords_json,brief_json,spec_json,skeleton_id,"
    "theme_json,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
    (
        pid, uid, "苏桃", json.dumps({"tags": ["内向"], "free_text": ""}), json.dumps({}),
        json.dumps(base_spec, ensure_ascii=False), "minimal",
        json.dumps(base_spec["theme"]), "active", ts, ts,
    ),
)
conn.commit()
calls_before = conn.execute("SELECT COUNT(*) FROM llm_calls WHERE user_id=?", (uid,)).fetchone()[0]
quota_before = conn.execute("SELECT quota_gen_used FROM users WHERE id=?", (uid,)).fetchone()[0]
conn.close()

# ---------- 3. 浅色 minimal → 深色 neon ----------
r = call("PATCH", f"/personas/{pid}", {"skeleton_id": "neon"}, token=access)
check("骨架 id 已切换", r["skeleton_id"] == "neon", r["skeleton_id"])
check("骨架展示名正确", r["skeleton_name"] == "霓虹街", r.get("skeleton_name"))
check("顶层 theme 换成霓虹配色", r["theme"]["primary"] == "#ff2d95", r["theme"]["primary"])
check("spec.theme 同步", r["spec"]["theme"]["primary"] == "#ff2d95")
check("spec.skeleton_id 同步", r["spec"]["skeleton_id"] == "neon")
check("深底配浅字", r["theme"]["text"] == "#efeaff", r["theme"]["text"])
check("输入框文案随骨架替换", r["spec"]["page_copy"]["input_placeholder"] == "敲一下门…",
      r["spec"]["page_copy"]["input_placeholder"])
check("页面标题与开场白保留", r["spec"]["page_copy"]["title"] == "苏桃的信箱"
      and r["spec"]["opening_message"].startswith("你来啦"))
check("人设未被动过", r["spec"]["system_prompt"] == base_spec["system_prompt"])
check("名字未被改", r["name"] == "苏桃")
check("updated_at 已刷新", r["updated_at"] >= ts)

# ---------- 4. 非法 id 必须被拒 ----------
for bad in ("nope", "", "Neon", "neon "):
    call("PATCH", f"/personas/{pid}", {"skeleton_id": bad}, token=access, expect=422)

# 拒绝后人格不应被改动
r = call("GET", f"/personas/{pid}", token=access)
check("非法请求未污染数据", r["skeleton_id"] == "neon")

# ---------- 5. 显式 theme 优先于预设 ----------
custom = {
    "primary": "#123456", "bg": "#0a0a0a", "surface": "#101010",
    "text": "#fafafa", "accent": "#abcdef", "font_style": "serif", "decoration": "none",
}
r = call("PATCH", f"/personas/{pid}", {"skeleton_id": "oracle", "theme": custom}, token=access)
check("骨架已换到 oracle", r["skeleton_id"] == "oracle")
check("显式配色优先于预设", r["theme"]["primary"] == "#123456", r["theme"]["primary"])
check("显式字体优先于预设", r["theme"]["font_style"] == "serif")
check("显式配色时不动文案", r["spec"]["page_copy"]["input_placeholder"] == "敲一下门…")

# ---------- 6. 只改名仍然可用（回归） ----------
r = call("PATCH", f"/personas/{pid}", {"name": "苏小桃"}, token=access)
check("改名生效", r["name"] == "苏小桃")
check("改名不影响骨架", r["skeleton_id"] == "oracle" and r["spec"]["skeleton_id"] == "oracle")

# ---------- 7. 不调 LLM、不耗配额 ----------
conn = sqlite3.connect(DB)
calls_after = conn.execute("SELECT COUNT(*) FROM llm_calls WHERE user_id=?", (uid,)).fetchone()[0]
quota_after = conn.execute("SELECT quota_gen_used FROM users WHERE id=?", (uid,)).fetchone()[0]
conn.close()
check("全程零 LLM 调用", calls_after == calls_before, f"{calls_before} -> {calls_after}")
check("生成配额未被消耗", quota_after == quota_before, f"{quota_before} -> {quota_after}")

# ---------- 8. 别人的人格一律 404 ----------
other = call("POST", "/auth/register", {"username": "sw2" + secrets.token_hex(3), "password": PWD},
             expect=201)
call("PATCH", f"/personas/{pid}", {"skeleton_id": "bbs"}, token=other["access_token"], expect=404)

print(f"\n通过 {passed} / 失败 {failed}")
sys.exit(1 if failed else 0)
