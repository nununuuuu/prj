from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class BacktestRequest(BaseModel):
    ticker: str
    start_date: str
    end_date: str
    cash: float = 100000
    ma_short: int = 10
    ma_long: int = 20
    rsi_period: int = 14
    buy_fee_pct: float = 0.1425
    sell_fee_pct: float = 0.4425
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0

class BacktestResponse(BaseModel):
    ticker: str
    # --- 核心指標 (對應您的截圖) ---
    final_equity: float       # 最終資產
    total_return: float       # 總報酬率
    annual_return: float      # 年化報酬率
    buy_and_hold_return: float # 買入持有報酬率
    win_rate: float           # 勝率
    total_trades: int         # 總交易次數
    avg_pnl: float            # 平均交易盈虧 (金額)
    max_consecutive_loss: int # 最大連虧次數
    
    # --- 圖表數據 ---
    equity_curve: List[Dict]  # 資金曲線
    price_data: List[Dict]    # 股價走勢 (畫背景用)
    trades: List[Dict]        # 交易點位 (畫買賣點用)
    heatmap_data: Dict[int, Dict[int, float]] # 熱力圖數據 {Year: {Month: Return}}
    buy_and_hold_curve: List[Dict]