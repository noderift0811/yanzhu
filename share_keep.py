"""言筑公网分享·守护版（双引擎）。

为什么改：cpolar 免费隧道在同一台机器上反复失效——日志里成片
`StartProxy ... i/o timeout`，加上免费额度会被账号下其它隧道挤占。
localhost.run 走 ssh，不需要二进制、不需要账号，实测更稳。

引擎选择：
  默认 ssh      → localhost.run，地址形如 https://xxxx.lhr.life
  SHARE_ENGINE=cpolar 时改用 cpolar（带 HTTP Basic 口令）

守护职责：
  1. 隧道进程退出 → 3 秒后重起
  2. 进程活着但公网不通 → 连续 2 次探测失败就杀掉重连
  3. 拿到新地址自动重写 share-url.txt / share-access.txt

用法：python share_keep.py        停止：Ctrl+C
日志：share.log
"""

import base64
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from collections import deque
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
LOG_PATH = ROOT / "share.log"

FRONTEND_PORT = os.environ.get("SHARE_PORT", "4180")
LOCAL = "http://127.0.0.1:%s/" % FRONTEND_PORT
ENGINE = os.environ.get("SHARE_ENGINE", "ssh").strip().lower()

# 地址解析放全局，两个引擎各一套正则
SSH_TEXT_RE = re.compile(r"https://([a-z0-9][a-z0-9-]*\.lhr\.life)")

# localhost.run：只需要系统自带的 ssh，无需注册。
# -F /dev/null 是关键——默认会读 ~/.ssh/config，那台机器的 config 有一条
# 无法映射的 ACL 残留，Windows OpenSSH 直接报 "Bad owner or permissions" 拒绝启动。
SSH_HOST = os.environ.get("SHARE_SSH_HOST", "nokey@localhost.run")
SSH_CMD = [
    "ssh", "-F", "/dev/null",
    "-o", "StrictHostKeyChecking=no",
    "-o", "UserKnownHostsFile=/dev/null",
    "-o", "BatchMode=yes",
    "-o", "ExitOnForwardFailure=yes",
    "-o", "ServerAliveInterval=20",
    "-o", "ServerAliveCountMax=3",
    "-o", "TCPKeepAlive=yes",
    "-R", "80:127.0.0.1:%s" % FRONTEND_PORT,
]

# cpolar：需要二进制，且账户是 free 计划，随时可能被并发额度挤掉。
CPOLAR_CANDIDATES = [
    Path(r"F:\cpolar\cpolar.exe"),
    Path(r"C:\Program Files\cpolar\cpolar.exe"),
    Path(r"C:\Program Files (x86)\cpolar\cpolar.exe"),
]
CPOLAR_TEXT_RE = re.compile(r"Tunnel established at (https://[^\s\"]+)")
HTTP_USER = os.environ.get("SHARE_USER", "yanzhu")
HTTP_PASS = os.environ.get("SHARE_PASS", "yanzhu2026")

PROBE_INTERVAL = 60
PROBE_FAIL_LIMIT = 2
RESTART_DELAY = 3

_log_lock = threading.Lock()


def say(msg=""):
    print(msg, flush=True)


def log(line):
    try:
        with _log_lock, LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# 本机装了 HTTP_PROXY 时，urlopen 默认会走代理，把 127.0.0.1 也送去代理，
