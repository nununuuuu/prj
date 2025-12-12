from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from backtesting import Backtest
import pandas as pd
import yfinance as yf
import traceback
import os
from .strategy import SmaRsiStrategy
from .schemas import BacktestRequest, BacktestResponse

app = FastAPI()

# 設定路徑
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

def get_yfinance_data(ticker: str, start: str, end: str):
    """
    智慧抓取數據：自動判斷台股或美股
    """
    download_ticker = ticker.upper().strip()
    
    # 簡單判斷：如果是數字開頭 (如 2330, 0050)，且沒有後綴，預設加上 .TW
    if download_ticker.isdigit() or (len(download_ticker) == 4 and download_ticker.isdigit()):
         download_ticker += ".TW"
    
    print(f"正在下載: {download_ticker} ({start} ~ {end})")
    
    try:
        # 下載數據 (auto_adjust=True 讓回測更準確)
        df = yf.download(download_ticker, start=start, end=end, progress=False, auto_adjust=True)
        
        # 檢查是否為空
        if df.empty:
            return None, download_ticker

        # 處理 yfinance 新版 MultiIndex 問題 (移除 Ticker 層級)
        if isinstance(df.columns, pd.MultiIndex):
            try:
                df.columns = df.columns.get_level_values(0)
            except Exception:
                pass 

        # 確保索引是 Datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        return df, download_ticker
    except Exception as e:
        print(f"下載失敗: {e}")
        return None, download_ticker

@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.post("/api/backtest", response_model=BacktestResponse)
def run_backtest(params: BacktestRequest):
    print(f"收到回測請求: {params.ticker}")
    
    try:
        # 1. 下載數據
        df, real_ticker = get_yfinance_data(params.ticker, params.start_date, params.end_date)
        
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"找不到 {real_ticker} 的數據，請確認代碼或日期範圍。")

        # 資料長度檢查
        if len(df) < params.ma_long:
            raise HTTPException(status_code=400, detail=f"數據筆數不足 ({len(df)} 筆)，無法計算 {params.ma_long} 日均線，請拉長日期範圍。")

        # 2. 計算平均單邊手續費
        avg_commission = ((params.buy_fee_pct + params.sell_fee_pct) / 2) / 100

        # 3. 初始化回測
        bt = Backtest(df, SmaRsiStrategy, cash=params.cash, commission=avg_commission)
        
        # 4. 執行策略
        stats = bt.run(
            n1=params.ma_short, 
            n2=params.ma_long, 
            sl_pct=params.stop_loss_pct,
            tp_pct=params.take_profit_pct
        )
        
        # 5. 整理數據回傳
        equity_curve = stats._equity_curve
        trades = stats._trades
        
        # --- 計算 Buy & Hold (基準線) ---
        bh_list = []
        if len(df) > 0:
            first_price = df['Close'].iloc[0]
            if first_price > 0:
                bh_equity_series = (df['Close'] / first_price) * params.cash
                bh_list = [{"time": t.strftime("%Y-%m-%d"), "value": v} for t, v in zip(bh_equity_series.index, bh_equity_series)]

        # --- 格式化數據 ---
        equity_list = [{"time": t.strftime("%Y-%m-%d"), "value": v} for t, v in zip(equity_curve.index, equity_curve['Equity'])]
        price_list = [{"time": t.strftime("%Y-%m-%d"), "value": v} for t, v in zip(df.index, df['Close'])]

        # --- 整理交易紀錄 ---
        trade_list = []
        max_consecutive_loss = 0
        current_loss = 0
        
        if not trades.empty:
            for i, row in trades.iterrows():
                trade_list.append({
                    "time": row['EntryTime'].strftime("%Y-%m-%d"),
                    "price": row['EntryPrice'],
                    "type": "buy"
                })
                trade_list.append({
                    "time": row['ExitTime'].strftime("%Y-%m-%d"),
                    "price": row['ExitPrice'],
                    "type": "sell"
                })
                # 連虧計算
                if row['PnL'] < 0:
                    current_loss += 1
                    max_consecutive_loss = max(max_consecutive_loss, current_loss)
                else:
                    current_loss = 0

        # --- 計算熱力圖 (這是您報錯的地方) ---
        heatmap_data = {}  # <--- 關鍵修復：這裡必須先初始化為空字典
        
        if not equity_curve.empty:
            equity_df = pd.DataFrame(equity_curve['Equity'])
            # 使用 ME 代表 Month End
            monthly_df = equity_df.resample('ME').last()
            monthly_df['Return'] = monthly_df['Equity'].pct_change() * 100
            
            for date, row in monthly_df.iterrows():
                val = row['Return']
                if pd.isna(val): continue
                if date.year not in heatmap_data: heatmap_data[date.year] = {}
                heatmap_data[date.year][date.month] = round(val, 2)

        # 6. 回傳結果
        return {
            "ticker": real_ticker,
            "final_equity": round(stats["Equity Final [$]"], 0),
            "total_return": round(stats["Return [%]"], 2),
            "annual_return": round(stats["Return (Ann.) [%]"], 2),
            "buy_and_hold_return": round(stats["Buy & Hold Return [%]"], 2),
            "win_rate": round(stats["Win Rate [%]"], 2),
            "total_trades": int(stats["# Trades"]),
            "avg_pnl": round(trades['PnL'].mean(), 0) if not trades.empty else 0,
            "max_consecutive_loss": max_consecutive_loss,
            "equity_curve": equity_list,
            "price_data": price_list,
            "trades": trade_list,
            "heatmap_data": heatmap_data,
            "buy_and_hold_curve": bh_list
        }

    except Exception as e:
        # 印出詳細錯誤到終端機
        print("後端發生嚴重錯誤:")
        traceback.print_exc()
        # 回傳 500 錯誤給前端顯示
        raise HTTPException(status_code=500, detail=f"後端運算錯誤: {str(e)}")