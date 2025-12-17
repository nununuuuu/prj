from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from backtesting import Backtest
import pandas as pd
import yfinance as yf
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import traceback
import numpy as np
import math
import os

# --- 相容性補丁 ---
if not hasattr(pd.Series, 'iteritems'):
    pd.Series.iteritems = pd.Series.items
if not hasattr(np, 'float'):
    np.float = float
# ----------------

from .strategy import UniversalStrategy
from .schemas import BacktestRequest, BacktestResponse

app = FastAPI()

# 設定路徑
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

def safe_num(value, decimal=2):
    try:
        if hasattr(value, "item"): value = value.item()
        if pd.isna(value) or math.isnan(value) or np.isinf(value): return 0.0
        return round(float(value), decimal)
    except Exception:
        return 0.0

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"[CRITICAL ERROR] {str(exc)}")
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"detail": f"Server Error: {str(exc)}"})

@lru_cache(maxsize=64)
def _download_from_yahoo(ticker: str, start: str, end: str):
    print(f"[YFinance] 下載: {ticker}")
    try:
        return yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
    except Exception:
        return pd.DataFrame()

async def get_yfinance_data(ticker: str, start: str, end: str):
    ticker = ticker.upper().strip()
    if ticker.isdigit() or (len(ticker) == 4 and ticker.isdigit()): ticker += ".TW"
    
    loop = asyncio.get_event_loop()
    try:
        df = await loop.run_in_executor(None, _download_from_yahoo, ticker, start, end)
        if df is None or df.empty: return None, ticker
        
        if isinstance(df.columns, pd.MultiIndex): 
            df.columns = df.columns.get_level_values(0)
        
        df.columns = [c if isinstance(c, str) else c[0] for c in df.columns]

        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        if 'Adj Close' in df.columns and 'Close' not in df.columns: df.rename(columns={'Adj Close': 'Close'}, inplace=True)
        
        required = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in df.columns for col in required): return None, ticker
        
        df = df.ffill().bfill()
        
        csv_path = DATA_DIR / f"{ticker}.csv"
        df.to_csv(csv_path)
        
        return df, ticker
    except Exception as e:
        print(f"數據處理錯誤: {e}")
        return None, ticker

@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

def get_indicator_note(strategy, strat_name, strat_params, idx):
    if not strat_name: return ""
    try:
        if 'SMA' in strat_name:
            n_s = int(strat_params.get('n_short', 0))
            n_l = int(strat_params.get('n_long', 0))
            val_s = getattr(strategy, f"SMA_{n_s}", [])
            val_l = getattr(strategy, f"SMA_{n_l}", [])
            v1 = safe_num(val_s[idx]) if len(val_s) > idx else 0
            v2 = safe_num(val_l[idx]) if len(val_l) > idx else 0
            return f"SMA({n_s}):{v1} / SMA({n_l}):{v2}"
            
        elif 'RSI' in strat_name:
            p = int(strat_params.get('period', 14))
            val = getattr(strategy, f"RSI_{p}", [])
            v = safe_num(val[idx]) if len(val) > idx else 0
            return f"RSI({p}):{v}"
            
        elif 'MACD' in strat_name:
            p_f = int(strat_params.get('fast', 12))
            p_s = int(strat_params.get('slow', 26))
            p_sig = int(strat_params.get('signal', 9))
            key = f"MACD_{p_f}_{p_s}_{p_sig}"
            if hasattr(strategy, key):
                macd_data = getattr(strategy, key)
                m_val = safe_num(macd_data[0][idx]) if len(macd_data[0]) > idx else 0
                s_val = safe_num(macd_data[1][idx]) if len(macd_data[1]) > idx else 0
                return f"MACD:{m_val} / Sig:{s_val}"
                
        elif 'KD' in strat_name:
            p = int(strat_params.get('period', 9))
            key = f"KD_{p}"
            if hasattr(strategy, key):
                kd_data = getattr(strategy, key)
                k_val = safe_num(kd_data[0][idx]) if len(kd_data[0]) > idx else 0
                d_val = safe_num(kd_data[1][idx]) if len(kd_data[1]) > idx else 0
                return f"K:{k_val} / D:{d_val}"

        elif 'BB' in strat_name:
            p = int(strat_params.get('period', 20))
            std = strat_params.get('std', 2.0)
            key = f"BB_{p}_{std}"
            if hasattr(strategy, key):
                bb_data = getattr(strategy, key)
                u_val = safe_num(bb_data[0][idx]) if len(bb_data[0]) > idx else 0
                l_val = safe_num(bb_data[1][idx]) if len(bb_data[1]) > idx else 0
                return f"Upper:{u_val} / Lower:{l_val}"

    except Exception:
        return ""
    return strat_name

