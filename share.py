"""言筑一键分享：用本机已装好的 cpolar 起一条只暴露前端 4180 的公网隧道。

为什么只暴露 4180：前端 preview 自带 /api 代理到 127.0.0.1:8100，
所以隧道只开一个口，后端不会被直接暴露在公网。

用法：双击同目录的 share.bat，或 python share.py。
停止：在本窗口按 Ctrl+C。
"""

import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent

# 前端端口：与 frontend/vite.config.js 的 preview.port、start.bat 的 FRONTEND_PORT 保持一致。
# 4180 是本机让出来的位置——8000/4173/5173 常被别的项目（人智评分系统）占着。
FRONTEND_PORT = os.environ.get("SHARE_PORT", "4180")
LOCAL = "http://127.0.0.1:%s/" % FRONTEND_PORT
CPOLAR_CANDIDATES = [
    Path(r"F:\cpolar\cpolar.exe"),
    Path(r"C:\Program Files\cpolar\cpolar.exe"),
    Path(r"C:\Program Files (x86)\cpolar\cpolar.exe"),
]
URL_RE = re.compile(r'Tunnel established at (https://[^\s"]+)')

# 隧道访问口令（HTTP Basic）。想换口令直接改这里，或用环境变量 SHARE_USER / SHARE_PASS。
# 前端令牌走 X-Yanzhu-Token 自定义头，所以不会和 Basic 抢 Authorization。
HTTP_USER = os.environ.get("SHARE_USER", "yanzhu")
HTTP_PASS = os.environ.get("SHARE_PASS", "yanzhu2026")


def say(msg=""):
    print(msg, flush=True)


def find_cpolar():
    for p in CPOLAR_CANDIDATES:
        if p.exists():
            return p
    import shutil

    found = shutil.which("cpolar")
    return Path(found) if found else None


def local_ready():
    try:
        with urllib.request.urlopen(LOCAL, timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def probe_public(url, user=None, password=None):
    import base64

    headers = {"User-Agent": "yanzhu-share-check"}
    if user:
        raw = ("%s:%s" % (user, password)).encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except Exception as e:
        return "失败(%s)" % type(e).__name__


def main():
    cpolar = find_cpolar()
    if not cpolar:
        say("[ERROR] 没找到 cpolar.exe，请确认已安装 cpolar。")
        return 1

    if not local_ready():
        say("[ERROR] 本机 %s 没在跑。" % LOCAL)
        say("        请先双击 start.bat 把言筑跑起来，再运行本脚本。")
        return 1

    say("=" * 62)
    say("  言筑 YanZhu 公网分享（cpolar 隧道 -> 127.0.0.1:%s）" % FRONTEND_PORT)
    say("  建立连接需要 5-15 秒，拿到地址后复制给朋友即可")
    say("  停止分享：在本窗口按 Ctrl+C")
    say("=" * 62)
    say()
    say("  访问口令（浏览器会弹框要求输入）:")
    say("     用户名  %s" % HTTP_USER)
    say("     密  码  %s" % HTTP_PASS)
    say("  想换口令：改本文件顶部的 HTTP_USER / HTTP_PASS")
    say()

    cmd = [
        str(cpolar),
        "http",
        FRONTEND_PORT,
        "-region=cn_top",
        "-inspect-addr=false",
        "-host-header=localhost:%s" % FRONTEND_PORT,
        "-httpauth=%s:%s" % (HTTP_USER, HTTP_PASS),
        "-log=stdout",
        "-log-level=INFO",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(cpolar.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    public_url = None
    try:
        for line in proc.stdout:
            line = line.rstrip()
            # -inspect-addr=false 会让 cpolar 自己打一条 SplitHostPort 报错，是无害噪声
            if "level=error" in line and "SplitHostPort" not in line:
                say("  ! " + line)
                continue
            m = URL_RE.search(line)
            if m and not public_url:
                public_url = m.group(1)
                say()
                say("  " + "-" * 56)
                say("   公网地址（发给朋友的就是这个）:")
                say("   " + public_url)
                say("  " + "-" * 56)
                say()
                say("   正在自检公网可达性 ...", )
                status = probe_public(public_url + "/", HTTP_USER, HTTP_PASS)
                say("   自检结果: HTTP %s" % status)
                if status == 200:
                    say("   可以分享了。朋友打开后先过口令框，再自己注册账号。")
                    (ROOT / "share-url.txt").write_text(public_url + "\n", encoding="utf-8")
                    (ROOT / "share-access.txt").write_text(
                        "URL: %s\n用户名: %s\n密码: %s\n" % (public_url, HTTP_USER, HTTP_PASS),
                        encoding="utf-8",
                    )
                    say("   地址与口令也已写入 share-url.txt / share-access.txt")
                elif status == 401:
                    say("   隧道通了但口令不对（自检拿到 401）。检查 HTTP_USER / HTTP_PASS。")
                else:
                    say("   公网暂时不通，稍等十几秒再刷新一次；若持续失败请重试。")
                say()
        proc.wait()
    except KeyboardInterrupt:
        say()
        say("正在关闭隧道 ...")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
        say("隧道已关闭。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
