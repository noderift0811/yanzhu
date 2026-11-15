"""演示 / 评审账号：启动期幂等播种，评委可直接登录，绕开注册限流。

赛项要求「在线演示地址 + 评审账号」；而注册接口按 IP 限流（15 分钟 5 个），
评委多人同时进来、或换网络重试，很容易撞 429 把人挡在门外。给一个固定账号
既能避开这条链路，也能把配额调高，避免演示到一半撞到 20 次/天的生成上限。

账号密码走 config（可用 DEMO_USER_* 环境变量覆盖），关闭开关即不播种。
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from .config import get_settings
from .db import db_session
from .security import hash_password


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_demo_user() -> bool:
    """创建或校正演示账号，返回本次是否新建（供启动日志用）。"""
    s = get_settings()
    if not s.demo_user_enabled:
        return False

    # 演示账号预置「心理陪伴」并豁免切换冷却（评委要逐个场景验证），
    # 所以它必须一开始就有一个已选场景，否则会被引导页拦住。
    with db_session() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (s.demo_username,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO users (id, username, password_hash, quota_gen_daily,"
                " quota_chat_daily, quota_gen_used, quota_chat_used, quota_reset_at, created_at,"
                " primary_scene, scene_changed_at)"
                " VALUES (?,?,?,?,?,0,0,?,?,?,?)",
                (
                    str(uuid.uuid4()),
                    s.demo_username,
                    hash_password(s.demo_password),
                    s.demo_quota_gen,
                    s.demo_quota_chat,
                    date.today().isoformat(),
                    _now(),
                    s.demo_scene,
                    _now(),
                ),
            )
            return True
        # 账号已存在：每次启动把配额拉回演示档位，旧库里被改小的也不会把演示卡死。
        # 不改密码——评委可能已经改过，覆盖会让人莫名其妙登不进去。
        conn.execute(
            "UPDATE users SET quota_gen_daily=?, quota_chat_daily=? WHERE id=?",
            (s.demo_quota_gen, s.demo_quota_chat, row["id"]),
        )
        # 老库里的演示账号是在场景功能之前建的，没有主场景，补一个免得被引导页拦住；
        # 已经选过的（包括评委切到别的场景）一律不动。
        if not row["primary_scene"]:
            conn.execute(
                "UPDATE users SET primary_scene=?, scene_changed_at=? WHERE id=?",
                (s.demo_scene, _now(), row["id"]),
            )
            scene = s.demo_scene
        else:
            scene = row["primary_scene"]

        # 专属网站模式：demo 登录要「直接进专属页面」，至少得有一个 active 人格。
        # scene_lock_test 会把 demo 的场景来回切、人格归档干净（且不恢复），
        # 这里做幂等兜底：没有 active 人格时，恢复当前场景下最早的一个归档人格。
        has_active = conn.execute(
            "SELECT 1 FROM personas WHERE user_id=? AND status!='archived' LIMIT 1",
            (row["id"],),
        ).fetchone()
        if has_active is None:
            cand = conn.execute(
                "SELECT id FROM personas WHERE user_id=? AND scene_id=? AND status='archived'"
                " ORDER BY created_at ASC LIMIT 1",
                (row["id"], scene),
            ).fetchone()
            if cand:
                conn.execute("UPDATE personas SET status='active' WHERE id=?", (cand["id"],))
        return False
