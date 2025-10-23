import os
import sys
import socket
import subprocess
import time
import argparse


def get_lan_ip() -> str:
    # 优先通过 UDP "探测" 外网路由以获取本机对外 IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        pass
    # 退化方案：主机名解析
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "127.0.0.1"


def is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def pick_port(start_port: int) -> int:
    port = start_port
    for _ in range(20):
        if is_port_free(port):
            return port
        port += 1
    return start_port


def wait_for_server(host: str, port: int, timeout: int = 20) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def main():
    parser = argparse.ArgumentParser(description="分拣进度实时看板启动器")
    parser.add_argument("--port", type=int, default=8501, help="监听端口 (默认 8501)")
    parser.add_argument("--bind", type=str, default="0.0.0.0", help="绑定地址 (默认 0.0.0.0)")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(base_dir, "streamlit_app.py")
    if not os.path.exists(app_path):
        print(f"[ERROR] 未找到看板文件: {app_path}")
        sys.exit(1)

    port = pick_port(args.port)
    lan_ip = get_lan_ip()

    local_url = f"http://localhost:{port}/"
    lan_url = f"http://{lan_ip}:{port}/"

    print("[INFO] 即将启动分拣进度实时看板...")
    print(f"[INFO] 本机访问: {local_url}")
    print(f"[INFO] 手机(同局域网)访问: {lan_url}")
    print("[INFO] 如手机不通，请在电脑终端执行 ipconfig，确认 IPv4 地址。")

    # 修正自动弹出的浏览器地址为可访问的 LAN/本机地址
    open_addr = lan_ip if lan_ip and lan_ip != "127.0.0.1" else "localhost"
    os.environ["STREAMLIT_BROWSER_SERVER_ADDRESS"] = open_addr
    os.environ["STREAMLIT_BROWSER_SERVER_PORT"] = str(port)

    cmd = [
        "streamlit", "run", app_path,
        "--server.port", str(port),
        "--server.address", args.bind,
    ]

    # 启动 Streamlit 服务
    proc = subprocess.Popen(cmd)

    # 等待服务就绪后提示
    if wait_for_server("localhost", port, timeout=20):
        print("[INFO] 看板已启动 ✅")
    else:
        print("[WARN] 看板端口暂未就绪，稍后在浏览器重试访问。")

    # 将子进程保持前台，便于 Ctrl+C 关闭
    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\n[INFO] 收到中断信号，正在停止看板...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()