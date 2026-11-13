"""M0 冒烟测试：不接密钥跑通 注册 → 建人格 → 会话 → 聊天 → 历史 → 重生成 → 删除。"""
import json
import os
import sys
import urllib.request

# 后端默认 8100（8000 常被本机其它 FastAPI 项目占用），可改 YANZHU_API 覆盖。
BASE = os.environ.get("YANZHU_API", "http://127.0.0.1:8100/api")
USER = f"m0user{sys.argv[1] if len(sys.argv) > 1 else '01'}"
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
    mark = "PASS" if ok else "FAIL"
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"[{mark}] {method} {path} -> {payload if not ok else 'ok'}")
    return payload


# 1. 注册 / 登录 / me
tokens = call("POST", "/auth/register", {"username": USER, "password": PWD}, expect=201)
access = tokens["access_token"]
refresh = tokens["refresh_token"]
call("GET", "/auth/me", token=access)
call("POST", "/auth/refresh", {"refresh_token": refresh})

# 2. 建人格（Mock 工程师 AI）
persona = call("POST", "/personas", {"tags": ["内向", "害羞", "笔友"], "free_text": "句末常带省略号"}, token=access, expect=201)
pid = persona["id"]
assert persona["spec"]["skeleton_id"] == "diary", persona["spec"]["skeleton_id"]
assert persona["spec"]["opening_message"], "opening_message 缺失"
call("GET", "/personas", token=access)
call("GET", f"/personas/{pid}", token=access)
call("PATCH", f"/personas/{pid}", {"name": "苏桃"}, token=access)

# 3. 会话 + 种子开场白
conv = call("POST", f"/personas/{pid}/conversations", {}, token=access, expect=201)
cid = conv["id"]
msgs = call("GET", f"/conversations/{cid}/messages", token=access)
assert msgs["items"] and msgs["items"][0]["role"] == "assistant", "种子开场白缺失"

# 4. 聊天（Mock 人格 AI，非流式）
reply = call("POST", f"/conversations/{cid}/messages", {"content": "今天有点累"}, token=access)
assert reply["assistant_message"]["content"], "回复为空"

# 4b. 流式聊天（SSE：meta → token* → done）
try:
    req = urllib.request.Request(
        BASE + f"/conversations/{cid}/messages/stream",
        method="POST",
        data=json.dumps({"content": "流式也说一句"}).encode(),
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {access}")
    events = []
    done_payload = None
    with urllib.request.urlopen(req) as resp:
        event_name = None
        for raw_line in resp:
            line = raw_line.decode().rstrip("\n")
            if line.startswith("event:"):
                event_name = line[6:].strip()
            elif line.startswith("data:"):
                events.append(event_name)
                if event_name == "done":
                    done_payload = json.loads(line[5:].strip())
                    break
    ok = (
        resp.status == 200
        and events[:1] == ["meta"]
        and "token" in events
        and events[-1] == "done"
        and bool(done_payload and done_payload.get("assistant_message", {}).get("content"))
        and bool(done_payload.get("quota"))
    )
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"[{'PASS' if ok else 'FAIL'}] POST /messages/stream -> events={events}")
except Exception as e:  # noqa: BLE001
    failed += 1
    print(f"[FAIL] POST /messages/stream -> {e}")

# 5. 重新生成 + 删除
call("POST", f"/personas/{pid}/regenerate", {"tags": ["毒舌", "前辈"], "free_text": "嘴硬心软"}, token=access)
call("DELETE", f"/personas/{pid}", token=access, expect=204)

# 6. 未授权访问应 401
call("GET", "/personas", expect=401)

print(f"\nRESULT: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
