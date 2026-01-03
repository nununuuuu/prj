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

if not hasattr(pd.Series, 'iteritems'):
    pd.Series.iteritems = pd.Series.items
if not hasattr(np, 'float'):
    np.float = float

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

        elif 'WILLR' in strat_name:
            p = int(strat_params.get('period', 14))
            val = getattr(strategy, f"WILLR_{p}", [])
            v = safe_num(val[idx]) if len(val) > idx else 0
            return f"W%R({p}):{v}"

        elif 'TURTLE' in strat_name:
            p = int(strat_params.get('period', 20))
            # 判斷是進場(High)還是出場(Low)
            if 'ENTRY' in strat_name:
                key = f"DONCHIAN_HIGH_{p}"
                prefix = "High"
            else:
                key = f"DONCHIAN_LOW_{p}"
                prefix = "Low"
            
            if hasattr(strategy, key):
                val = getattr(strategy, key)
                v = safe_num(val[idx]) if len(val) > idx else 0
                return f"{prefix}({p}):{v}"

    except Exception:
        return ""
    return strat_name


@app.post("/api/shutdown")
def shutdown_event():
    import os
    import threading
    import time
    import psutil
    
    def kill():
        print("使用者請求關閉系統，正在終止伺服器...")
        time.sleep(0.5)
        
        try:
            # 獲取當前進程 (子進程)
            current_process = psutil.Process(os.getpid())
            # 嘗試獲取父進程 (Uvicorn Watcher)
            parent = current_process.parent()
            
            # 如果有父進程，先殺父進程
            if parent:
                print(f"正在結束主程序 (PID: {parent.pid})...")
                parent.terminate()
        except Exception as e:
            print(f"關閉主程序時發生錯誤: {e}")

        # 最後強制結束自己
        os._exit(0)
        
    threading.Thread(target=kill).start()
    return {"message": "系統正在關閉..."}

