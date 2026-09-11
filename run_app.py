import os
import sys
import time
import socket
import webbrowser
import threading
import uvicorn

# 确保在打包后或双击运行时，工作目录与导入路径正确
if getattr(sys, "frozen", False):
    app_dir = os.path.dirname(sys.executable)
    os.chdir(app_dir)
    sys.path.insert(0, app_dir)
else:
    app_dir = os.path.abspath(os.path.dirname(__file__))
    os.chdir(app_dir)
    sys.path.insert(0, app_dir)

# 确保运行时必要目录存在
os.makedirs(os.path.join(app_dir, "data", "exports"), exist_ok=True)
os.makedirs(os.path.join(app_dir, "data", "backups"), exist_ok=True)

from backend.app.main import app


if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def get_lan_ip() -> str:
    """获取本机在局域网中的 IPv4 地址"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) != 0


def find_free_port(start_port: int = 8000) -> int:
    for p in range(start_port, start_port + 50):
        if is_port_available(p):
            return p
    return start_port


def open_browser_later(url: str):
    time.sleep(1.2)
    try:
        webbrowser.open(url)
    except Exception:
        print(f"[*] 提示：自动打开浏览器失败，请手动在浏览器中输入网址: {url}")


def main():
    port = find_free_port(8000)
    local_url = f"http://127.0.0.1:{port}"
    lan_ip = get_lan_ip()
    lan_url = f"http://{lan_ip}:{port}" if lan_ip and lan_ip != "127.0.0.1" else None

    print("=" * 68)
    print("       【校园运动会赛事成绩管理系统】离线免安装便携版已就绪")
    print("=" * 68)
    print(f"  * 本机访问网址:   {local_url}")
    if lan_url:
        print(f"  * 局域网协同网址: {lan_url}  (同一Wi-Fi下手机/平板可直接输入访问)")
    print(f"  * 数据保存目录:   {os.path.join(app_dir, 'data')}")
    print("  * --------------------------------------------------------------")
    print("  * 默认管理员账号: admin0001     密码: Admin123456!")
    print("  * 默认开发人员账号: developer01   密码: Dev123456!")
    print("  * 学生免密/初始密码: DF + 学号后6位")
    print("=" * 68)
    print("  系统正在为您自动打开浏览器，请稍候...")
    print("  【提示】保持此黑色控制台窗口开启即为运行；关闭此窗口即可退出系统。\n")

    threading.Thread(target=open_browser_later, args=(local_url,), daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()

