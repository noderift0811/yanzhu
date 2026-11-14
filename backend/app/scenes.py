"""场景锁定的唯一判定点：账号只有一个主场景，切换受冷却与确认约束。

为什么锁在后端：前端只管展示。`POST /personas`、`POST /agent/build` 一律
从 users 表读主场景，请求里带的场景参数只用来交叉校验（不一致就 400）。
否则「一个账号一个场景」只是页面上的一句话，改个请求就破了。

规则：
- 首次选择不需要确认，也没有冷却；
- 已选之后切换需要 confirm=true，且距上次选择满 N 天；
- 演示 / 评审账号豁免冷却（评委要逐个验证场景，不能被 30 天锁住）；
- 切换时旧人格归档为 archived 而不是删除——用户可能只是试一下，
  回不去至少还看得见自己做过什么。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from .config import get_settings
from .errors import ApiError
from .pipeline.presets import DEFAULT_PRESET_ID, PRESET_BY_ID

TONE_KEYS = ("calm", "brief", "no_exclaim")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _parse(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_demo(user: sqlite3.Row) -> bool:
    return user["username"] == get_settings().demo_username


def scene_of(user: sqlite3.Row) -> str:
    """账号当前生效的场景。还没选时按 free 兜底，但「未选」状态仍然可见。"""
    return user["primary_scene"] or DEFAULT_PRESET_ID


def has_chosen(user: sqlite3.Row) -> bool:
    return bool(user["primary_scene"])


def next_switch_at(user: sqlite3.Row) -> Optional[str]:
    """下次可切换的时间；演示账号与从未选过的账号返回 None（表示现在就能选）。"""
    if is_demo(user):
        return None
    changed = _parse(user["scene_changed_at"])
    if changed is None:
        return None
    return _iso(changed + timedelta(days=get_settings().scene_switch_cooldown_days))


def can_switch(user: sqlite3.Row) -> Tuple[bool, Optional[str]]:
    nxt = next_switch_at(user)
    if nxt is None:
        return True, None
    return _now() >= _parse(nxt), nxt


def scene_profile(user: sqlite3.Row) -> Dict[str, Any]:
    """给 /auth/me 的场景视图：前端据此决定是否强制进引导页、按钮是否可点。"""
    scene_id = scene_of(user)
    ok, nxt = can_switch(user)
    preset = PRESET_BY_ID.get(scene_id, {})
    return {
        "primary_scene": user["primary_scene"],
        "scene_id": scene_id,
        "scene_name": preset.get("name", ""),
        "scene_chosen": has_chosen(user),
        "can_switch": ok,
        "next_switch_at": nxt,
        "is_demo": is_demo(user),
        "cooldown_days": get_settings().scene_switch_cooldown_days,
    }


def choose_scene(conn: sqlite3.Connection, user: sqlite3.Row, scene: str, confirm: bool) -> Dict[str, Any]:
    """首次选择或受控切换；返回给前端的场景视图。"""
    if scene not in PRESET_BY_ID:
        raise ApiError(400, "SCENE_UNKNOWN", f"未知场景 {scene}", {"scenes": list(PRESET_BY_ID)})

    current = user["primary_scene"]
    archived = 0
    if current and current != scene:
        if not confirm:
            raise ApiError(
                409,
                "SCENE_CONFIRM_REQUIRED",
                "切换场景会归档当前场景下的所有人格，需要确认",
                {"from": current, "to": scene},
            )
        ok, nxt = can_switch(user)
        if not ok:
            raise ApiError(
                409,
                "SCENE_COOLDOWN",
                f"场景切换有冷却期，{nxt} 之后可再切换",
                {"next_switch_at": nxt, "cooldown_days": get_settings().scene_switch_cooldown_days},
            )
        # 只归档 active/needs_review，已归档的不重复计数
        cur = conn.execute(
            "UPDATE personas SET status='archived', updated_at=?"
            " WHERE user_id=? AND status!='archived'",
            (_iso(_now()), user["id"]),
        )
        archived = cur.rowcount or 0

    if current != scene:
        conn.execute(
            "UPDATE users SET primary_scene=?, scene_changed_at=? WHERE id=?",
            (scene, _iso(_now()), user["id"]),
        )

    fresh = conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
    out = scene_profile(fresh)
    out["switched"] = bool(current) and current != scene
    out["archived_personas"] = archived
    return out


def tone_of(user: sqlite3.Row) -> Dict[str, bool]:
    try:
        raw = json.loads(user["tone_json"] or "{}")
    except (TypeError, ValueError):
        raw = {}
    return {k: bool(raw.get(k)) for k in TONE_KEYS}


def tone_clause(tone: Dict[str, bool]) -> str:
    """把语气开关翻成运行时指令。

    刻意不重写 system_prompt：改写人设要走工程师模型（30 秒 + 耗配额），
    而悬浮球是即时交互，点一下必须马上生效。这里只在消息序列末尾追加一段
    语气提示，不落库、不算生成次数。
    """
    bits = []
    if tone.get("calm"):
        bits.append("语气更沉稳：先承接再回应，不急着给方案")
    if tone.get("brief"):
        bits.append("回复更简短：控制在三句以内，能一句说完就不写第二句")
    if tone.get("no_exclaim"):
        bits.append("不使用感叹号，也不用「呢 / 哦 / 呀」这类语气词")
    if not bits:
        return ""
    return "【本次对话的语气偏好】" + "；".join(bits) + "。这条只影响说法，不改变身份与边界。"


def update_tone(conn: sqlite3.Connection, user: sqlite3.Row, patch: Dict[str, Any]) -> Dict[str, bool]:
    tone = tone_of(user)
    for k in TONE_KEYS:
        if k in patch and patch[k] is not None:
            tone[k] = bool(patch[k])
    conn.execute("UPDATE users SET tone_json=? WHERE id=?", (json.dumps(tone), user["id"]))
    return tone