@app.post("/api/backtest", response_model=BacktestResponse)
async def run_backtest(params: BacktestRequest):
    df, real_ticker = await get_yfinance_data(params.ticker, params.start_date, params.end_date)
    
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="找不到數據")

    min_bars = 60
    if len(df) < min_bars:
        raise HTTPException(status_code=400, detail=f"數據不足 {min_bars} 筆")

    # 清除可能的 NaN 值，避免 Backtesting 引擎崩潰
    if df.isnull().values.any():
        df = df.dropna()
    
    # 二次檢查長度
    if len(df) < min_bars:
        raise HTTPException(status_code=400, detail=f"有效數據不足 {min_bars} 筆 (含空值)")

    # 計算手續費率 (Backtesting 僅支援單一費率，故取平均)
    # 若為定期定額模式，因我們將在 Strategy 中手動扣除定額手續費，故將 Backtest 手續費設為 0
    if params.strategy_mode == 'periodic':
         commission_rate_for_bt = 0.0
         commission_rate_param = 0.0 # 雖然 Strategy 內部不使用百分比費率，但保持從屬性傳遞一致性
    else:
         commission_rate_for_bt = ((params.buy_fee_pct + params.sell_fee_pct)/2)/100
         commission_rate_param = commission_rate_for_bt

    bt = Backtest(
        df, 
        UniversalStrategy, 
        cash=params.cash, 
        commission=commission_rate_for_bt,
        exclusive_orders=True if params.strategy_mode != 'periodic' else False,
        trade_on_close=True if params.strategy_mode == 'periodic' else False, 
        margin=0.05 if params.strategy_mode == 'periodic' else 1.0 
    )
    
    strat_kwargs = {
        'mode': params.strategy_mode,
        'sl_pct': params.stop_loss_pct,
        'tp_pct': params.take_profit_pct,
        'trailing_stop_pct': params.trailing_stop_pct,
        'monthly_contribution_amount': params.monthly_contribution_amount,
        'monthly_contribution_fee': params.monthly_contribution_fee,
        'monthly_contribution_days': params.monthly_contribution_days,
        'commission_rate': commission_rate_param 
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
    elif params.strategy_mode == 'advanced':
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

    # --- 修正報酬率計算 (針對定期定額) & 產生 ROI 曲線 ---
    invested_series = []
    current_invested = params.cash
    
    if params.monthly_contribution_amount > 0 and params.monthly_contribution_days:
        last_m = -1
        dep_set = set()
        for ts in df.index:
            m = ts.month
            d = ts.day
            if m != last_m:
                dep_set = set()
                last_m = m
            
            for t_day in params.monthly_contribution_days:
                if d >= t_day and t_day not in dep_set:
                    current_invested += params.monthly_contribution_amount
                    dep_set.add(t_day)
            
            invested_series.append(current_invested)
    else:
        invested_series = [params.cash] * len(df)
    
    total_invested = invested_series[-1] if invested_series else params.cash
    final_equity = stats["Equity Final [$]"]
    
    # 重新計算總報酬率
    adjusted_return = ((final_equity - total_invested) / total_invested) * 100
    
    equity_curve = stats._equity_curve

    # 準備 ROI 曲線數據 (時間序列)
    roi_list = []
    if not equity_curve.empty and len(equity_curve) == len(invested_series):
        roi_vals = (equity_curve['Equity'] - invested_series) / invested_series * 100
        roi_list = [{"time": t.strftime("%Y-%m-%d"), "value": safe_num(v)} for t, v in zip(equity_curve.index, roi_vals)]
    else:
        roi_list = [{"time": t.strftime("%Y-%m-%d"), "value": safe_num((v - params.cash)/params.cash*100)} for t, v in zip(equity_curve.index, equity_curve['Equity'])]

    equity_list = [{"time": t.strftime("%Y-%m-%d"), "value": safe_num(v)} for t, v in zip(equity_curve.index, equity_curve['Equity'])]
    
    # B&H Logic...
    trades_df = stats._trades
    strategy = stats._strategy

    extra_trades = []
    if params.strategy_mode == 'periodic' and hasattr(strategy, 'order_log'):
        for log in strategy.order_log:
            extra_trades.append({
                "time": log['time'].strftime("%Y-%m-%d"),
                "type": "buy",
                "price": log['price'],
                "size": 0, 
                "pnl": 0
            })
            
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
            
            elif params.strategy_mode == 'periodic':
                entry_note = "定期定額買入"
                exit_note = "期末結算" if x_idx >= len(df)-2 else "定期定額" 

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

    if extra_trades:
        chart_trades.extend(extra_trades)
        
        for et in extra_trades:
             detailed_trades.append({
                "entry_date": et['time'],
                "exit_date": "-",
                "entry_price": safe_num(et['price']),
                "exit_price": "-",
                "size": 0,
                "pnl": 0,
                "return_pct": 0,
                "entry_note": "定期定額",
                "exit_note": "-"
             })
             

    detailed_trades.sort(key=lambda x: str(x['entry_date']))

    heatmap_data = {}
    if not equity_curve.empty:
        eq_df = pd.DataFrame(equity_curve['Equity'])
        m_df = eq_df.resample('ME').last() if hasattr(eq_df, 'resample') else eq_df
        m_df['Return'] = m_df['Equity'].pct_change() * 100
        for date, row in m_df.iterrows():
            if not (pd.isna(row['Return']) or np.isinf(row['Return'])):
                if date.year not in heatmap_data: heatmap_data[date.year] = {}
                heatmap_data[date.year][date.month] = safe_num(row['Return'])


    lump_sum_bh_return_pct = stats["Buy & Hold Return [%]"]

    return {
        "ticker": real_ticker,
        "final_equity": safe_num(stats["Equity Final [$]"], 0),
        "total_invested": safe_num(total_invested), 
        "total_return": safe_num(adjusted_return),
        "annual_return": safe_num(stats["Return (Ann.) [%]"]),
        "buy_and_hold_return": safe_num(lump_sum_bh_return_pct), 
        "win_rate": safe_num(stats["Win Rate [%]"]),
        "winning_trades": winning_trades,
        "profit_factor": safe_num(stats.get("Profit Factor", 0)),
        "total_trades": int(stats["# Trades"]),
        "avg_pnl": safe_num(trades_df['PnL'].mean(), 0) if not trades_df.empty else 0,
        "max_consecutive_loss": max_consecutive_loss,
        "max_drawdown": safe_num(stats["Max. Drawdown [%]"]),
        "sharpe_ratio": safe_num(stats["Sharpe Ratio"]),
        "equity_curve": equity_list,
        "roi_curve": roi_list,
        "drawdown_curve": drawdown_list,
        "pnl_histogram": pnl_hist_data,  
        "price_data": price_list,
        "trades": chart_trades,
        "heatmap_data": heatmap_data,
        "buy_and_hold_curve": bh_list,
        "detailed_trades": detailed_trades
    }