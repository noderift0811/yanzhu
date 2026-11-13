"""真模型验收：确认 .env 的双密钥已生效（工程师 v4-pro 生成规格、人格 flash 聊天），
而不是静默回落到 MockAdapter。用法：python real_smoke.py [用户名后缀]"""
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.environ.get("YANZHU_API", "http://127.0.0.1:8100/api")
USER = f"real{sys.argv[1] if len(sys.argv) > 1 else '01'}"
PWD = "test123456"
DB = Path(__file__).resolve().parent / "data" / "yanzhu.db"


def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=180) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def main() -> int:
    ok = True

    status, health = call("GET", "/health")
    print(f"[health] {status} {health}")
    if health.get("app_env") == "framework":
        print("  ! app_env 仍是 framework，.env 可能没被加载")

    status, tokens = call("POST", "/auth/register", {"username": USER, "password": PWD})
    if status != 201:
        print(f"[register] 失败 {status} {tokens}")
        return 1
    access = tokens["access_token"]

    t0 = time.monotonic()
    status, persona = call(
        "POST",
        "/personas",
        {"tags": ["害羞", "笔友", "安静"], "free_text": "说话轻声细语，句末常带省略号，熟了会小声撒娇"},
        token=access,
    )
    gen_ms = int((time.monotonic() - t0) * 1000)
    if status != 201:
        print(f"[generate] 失败 {status} {persona}")
        return 1

    spec = persona["spec"]
    print(f"\n=== 工程师 AI 产出（{gen_ms} ms, status={persona['status']}）===")
    print(f"名字：{spec['name']}")
    print(f"骨架：{spec['skeleton_id']}")
    print(f"主题：primary {spec['theme']['primary']} / bg {spec['theme']['bg']} / {spec['theme']['font_style']} / {spec['theme']['decoration']}")
    print(f"标题：{spec['page_copy']['title']}")
    print(f"开场白：{spec['opening_message']}")
    print(f"输入提示：{spec['page_copy']['input_placeholder']}")
    print(f"\nsystem_prompt（{len(spec['system_prompt'])} 字）：\n{spec['system_prompt']}\n")

    if persona["status"] == "needs_review":
        ok = False
        print("  ! 状态 needs_review：真模型输出未过 schema，走了兜底")

    status, conv = call("POST", f"/personas/{persona['id']}/conversations", {}, token=access)
    cid = conv["id"]

    t1 = time.monotonic()
    req = urllib.request.Request(
        BASE + f"/conversations/{cid}/messages/stream",
        method="POST",
        data=json.dumps({"content": "今天有点累，不太想说话"}).encode(),
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {access}")
    chunks, reply = [], ""
    with urllib.request.urlopen(req, timeout=180) as resp:
        event = None
        for raw in resp:
            line = raw.decode().rstrip("\n")
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:") and event == "token":
                chunks.append(json.loads(line[5:].strip())["text"])
            elif line.startswith("data:") and event == "done":
                reply = json.loads(line[5:].strip())["assistant_message"]["content"]
                break
    chat_ms = int((time.monotonic() - t1) * 1000)
    print(f"=== 人格 AI 回复（{chat_ms} ms, {len(chunks)} 个 token 事件）===")
    print(reply)
    if not reply or reply.startswith("（Mock"):
        ok = False
        print("  ! 回复为空或疑似 Mock 输出")

    with sqlite3.connect(str(DB)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT purpose, adapter, model, latency_ms, status FROM llm_calls ORDER BY id DESC LIMIT 3"
        ).fetchall()
    print("\n=== llm_calls 最近记录 ===")
    for r in rows:
        print(f"  {r['purpose']:9s} {r['adapter']:14s} {r['model']:16s} {r['latency_ms']:>6d}ms {r['status']}")
    adapters = {r["adapter"] for r in rows}
    if "mock" in adapters:
        ok = False
        print("  ! 出现 mock 记录：至少一侧没接上真模型")

    print("\nRESULT:", "PASS 真模型链路可用" if ok else "FAIL 见上方提示")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
