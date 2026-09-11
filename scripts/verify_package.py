# -*- coding: utf-8 -*-
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
package_dir = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else project_root / "dist" / "校园运动会成绩管理系统_绿色免安装版"
exe_path = package_dir / "校园运动会成绩管理系统.exe"
if not exe_path.exists():
    print(f"ERROR: {exe_path} does not exist!")
    sys.exit(1)

def port_is_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) != 0


target_port = next(port for port in range(8000, 8050) if port_is_available(port))
child_env = os.environ.copy()
# 验收时禁用自动打开浏览器，只检查打包程序自身的 HTTP 服务。
child_env["BROWSER"] = "__codex_package_verification_no_browser__"

print(f"Starting packaged exe in background (expected port {target_port})...")
proc = subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent), env=child_env)
print(f"Started process with PID: {proc.pid}")

try:
    health_data = None
    deadline = time.monotonic() + 30
    last_error = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"Packaged process exited early with code {proc.returncode}")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{target_port}/health", timeout=2) as resp:
                health_data = json.loads(resp.read().decode("utf-8"))
                break
        except Exception as exc:
            last_error = exc
            time.sleep(0.5)
    if health_data is None:
        raise RuntimeError(f"Health endpoint did not become ready: {last_error}")
    print(f"Health endpoint verified: {health_data}")

    # Test index.html
    spa_url = f"http://127.0.0.1:{target_port}/"
    with urllib.request.urlopen(spa_url, timeout=3) as resp:
        html = resp.read().decode("utf-8")
        print(f"SPA index.html status: {resp.status}, length: {len(html)}")
        assert "<title>" in html, "SPA index.html missing title tag"
        print("SPA index.html verified successfully!")

    # Test template file download endpoint
    tpl_url = f"http://127.0.0.1:{target_port}/api/v1/sports-teacher/students/template"
    # Need auth or check direct response; if 401 Unauthorized, it proves endpoint exists and router is loaded
    try:
        urllib.request.urlopen(tpl_url, timeout=3)
    except urllib.error.HTTPError as he:
        if he.code != 401:
            raise
        print(f"Template endpoint checked (HTTP {he.code}: {he.reason}) - Route is active!")

finally:
    print("Terminating test process...")
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

print("ALL VERIFICATIONS PASSED!")
