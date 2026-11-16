"""AI 装修接口验收：自然语言→主题、对比度护栏、不耗配额、不落库、非法值拒。"""
import json
import os
import urllib.error
import urllib.request

BASE = os.environ.get("YANZHU_API", "http://127.0.0.1:8100/api")
USER = "demo"
PWD = "yanzhu2026"
passed = failed = 0

BASE_THEME = {
    "primary": "#4f46e5", "bg": "#f7f7f8", "surface": "#ffffff",
    "text": "#1f2328", "accent": "#7c6cf0", "font_style": "system", "decoration": "none",
}


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


def luminance(hex_color):
    h = hex_color.lstrip("#")
    ch = lambda v: (v / 255) / 12.92 if v / 255 <= 0.03928 else (((v / 255) + 0.055) / 1.055) ** 2.4
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def main():
    tok = call("POST", "/auth/login", {"username": USER, "password": PWD})["access_token"]

    # 未登录拒
    call("POST", "/decorate", {"request": "暗色调", "theme": BASE_THEME}, expect=401)

    # 正常装修：深色需求
    me = call("GET", "/auth/me", token=tok)
    quota_before = me.get("quota_gen_used")
    r = call("POST", "/decorate", {
        "request": "深夜咖啡馆那种暖橙色暗色调", "theme": BASE_THEME, "skeleton_id": "diary",
    }, token=tok)
    theme = r.get("theme", {})
    check("返回完整主题", all(k in theme for k in ("primary", "bg", "surface", "text", "accent", "font_style", "decoration")))
    check("返回一句说明", len(r.get("note", "")) > 0)
    check("标明模型来源", r.get("model", "") != "")
    check("深色需求产出深底", luminance(theme.get("bg", "#ffffff")) < 0.35, theme.get("bg"))
    check("正文对比度护栏(对bg≥4.5)", contrast(theme.get("text", "#000"), theme.get("bg", "#fff")) >= 4.5,
          f"{contrast(theme.get('text','#000'), theme.get('bg','#fff')):.2f}")
    check("正文对比度护栏(对surface≥4.5)", contrast(theme.get("text", "#000"), theme.get("surface", "#fff")) >= 4.5)

    # 不耗生成配额：装修前后 quota_gen_used 不变
    me2 = call("GET", "/auth/me", token=tok)
    check("装修不耗生成配额", me2.get("quota_gen_used") == quota_before,
          f"{quota_before} -> {me2.get('quota_gen_used')}")

    # 不落库：装修只是返回建议，人格的 theme 没被改
    persona_id = me.get("primary_persona_id")
    if persona_id:
        p = call("GET", f"/personas/{persona_id}", token=tok)
        stored = (p.get("spec", {}).get("theme") or p.get("theme") or {})
        check("装修不自动落库", stored.get("bg") != theme.get("bg") or stored.get("primary") != theme.get("primary"),
              f"stored bg={stored.get('bg')} vs suggested bg={theme.get('bg')}")

    # 非法主题值被拒（422）
    call("POST", "/decorate", {
        "request": "改配色", "theme": {**BASE_THEME, "primary": "red"},
    }, token=tok, expect=422)
    # 需求过短被拒（422）
    call("POST", "/decorate", {"request": "a", "theme": BASE_THEME}, token=tok, expect=422)

    print(f"\nRESULT {passed} pass / {failed} fail")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