# 结果无论服务在不在都返回 502 —— 探活必须以直连为准。
_DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def local_ready():
    try:
        with _DIRECT.open(LOCAL, timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def probe_public(url, timeout=25):
    headers = {"User-Agent": "yanzhu-share-check"}
    if ENGINE == "cpolar":
        raw = ("%s:%s" % (HTTP_USER, HTTP_PASS)).encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")
    try:
        req = urllib.request.Request(url, headers=headers)
        with _DIRECT.open(req, timeout=timeout) as r:
            return r.status
    except Exception as e:
        return "失败(%s)" % type(e).__name__


def publish(url):
    (ROOT / "share-url.txt").write_text(url + "\n", encoding="utf-8")
    lines = ["URL: %s" % url]
    if ENGINE == "cpolar":
        lines += ["用户名: %s" % HTTP_USER, "密码: %s" % HTTP_PASS]
    else:
        lines.append("口令: 无（直接打开，登录用言筑自己的账号）")
    (ROOT / "share-access.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def watchdog(url, proc, stop_evt):
    """进程活着但公网静默失效的兜底：连续两次探测失败就杀掉进程触发重连。"""
    fails = 0
    while not stop_evt.wait(PROBE_INTERVAL):
        if proc.poll() is not None:
            return
        status = probe_public(url)
        if status == 200:
            if fails:
                log("  [守护] 公网恢复，继续使用 %s" % url)
            fails = 0
            continue
        fails += 1
        log("  [守护] 探测 %s 返回 %s（第 %d 次）" % (url, status, fails))
        if fails >= PROBE_FAIL_LIMIT:
            say("  ! 隧道静默失效，正在重建 ...")
            log("  [守护] 连续 %d 次失败，重启隧道" % fails)
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
            return


def find_cpolar():
    for p in CPOLAR_CANDIDATES:
        if p.exists():
            return p
    found = shutil.which("cpolar")
    return Path(found) if found else None


def open_engine():
    """返回 (进程, 用于解析地址的正则)。"""
    if ENGINE == "cpolar":
        cpolar = find_cpolar()
        if not cpolar:
            raise RuntimeError("没找到 cpolar.exe")
        cmd = [
            str(cpolar), "http", FRONTEND_PORT,
            "-region=cn_top", "-inspect-addr=false",
            "-host-header=localhost:%s" % FRONTEND_PORT,
            "-httpauth=%s:%s" % (HTTP_USER, HTTP_PASS),
            "-log=stdout", "-log-level=INFO",
        ]
        proc = subprocess.Popen(
            cmd, cwd=str(cpolar.parent), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        return proc, CPOLAR_TEXT_RE
    proc = subprocess.Popen(
        SSH_CMD + [SSH_HOST], cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    return proc, SSH_TEXT_RE


def run_once(attempt):
    proc, pattern = open_engine()
    url = None
    last_lines = deque(maxlen=12)
    stop_evt = threading.Event()
    try:
        for line in proc.stdout:
            line = line.rstrip()
            last_lines.append(line)
            if ENGINE == "cpolar" and "level=error" in line and "SplitHostPort" not in line:
                log("  ! " + line)
                continue
            if not url:
                m = pattern.search(line)
                if m:
                    url = m.group(1)
                    if not url.startswith("http"):
                        url = "https://" + url
                    say()
                    say("  " + "-" * 56)
                    say("   公网地址（第 %d 次建立）: %s" % (attempt, url))
                    say("  " + "-" * 56)
                    status = probe_public(url + "/")
                    say("   自检结果: HTTP %s" % status)
                    log("  [隧道] %s 自检 %s" % (url, status))
                    if status in (200, 401):
                        publish(url)
                        say("   已写入 share-url.txt")
                    threading.Thread(
                        target=watchdog, args=(url + "/", proc, stop_evt), daemon=True
                    ).start()
        proc.wait()
    finally:
        stop_evt.set()
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
        if last_lines:
            log("  [退出] code=%s，末尾输出：" % proc.returncode)
            for ln in list(last_lines)[-6:]:
                log("        " + ln)
    return proc.returncode


def main():
    if not local_ready():
        say("[ERROR] 本机 %s 没在跑。先双击 start.bat 把言筑跑起来。" % LOCAL)
        return 1
    LOG_PATH.write_text("", encoding="utf-8")
    say("=" * 62)
    say("  言筑 YanZhu 公网分享 · 守护模式（引擎：%s）" % ENGINE)
    say("  掉线自动重建，地址变化会重写 share-url.txt")
    say("  停止：Ctrl+C")
    say("=" * 62)

    attempt = 0
    try:
        while True:
            attempt += 1
            if attempt > 1:
                say()
                say("  正在重建隧道（第 %d 次）..." % attempt)
                time.sleep(RESTART_DELAY)
                if not local_ready():
                    say("  ! 本地 %s 不可用，等待中 ..." % LOCAL)
                    time.sleep(10)
                    continue
            code = run_once(attempt)
            log("  [退出] 第 %d 次隧道结束，code=%s" % (attempt, code))
            say("  隧道断开（code=%s），准备重建。" % code)
    except KeyboardInterrupt:
        say()
        say("已停止守护，隧道关闭。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
