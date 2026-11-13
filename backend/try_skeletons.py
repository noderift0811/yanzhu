"""真模型抽样：验证工程师 AI 会在 16 套骨架里按气质选不同骨架。
用法：python try_skeletons.py   （需后端 8100 已起、.env 有真 key）
"""
import json
import os
import time
import urllib.request

BASE = os.environ.get("YANZHU_API", "http://127.0.0.1:8100/api")


def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("X-Yanzhu-Token", token)
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(req, data=data, timeout=240) as r:
        return json.loads(r.read().decode() or "{}")


SAMPLES = [
    (["侦探", "冷峻", "推理"], "退休刑警，说话短促，习惯反问，对一切都保持怀疑"),
    (["小店老板", "烟火气", "家常"], "凌晨面馆的老板，爱唠叨，总关心客人吃没吃饱"),
    (["外星AI", "科幻", "冷静"], "舰载系统，说话像运行日志，没有情绪，只报事实"),
]

tok = call("POST", "/auth/login", {"username": "real02", "password": "test123456"})["access_token"]
print("登录成功\n")

for tags, free in SAMPLES:
    t0 = time.time()
    p = call("POST", "/personas", {"tags": tags, "free_text": free}, tok)
    spec = p.get("spec") or {}
    print(f"{time.time() - t0:5.1f}s  {spec.get('name'):<6} → {str(spec.get('skeleton_id')):<10} "
          f"status={p.get('status')}  brief={'/'.join(tags)}")