@app.post("/api/backtest", response_model=BacktestResponse)
async def run_backtest(params: BacktestRequest):
    df, real_ticker = await get_yfinance_data(params.ticker, params.start_date, params.end_date)
    
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="找不到數據")

    min_bars = 60
    if len(df) < min_bars:
        raise HTTPException(status_code=400, detail=f"數據不足 {min_bars} 筆")

    bt = Backtest(
        df, 
        UniversalStrategy, 
        cash=params.cash, 
        commission=((params.buy_fee_pct + params.sell_fee_pct)/2)/100
    )
    
    strat_kwargs = {
        'mode': params.strategy_mode,
        'sl_pct': params.stop_loss_pct,
        'tp_pct': params.take_profit_pct,
        'trailing_stop_pct': params.trailing_stop_pct 
    }

    if params.strategy_mode == 'basic':
        strat_kwargs.update({
            'n1': params.ma_short,
            'n2': params.ma_long,
            'n_rsi_entry': params.rsi_period_entry,
            'rsi_buy_threshold': params.rsi_buy_threshold,
            'n_rsi_exit': params.rsi_period_exit,
            'rsi_sell_threshold': params.rsi_sell_threshold
        })
    else:
        entry_conf = []
        if params.entry_strategy_1: entry_conf.append({'type': params.entry_strategy_1, 'params': params.entry_params_1})
        if params.entry_strategy_2: entry_conf.append({'type': params.entry_strategy_2, 'params': params.entry_params_2})
        
        exit_conf = []
        if params.exit_strategy_1: exit_conf.append({'type': params.exit_strategy_1, 'params': params.exit_params_1})
        if params.exit_strategy_2: exit_conf.append({'type': params.exit_strategy_2, 'params': params.exit_params_2})
        
        strat_kwargs.update({
            'entry_config': entry_conf,
            'exit_config': exit_conf
        })

    stats = bt.run(**strat_kwargs)
    
    equity_curve = stats._equity_curve
    trades_df = stats._trades
    strategy = stats._strategy
    
    # 計算獲利交易次數
    winning_trades = len(trades_df[trades_df['PnL'] > 0]) if not trades_df.empty else 0

    # 計算水下曲線
    drawdown_list = []
    if not equity_curve.empty:
        equity_series = equity_curve['Equity']
        running_max = equity_series.cummax()
        drawdown_series = (equity_series - running_max) / running_max * 100
        drawdown_list = [{"time": t.strftime("%Y-%m-%d"), "value": safe_num(v)} for t, v in zip(drawdown_series.index, drawdown_series)]

    # 計算損益分佈直方圖 (PnL Histogram)
    pnl_hist_data = {"labels": [], "values": [], "colors": []}
    if not trades_df.empty:
        returns = trades_df['ReturnPct'] * 100
        returns = returns.replace([np.inf, -np.inf], np.nan).dropna()
        if len(returns) > 0:
            counts, bin_edges = np.histogram(returns, bins='auto')
            for i in range(len(counts)):
                lower = round(bin_edges[i], 1)
                upper = round(bin_edges[i+1], 1)
                label = f"{lower}% ~ {upper}%"
                center = (lower + upper) / 2
                color = "#10b981" if center >= 0 else "#ef4444"
                pnl_hist_data["labels"].append(label)
                pnl_hist_data["values"].append(int(counts[i]))
                pnl_hist_data["colors"].append(color)

    # 準備 B&H 曲線
    bh_list = []
    if len(df) > 0:
        first = df['Close'].iloc[0]
        if first > 0:
            bh_vals = (df['Close'] / first) * params.cash
            bh_list = [{"time": t.strftime("%Y-%m-%d"), "value": safe_num(v)} for t, v in zip(bh_vals.index, bh_vals)]
            
    equity_list = [{"time": t.strftime("%Y-%m-%d"), "value": safe_num(v)} for t, v in zip(equity_curve.index, equity_curve['Equity'])]
    price_list = [{"time": t.strftime("%Y-%m-%d"), "value": safe_num(v)} for t, v in zip(df.index, df['Close'])]
    
    detailed_trades = []
    chart_trades = []
    
    max_consecutive_loss = 0
    current_loss = 0

    if not trades_df.empty:
        for i, row in trades_df.iterrows():
            e_idx, x_idx = int(row['EntryBar']), int(row['ExitBar'])
            
            entry_note = ""
            exit_note = ""

            if params.strategy_mode == 'basic':
                try:
                    e_rsi = safe_num(strategy.rsi_entry[e_idx]) if len(strategy.rsi_entry) > e_idx else 0
                    e_sma1 = safe_num(strategy.sma1[e_idx]) if len(strategy.sma1) > e_idx else 0
                    e_sma2 = safe_num(strategy.sma2[e_idx]) if len(strategy.sma2) > e_idx else 0
                    
                    x_rsi = safe_num(strategy.rsi_exit[x_idx]) if len(strategy.rsi_exit) > x_idx else 0
                    x_sma1 = safe_num(strategy.sma1[x_idx]) if len(strategy.sma1) > x_idx else 0
                    x_sma2 = safe_num(strategy.sma2[x_idx]) if len(strategy.sma2) > x_idx else 0
                    
                    entry_note = f"SMA: {e_sma1}/{e_sma2} | RSI: {e_rsi}"
                    exit_note = f"SMA: {x_sma1}/{x_sma2} | RSI: {x_rsi}"
                except: pass
            else:
                e_notes_list = []
                n1 = get_indicator_note(strategy, params.entry_strategy_1, params.entry_params_1, e_idx)
                if n1: e_notes_list.append(n1)
                n2 = get_indicator_note(strategy, params.entry_strategy_2, params.entry_params_2, e_idx)
                if n2: e_notes_list.append(n2)
                entry_note = " | ".join(e_notes_list)

                x_notes_list = []
                n1 = get_indicator_note(strategy, params.exit_strategy_1, params.exit_params_1, x_idx)
                if n1: x_notes_list.append(n1)
                n2 = get_indicator_note(strategy, params.exit_strategy_2, params.exit_params_2, x_idx)
                if n2: x_notes_list.append(n2)
                exit_note = " | ".join(x_notes_list)

            detailed_trades.append({
                "entry_date": row['EntryTime'].strftime("%Y-%m-%d"),
                "exit_date": row['ExitTime'].strftime("%Y-%m-%d"),
                "entry_price": safe_num(row['EntryPrice']),
                "exit_price": safe_num(row['ExitPrice']),
                "size": int(abs(row['Size'])),
                "pnl": safe_num(row['PnL'], 0),
                "return_pct": safe_num(row['ReturnPct'] * 100),
                "entry_note": entry_note, 
                "exit_note": exit_note
            })

            chart_trades.append({"time": row['EntryTime'].strftime("%Y-%m-%d"), "price": safe_num(row['EntryPrice']), "type": "buy"})
            chart_trades.append({"time": row['ExitTime'].strftime("%Y-%m-%d"), "price": safe_num(row['ExitPrice']), "type": "sell"})

            if row['PnL'] < 0:
                current_loss += 1
                max_consecutive_loss = max(max_consecutive_loss, current_loss)
            else:
                current_loss = 0

    heatmap_data = {}
    if not equity_curve.empty:
        eq_df = pd.DataFrame(equity_curve['Equity'])
        m_df = eq_df.resample('ME').last() if hasattr(eq_df, 'resample') else eq_df
        m_df['Return'] = m_df['Equity'].pct_change() * 100
        for date, row in m_df.iterrows():
            if not (pd.isna(row['Return']) or np.isinf(row['Return'])):
                if date.year not in heatmap_data: heatmap_data[date.year] = {}
                heatmap_data[date.year][date.month] = safe_num(row['Return'])

    return {
        "ticker": real_ticker,
        "final_equity": safe_num(stats["Equity Final [$]"], 0),
        "total_return": safe_num(stats["Return [%]"]),
        "annual_return": safe_num(stats["Return (Ann.) [%]"]),
        "buy_and_hold_return": safe_num(stats["Buy & Hold Return [%]"]),
        "win_rate": safe_num(stats["Win Rate [%]"]),
        "winning_trades": winning_trades,
        "profit_factor": safe_num(stats.get("Profit Factor", 0)),
        "total_trades": int(stats["# Trades"]),
        "avg_pnl": safe_num(trades_df['PnL'].mean(), 0) if not trades_df.empty else 0,
        "max_consecutive_loss": max_consecutive_loss,
        "max_drawdown": safe_num(stats["Max. Drawdown [%]"]),
        "sharpe_ratio": safe_num(stats["Sharpe Ratio"]),
        "equity_curve": equity_list,
        "drawdown_curve": drawdown_list,
        "pnl_histogram": pnl_hist_data,  
        "price_data": price_list,
        "trades": chart_trades,
        "heatmap_data": heatmap_data,
        "buy_and_hold_curve": bh_list,
        "detailed_trades": detailed_trades
    }