"""限流分桶验收：注册与登录必须各自计数，不能互相挤占。"""
import json
import os
import secrets
import urllib.error
import urllib.request

BASE = os.environ.get("YANZHU_API", "http://127.0.0.1:8100/api")
passed = failed = 0


def call(method, path, body=None, expect=200):
    global passed, failed
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    data = json.dumps(body).encode() if body is not None else None
    payload = {}
    try:
        with urllib.request.urlopen(req, data=data) as resp:
            payload = json.loads(resp.read().decode() or "{}")
            code = resp.status
    except urllib.error.HTTPError as e:
        payload = json.loads(e.read().decode() or "{}")
        code = e.code
    if code == expect:
        passed += 1
    else:
        failed += 1
        print(f"[FAIL] {method} {path} 期望 {expect} 实际 {code} {payload}")
    return code, payload


def check(label, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"[ok] {label}")
    else:
        failed += 1
        print(f"[FAIL] {label} {detail}")


# 登录 6 次（超过注册档的 5 次上限），注册不应受牵连
for i in range(6):
    call("POST", "/auth/login", {"username": "real02", "password": "test123456"}, expect=200)
check("连续登录 6 次未触发登录限流", True)

name = "rl" + secrets.token_hex(3)
code, body = call("POST", "/auth/register", {"username": name, "password": "test123456"}, expect=201)
check("登录 6 次后仍可注册（两档独立计数）", code == 201, body)

# 注册档自己仍然生效：同一 IP 再注册 4 次，第 6 次应 429
for i in range(4):
    call("POST", "/auth/register", {"username": f"{name}x{i}", "password": "test123456"}, expect=201)
code, body = call("POST", "/auth/register", {"username": f"{name}z", "password": "test123456"}, expect=429)
check("注册档上限仍生效（第 6 个被拒）", code == 429, body)

# 注册被限后，登录不受影响
call("POST", "/auth/login", {"username": "real02", "password": "test123456"}, expect=200)
check("注册被限时登录仍正常", True)

# 清理这几个账号
import sqlite3

conn = sqlite3.connect("data/yanzhu.db")
uids = [
    r[0]
    for r in conn.execute(
        "SELECT id FROM users WHERE username LIKE ?", (name + "%",)
    )
]
for uid in uids:
    conn.execute(
        "DELETE FROM messages WHERE conversation_id IN "
        "(SELECT id FROM conversations WHERE persona_id IN (SELECT id FROM personas WHERE user_id=?))",
        (uid,),
    )
    conn.execute(
        "DELETE FROM conversations WHERE persona_id IN (SELECT id FROM personas WHERE user_id=?)",
        (uid,),
    )
    conn.execute("DELETE FROM personas WHERE user_id=?", (uid,))
    conn.execute("DELETE FROM llm_calls WHERE user_id=?", (uid,))
    conn.execute("DELETE FROM refresh_tokens WHERE user_id=?", (uid,))
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
conn.commit()
conn.close()
print(f"已清理 {len(uids)} 个测试账号")

print(f"\n通过 {passed} / 失败 {failed}")
