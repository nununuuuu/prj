from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from backtesting import Backtest
import pandas as pd
import os
from .strategy import SmaRsiStrategy
from .schemas import BacktestRequest, BacktestResponse

app = FastAPI(title="Smart Quant Dashboard")

# 設定路徑
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# 讀取數據 (建議放在全域變數或快取，避免每次讀檔)
# 這裡假設你有一個 SPY.csv 在 data 資料夾
DATA_PATH = os.path.join(BASE_DIR, "data", "SPY.csv")
def get_data():
    if os.path.exists(DATA_PATH):
        df = pd.read_csv(DATA_PATH, index_col=0, parse_dates=True)
        return df
    # 如果沒有檔案，可以使用 yfinance 下載 (Demo 時建議先下載好)
    import yfinance as yf
    return yf.download("SPY", start="2020-01-01", end="2023-12-31")

@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.post("/api/backtest", response_model=BacktestResponse)
def run_backtest(params: BacktestRequest):
    df = get_data()
    
    # 初始化回測，動態傳入參數
    bt = Backtest(df, SmaRsiStrategy, cash=params.cash, commission=.002)
    
    stats = bt.run(
        n1=params.ma_short, 
        n2=params.ma_long, 
        n_rsi=params.rsi_period
    )
    
    # 處理回傳數據
    equity_curve = stats._equity_curve  # 這是 backtesting.py 的內部數據
    equity_list = []
    for time, value in zip(equity_curve.index, equity_curve['Equity']):
        equity_list.append({"time": time.strftime("%Y-%m-%d"), "value": value})
        
    return {
        "return_pct": round(stats["Return [%]"], 2),
        "max_drawdown": round(stats["Max. Drawdown [%]"], 2),
        "win_rate": round(stats["Win Rate [%]"], 2),
        "equity_curve": equity_list, # 只取部分點數避免前端過重，或全部傳
        "trades": [] # 簡化起見先略過詳細交易列表
    }