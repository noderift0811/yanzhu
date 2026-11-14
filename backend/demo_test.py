"""演示 / 评审账号验收：播种幂等、密码哈希、配额档位、登录链路。

不依赖 API Key。播种是幂等的——反复跑这个脚本不会把账号或密码搅乱，
否则「评委改过密码后重启反而登不进去」这类问题要等交付当天才会暴露。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 与其它验收脚本一致：HTTP_PROXY 会把 127.0.0.1 也劫到代理，返回 502
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

from app.config import get_settings
from app.db import db_session
from app.demo import ensure_demo_user

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


def http_json(path, method="GET", body=None, token=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("X-Yanzhu-Token", token)
    try:
        with OPENER.open(req, timeout=8) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except Exception:  # noqa: BLE001
            return e.code, {}


s = get_settings()
print("=== A 播种幂等（直接落库） ===")
check("演示账号开关默认开启", s.demo_user_enabled is True)
first = ensure_demo_user()
second = ensure_demo_user()
check("重复播种不重复建号", first is False and second is False, f"{first}/{second}")

with db_session() as conn:
    rows = conn.execute(
        "SELECT id, password_hash, quota_gen_daily, quota_chat_daily, quota_gen_used"
        " FROM users WHERE username=?",
        (s.demo_username,),
    ).fetchall()
check("库中只有一条演示账号", len(rows) == 1, len(rows))
row = rows[0] if rows else None
if row:
    check("密码以 bcrypt 哈希入库", row["password_hash"].startswith("$2") and s.demo_password not in row["password_hash"])
    check(
        "配额是演示档位",
        (row["quota_gen_daily"], row["quota_chat_daily"]) == (s.demo_quota_gen, s.demo_quota_chat),
        (row["quota_gen_daily"], row["quota_chat_daily"]),
    )
    check("新建账号已用次数为 0", row["quota_gen_used"] == 0, row["quota_gen_used"])

print("\n=== B HTTP（服务不可达则跳过） ===")
try:
    status, d = http_json("/meta/demo-account")
    check("GET /meta/demo-account 200", status == 200, status)
    check("下发的账号可用", d.get("enabled") is True and d.get("username") == s.demo_username, d)
    check("下发密码与配置一致", d.get("password") == s.demo_password, d.get("password"))

    status, tok = http_json(
        "/auth/login", "POST", {"username": s.demo_username, "password": s.demo_password}
    )
    check("演示账号可登录", status == 200 and "access_token" in tok, status)
    access = tok.get("access_token")
    if access:
        status, me = http_json("/auth/me", token=access)
        check("GET /auth/me 200", status == 200, status)
        check(
            "登录后配额与配置一致",
            (me.get("quota_gen_daily"), me.get("quota_chat_daily")) == (s.demo_quota_gen, s.demo_quota_chat),
            me,
        )

    status, bad = http_json(
        "/auth/login", "POST", {"username": s.demo_username, "password": s.demo_password + "x"}
    )
    check("错误密码被拒 401", status == 401 and bad.get("code") == "INVALID_CREDENTIALS", (status, bad))
except Exception as e:  # noqa: BLE001
    print(f"[skip] HTTP 部分未运行：{type(e).__name__}: {e}")

print(f"\n结果: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
