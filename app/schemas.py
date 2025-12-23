from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class BacktestRequest(BaseModel):
    ticker: str
    start_date: str
    end_date: str
    cash: float = Field(default=100000, gt=0, description="Initial cash")
    
    # --- 交易成本 ---
    buy_fee_pct: float = Field(default=0.1425, ge=0, le=10, description="Buy fee percentage")
    sell_fee_pct: float = Field(default=0.4425, ge=0, le=10, description="Sell fee percentage")
    
    # --- 模式選擇 ---
    # 基礎 or 進階
    strategy_mode: str = "basic" 

    # --- 定期定額 ---
    monthly_contribution_amount: float = Field(default=0.0, ge=0, description="Monthly contribution amount")
    monthly_contribution_fee: float = Field(default=1.0, ge=0, description="Monthly contribution fixed fee")
    monthly_contribution_days: List[int] = Field(default=[], description="Days of month to contribute (1-28)")

    # --- 基礎模式參數 ---
    ma_short: int = 10
    ma_long: int = 60
    rsi_period_entry: int = 14    
    rsi_buy_threshold: int = 70   
    rsi_period_exit: int = 14     
    rsi_sell_threshold: int = 80  
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0
    trailing_stop_pct: float = 0.0 

    # --- 進階模式參數 ---
    # 策略名稱
    entry_strategy_1: Optional[str] = None
    entry_params_1: Dict[str, float] = {}
    
    entry_strategy_2: Optional[str] = None
    entry_params_2: Dict[str, float] = {}
    
    exit_strategy_1: Optional[str] = None
    exit_params_1: Dict[str, float] = {}
    
    exit_strategy_2: Optional[str] = None
    exit_params_2: Dict[str, float] = {}

class BacktestResponse(BaseModel):
    ticker: str
    final_equity: float
    total_return: float
    annual_return: float
    buy_and_hold_return: float
    win_rate: float
    winning_trades: int
    total_trades: int
    avg_pnl: float
    max_consecutive_loss: int
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    profit_factor: float

    pnl_histogram: Dict[str, List] 
    equity_curve: List[Dict]
    roi_curve: List[Dict] # 新增 ROI 曲線 (針對定期定額正確計算)
    drawdown_curve: List[Dict]
    price_data: List[Dict]
    trades: List[Dict]
    detailed_trades: Optional[List[Dict]] = [] 
    heatmap_data: Dict[int, Dict[int, float]]
    buy_and_hold_curve: List[Dict]