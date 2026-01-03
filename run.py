import uvicorn
import webbrowser
import threading
import time
import sys
import os
import psutil
import socket

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def kill_process_on_port(port):
    """殺死佔用指定端口的進程"""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            for conn in proc.connections(kind='inet'):
                if conn.laddr.port == port:
                    print(f"發現端口 {port} 被 {proc.info['name']} (PID: {proc.info['pid']}) 佔用，正在關閉...")
                    proc.terminate()
                    proc.wait(timeout=3)
                    print("已成功釋放端口。")
                    return
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

def start_browser():
    """等待 2 秒讓 Server 啟動後，自動開啟預設瀏覽器"""
    time.sleep(2)
    url = "http://127.0.0.1:8000"
    print(f"正在開啟瀏覽器: {url}")
    webbrowser.open(url)

if __name__ == "__main__":
    # 確保端口乾淨
    if is_port_in_use(8000):
        try:
            kill_process_on_port(8000)
            # 稍作等待確保系統釋放資源
            time.sleep(1)
        except Exception as e:
            print(f"警告：無法清理端口 8000: {e}")
            print("嘗試直接啟動...")

    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    threading.Thread(target=start_browser, daemon=True).start()
    print("正在啟動 ..")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)