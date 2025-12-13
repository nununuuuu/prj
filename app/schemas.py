from pydantic import BaseModel
from typing import List, Dict, Optional

class BacktestRequest(BaseModel):
    ticker: str
    start_date: str
    end_date: str
    cash: float = 100000
    ma_short: int = 10
    ma_long: int = 60
    
    # --- RSI 進階設定 (修正預設值) ---
    rsi_period_entry: int = 14    
    rsi_buy_threshold: int = 30   # [修正] 預設改為 30
    
    rsi_period_exit: int = 14     
    rsi_sell_threshold: int = 70  # [修正] 預設改為 70

    buy_fee_pct: float = 0.1425
    sell_fee_pct: float = 0.4425
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0

class BacktestResponse(BaseModel):
    ticker: str
    final_equity: float
    total_return: float
    annual_return: float
    buy_and_hold_return: float
    win_rate: float
    total_trades: int
    avg_pnl: float
    max_consecutive_loss: int
    
    equity_curve: List[Dict]
    price_data: List[Dict]
    trades: List[Dict]
    detailed_trades: Optional[List[Dict]] = [] 
    heatmap_data: Dict[int, Dict[int, float]]
    buy_and_hold_curve: List[Dict]