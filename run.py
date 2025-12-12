import uvicorn
import webbrowser
import threading
import time
import sys
import os

def start_browser():
    """等待 1.5 秒讓 Server 啟動後，自動開啟預設瀏覽器"""
    time.sleep(1.5)
    url = "http://127.0.0.1:8000"
    print(f"正在開啟瀏覽器: {url}")
    webbrowser.open(url)

if __name__ == "__main__":
    # 將當前目錄加入 Python 路徑，確保能找到 app 套件
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))

    # 建立一個背景執行緒來開瀏覽器 (daemon=True 代表主程式結束它也會跟著結束)
    threading.Thread(target=start_browser, daemon=True).start()

    # 啟動 Server
    print("正在啟動 ..")
    
    # 注意：這裡的 app.main:app 對應你的資料夾結構
    # reload=True 讓你在修改程式碼時會自動更新，但在這個腳本中瀏覽器只會開一次
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)