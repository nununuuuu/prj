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
    try:
        df, real_ticker = get_yfinance_data(params.ticker, params.start_date, params.end_date)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail="無數據")

        avg_commission = ((params.buy_fee_pct + params.sell_fee_pct) / 2) / 100
        bt = Backtest(df, SmaRsiStrategy, cash=params.cash, commission=avg_commission)
        
        # 執行回測 (移除 use_death_cross)
        stats = bt.run(
            n1=params.ma_short, 
            n2=params.ma_long, 
            n_rsi=params.rsi_period,
            rsi_overbought=params.rsi_overbought,
            sl_pct=params.stop_loss_pct,
            tp_pct=params.take_profit_pct
        )
        
        # ... (Equity Curve, Buy&Hold 處理保持不變) ...
        equity_curve = stats._equity_curve
        bh_list = []
        if len(df) > 0:
            first_price = df['Close'].iloc[0]
            if first_price > 0:
                bh_equity_series = (df['Close'] / first_price) * params.cash
                bh_list = [{"time": t.strftime("%Y-%m-%d"), "value": v} for t, v in zip(bh_equity_series.index, bh_equity_series)]
        
        equity_list = [{"time": t.strftime("%Y-%m-%d"), "value": v} for t, v in zip(equity_curve.index, equity_curve['Equity'])]
        price_list = [{"time": t.strftime("%Y-%m-%d"), "value": v} for t, v in zip(df.index, df['Close'])]
        
        # =========================================
        #   生成詳細交易紀錄 (包含 RSI, SMA 數值)
        # =========================================
        trades_df = stats._trades
        detailed_trades = [] # 這是要傳給前端列表用的
        
        # 從策略實例中取得指標陣列
        strategy = stats._strategy
        rsi_arr = strategy.rsi
        sma1_arr = strategy.sma1
        sma2_arr = strategy.sma2
        
        # 計算最大連虧
        max_consecutive_loss = 0
        current_loss = 0

        if not trades_df.empty:
            for i, row in trades_df.iterrows():
                # 取得索引位置
                entry_idx = row['EntryBar']
                exit_idx = row['ExitBar']
                
                # 安全地取得數值 (防止索引越界)
                entry_rsi = rsi_arr[entry_idx] if entry_idx < len(rsi_arr) else 0
                
                # 出場時的均線 (用於顯示死叉狀態)
                exit_sma1 = sma1_arr[exit_idx] if exit_idx < len(sma1_arr) else 0
                exit_sma2 = sma2_arr[exit_idx] if exit_idx < len(sma2_array) else 0 # 注意這裡要用 sma2_arr

                # 建立詳細物件
                detailed_trades.append({
                    "entry_date": row['EntryTime'].strftime("%Y-%m-%d"),
                    "exit_date": row['ExitTime'].strftime("%Y-%m-%d"),
                    "entry_price": round(row['EntryPrice'], 2),
                    "exit_price": round(row['ExitPrice'], 2),
                    "size": int(abs(row['Size'])),
                    "pnl": round(row['PnL'], 0),
                    "return_pct": round(row['ReturnPct'] * 100, 2),
                    # 指標數據
                    "entry_rsi": round(entry_rsi, 2),
                    "exit_sma_short": round(exit_sma1, 2),
                    "exit_sma_long": round(exit_sma2, 2)
                })

                if row['PnL'] < 0:
                    current_loss += 1
                    max_consecutive_loss = max(max_consecutive_loss, current_loss)
                else:
                    current_loss = 0

        # 圖表用的簡單交易點
        chart_trades = []
        for i, row in trades_df.iterrows():
             chart_trades.append({"time": row['EntryTime'].strftime("%Y-%m-%d"), "price": row['EntryPrice'], "type": "buy"})
             chart_trades.append({"time": row['ExitTime'].strftime("%Y-%m-%d"), "price": row['ExitPrice'], "type": "sell"})

        # Heatmap 保持不變
        heatmap_data = {}
        if not equity_curve.empty:
            equity_df = pd.DataFrame(equity_curve['Equity'])
            monthly_df = equity_df.resample('ME').last() if hasattr(equity_df, 'resample') else equity_df
            monthly_df['Return'] = monthly_df['Equity'].pct_change() * 100
            for date, row in monthly_df.iterrows():
                if pd.isna(row['Return']): continue
                if date.year not in heatmap_data: heatmap_data[date.year] = {}
                heatmap_data[date.year][date.month] = round(row['Return'], 2)

        return {
            "ticker": real_ticker,
            "final_equity": round(stats["Equity Final [$]"], 0),
            "total_return": round(stats["Return [%]"], 2),
            "annual_return": round(stats["Return (Ann.) [%]"], 2),
            "buy_and_hold_return": round(stats["Buy & Hold Return [%]"], 2),
            "win_rate": round(stats["Win Rate [%]"], 2),
            "total_trades": int(stats["# Trades"]),
            "avg_pnl": round(trades_df['PnL'].mean(), 0) if not trades_df.empty else 0,
            "max_consecutive_loss": max_consecutive_loss,
            "equity_curve": equity_list,
            "price_data": price_list,
            "trades": chart_trades,
            "heatmap_data": heatmap_data,
            "buy_and_hold_curve": bh_list,
            "detailed_trades": detailed_trades # 傳回給前端列表用
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))