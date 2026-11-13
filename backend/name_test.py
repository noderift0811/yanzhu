"""角色命名验收：用户指定的名字必须被原样使用，改名要连人设提示词一起改。

三段：
A. 纯函数（不联网）：brief 归一化、强制改名兜底
B. HTTP 改名：直插一条人格→PATCH 改名→校验 spec.name 与 system_prompt
C. HTTP 生成：真模型生成时带 name，验证落库名字与用户输入一致（约 30 秒，仅一次）
"""
import json
import os
import secrets
import sqlite3
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.pipeline.brief import normalize_brief
from app.pipeline.engineer_prompt import build_engineer_messages
from app.routers.personas import _apply_forced_name
from app.schemas import SpecModel

BASE = os.environ.get("YANZHU_API", "http://127.0.0.1:8100/api")
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "yanzhu.db")
USER = "nm" + secrets.token_hex(3)
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


# ============ A. 纯函数 ============
b = normalize_brief(["毒舌"], "口癖：反问", "  沈砚 ")
check("brief 保留用户名字并去空白", b.get("name") == "沈砚", b)

b2 = normalize_brief(["毒舌"], "", None)
check("没给名字时 brief 不带 name 键", "name" not in b2, b2)

b3 = normalize_brief([], "", "一" * 30)
check("超长名字截断到 20 字", len(b3["name"]) == 20, b3.get("name"))

msgs = build_engineer_messages({"tags": ["毒舌"], "free_text": "", "name": "沈砚"})
check("提示词里能读到用户指定的名字", "沈砚" in msgs[-1]["content"], "brief 未进入 prompt")

fake = SpecModel(
    name="陆沉",
    system_prompt="你是陆沉，一个不爱说话的档案管理员。" + "你说话极简。" * 6,
    skeleton_id="casefile",
    theme={
        "primary": "#8a6a3b", "bg": "#f3ead8", "surface": "#fffaf0",
        "text": "#2c2417", "accent": "#a8792f", "font_style": "serif", "decoration": "paper",
    },
    page_copy={"title": "卷宗", "greeting": "又见面了。", "input_placeholder": "写点什么"},
    opening_message="进来吧，门没锁。",
)
forced = _apply_forced_name(fake, "沈砚")
check("模型自作主张的名字被强制覆盖", forced.name == "沈砚", forced.name)
check("system_prompt 同步改名，不留旧名", "陆沉" not in forced.system_prompt and "沈砚" in forced.system_prompt, forced.system_prompt[:40])
check("原有性格描述没被冲掉", "档案管理员" in forced.system_prompt, forced.system_prompt[:60])

# ============ B. 改名接口 ============
tokens = call("POST", "/auth/register", {"username": USER, "password": PWD}, expect=201)
access = tokens["access_token"]
uid = call("GET", "/auth/me", token=access)["id"]

pid = str(uuid.uuid4())
spec = {
    "name": "苏桃",
    "system_prompt": "你是苏桃，一个写日记的女生。" + "你说话很轻。" * 8,
    "skeleton_id": "minimal",
    "theme": {
        "primary": "#4f46e5", "bg": "#f7f7f8", "surface": "#ffffff",
        "text": "#1f2328", "accent": "#7c6cf0", "font_style": "system", "decoration": "none",
    },
    "page_copy": {"title": "苏桃的对话框", "greeting": "你来了。", "input_placeholder": "说点什么…"},
    "opening_message": "今天也写了一点东西。",
}
now = utcnow()
conn = sqlite3.connect(DB)
conn.execute(
    "INSERT INTO personas (id, user_id, name, keywords_json, brief_json, spec_json,"
    " skeleton_id, theme_json, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
    (
        pid, uid, "苏桃",
        json.dumps({"tags": ["内向"], "free_text": ""}, ensure_ascii=False),
        json.dumps({"tags": ["内向"], "free_text": "", "lang": "zh"}, ensure_ascii=False),
        json.dumps(spec, ensure_ascii=False),
        "minimal", json.dumps(spec["theme"], ensure_ascii=False), "active", now, now,
    ),
)
conn.commit()
conn.close()

detail = call("GET", f"/personas/{pid}", token=access)
check("改名之前 spec.name 是苏桃", detail["spec"]["name"] == "苏桃", detail["spec"]["name"])

patched = call("PATCH", f"/personas/{pid}", {"name": "苏晚"}, token=access)
check("列表名已更新", patched["name"] == "苏晚", patched["name"])
check("spec.name 同步更新", patched["spec"]["name"] == "苏晚", patched["spec"]["name"])
check("人设提示词里的旧名被替换", "苏桃" not in patched["spec"]["system_prompt"] and "苏晚" in patched["spec"]["system_prompt"], patched["spec"]["system_prompt"][:30])

conn = sqlite3.connect(DB)
row = conn.execute("SELECT name, spec_json FROM personas WHERE id=?", (pid,)).fetchone()
conn.close()
saved = json.loads(row[1])
check("落库列与 spec 一致", row[0] == "苏晚" and saved["name"] == "苏晚", f"{row[0]}/{saved['name']}")

call("PATCH", f"/personas/{pid}", {"name": ""}, token=access, expect=422)
call("PATCH", f"/personas/{pid}", {"name": "名" * 21}, token=access, expect=422)
after = call("GET", f"/personas/{pid}", token=access)
check("非法名字被拒后数据没变", after["name"] == "苏晚", after["name"])

# ============ C. 生成时指定名字（真模型，约 30 秒） ============
print("... 真模型生成中（约 30 秒）")
created = call("POST", "/personas", {"tags": ["古板", "档案管理员"], "free_text": "说话像公文", "name": "沈砚"}, token=access, expect=201)
check("生成结果使用用户指定的名字", created["spec"]["name"] == "沈砚", created["spec"].get("name"))
check("列表名与 spec 名一致", created["name"] == "沈砚", created["name"])
check("人设提示词包含该名字", "沈砚" in created["spec"]["system_prompt"], created["spec"]["system_prompt"][:40])

# 名字单独出现、没有任何限定词时必须拒绝（名字不能替代人格描述）
call("POST", "/personas", {"tags": [], "free_text": "", "name": "只有名字"}, token=access, expect=400)

print(f"\nRESULT: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
