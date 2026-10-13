"""本地启动入口：检查环境、选择端口、启动服务并打开浏览器。"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
import webbrowser


PROJECT_ROOT = Path(__file__).resolve().parent
LOCAL_HOST = "127.0.0.1"
DEPENDENCIES = ("uvicorn", "fastapi", "sqlalchemy", "alembic", "pydantic_settings",
                "jwt", "bcrypt", "openpyxl", "multipart", "httpx", "cryptography")
# 只有提供当前跳绳表格功能的本系统才可复用，旧版或其他服务不作复用。
REQUIRED_FEATURES = {"rope-skipping-workbench", "rope-registration-tables", "ai-copilot-platform", "configured-college-team-scope"}
HTTP = build_opener(ProxyHandler({}))


def ready_system(port: int) -> bool:
    try:
        with HTTP.open(f"http://{LOCAL_HOST}:{port}/health", timeout=.5) as response:
            data = json.loads(response.read(65536))
        return (isinstance(data, dict) and data.get("status") == "ok"
                and REQUIRED_FEATURES.issubset(set(data.get("features") or [])))
    except (OSError, URLError, ValueError, TypeError):
        return False


def port_available(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            # Windows上禁止与已监听的服务共用端口。
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            probe.bind((LOCAL_HOST, port))
        return True
    except OSError:
        return False


def select_port(preferred: int, fallback: bool = True) -> tuple[int, bool]:
    ports = list(range(preferred, min(preferred + (10 if fallback else 0), 65535) + 1))
    for port in ports:
        if not port_available(port) and ready_system(port):
            return port, True
    for port in ports:
        if port_available(port):
            return port, False
    raise RuntimeError(f"端口 {ports[0]}—{ports[-1]} 均不可用，请关闭占用端口的程序后重试。")


def frontend_needs_build(root: Path) -> bool:
    index = root / "frontend" / "dist" / "index.html"
    if not index.is_file():
        return True
    built_at = index.stat().st_mtime
    frontend = root / "frontend"
    inputs = [frontend / name for name in ("index.html", "package.json", "package-lock.json", "vite.config.ts",
                                           "tsconfig.json", "tsconfig.app.json", "tsconfig.node.json")]
    inputs.extend(path for path in (frontend / "src").rglob("*") if path.is_file())
    return any(path.is_file() and path.stat().st_mtime > built_at for path in inputs)


def check_environment() -> None:
    if sys.version_info < (3, 12):
        raise RuntimeError("需要 Python 3.12 或更高版本。")
    missing = [name for name in DEPENDENCIES if importlib.util.find_spec(name) is None]
    if missing:
        raise RuntimeError("Python依赖不完整：" + "、".join(missing)
                           + f'\n请执行："{sys.executable}" -m pip install -r "{PROJECT_ROOT / "backend" / "requirements.txt"}"')
    if frontend_needs_build(PROJECT_ROOT):
        if not (PROJECT_ROOT / "frontend" / "node_modules" / ".bin" / "vite.cmd").is_file() or not shutil.which("npm.cmd"):
            raise RuntimeError("前端需要构建。请先安装Node.js，并在项目目录执行：\n"
                               "npm.cmd --prefix frontend ci\nnpm.cmd --prefix frontend run build")


def ensure_frontend() -> None:
    if not frontend_needs_build(PROJECT_ROOT):
        return
    print("前端页面有更新，正在自动构建，请稍候……", flush=True)
    # Windows的npm.cmd通过cmd启动；命令和参数均固定，工作目录单独传递。
    result = subprocess.run([os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c",
                             "npm.cmd --prefix frontend run build"], cwd=PROJECT_ROOT, check=False)
    if result.returncode:
        raise RuntimeError("前端构建失败，请查看上方错误信息后重新启动。")


def open_when_ready(port: int) -> None:
    for _ in range(120):
        if ready_system(port):
            webbrowser.open(f"http://{LOCAL_HOST}:{port}", new=2)
            return
        time.sleep(.5)
    print(f"浏览器未自动打开，请手动访问：http://{LOCAL_HOST}:{port}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="一键启动校园运动会赛事成绩管理系统")
    parser.add_argument("--check", action="store_true", help="只检查环境，不启动服务或打开浏览器")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-port-fallback", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("端口须为1至65535")
    os.chdir(PROJECT_ROOT)
    try:
        check_environment()
        if args.check:
            print(f"环境检查通过。Python：{sys.version.split()[0]}；项目：{PROJECT_ROOT}")
            if frontend_needs_build(PROJECT_ROOT):
                print("下次启动时将自动构建前端页面。")
            return 0
        ensure_frontend()
        port, running = select_port(args.port, not args.no_port_fallback)
        url = f"http://{LOCAL_HOST}:{port}"
        if running:
            print(f"系统已经运行，已复用现有服务：{url}", flush=True)
            if not args.no_browser:
                webbrowser.open(url, new=2)
            return 0
        if port != args.port:
            print(f"{args.port}端口已被占用，自动改用{port}端口。", flush=True)
        print(f"正在启动校园运动会赛事成绩管理系统：{url}", flush=True)
        print("启动完成后会自动打开浏览器。请保留此窗口；停止系统请按 Ctrl+C。" if not args.no_browser
              else "请保留此窗口；停止系统请按 Ctrl+C。", flush=True)
        if not args.no_browser:
            threading.Thread(target=open_when_ready, args=(port,), daemon=True).start()
        import uvicorn
        uvicorn.run("backend.app.main:app", app_dir=str(PROJECT_ROOT), host=LOCAL_HOST, port=port)
        return 0
    except (RuntimeError, OSError) as exc:
        print(f"启动失败：{exc}", file=sys.stderr, flush=True)
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
