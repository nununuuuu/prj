from pydantic import BaseModel, Field

class BacktestRequest(BaseModel):
    ticker: str = Field(default="SPY", description="股票代號")
    ma_short: int = Field(default=10, ge=1, le=100, description="短期均線天數")
    ma_long: int = Field(default=20, ge=5, le=300, description="長期均線天數")
    rsi_period: int = Field(default=14, description="RSI 週期")
    cash: float = Field(default=10000, description="初始資金")

class BacktestResponse(BaseModel):
    return_pct: float
    max_drawdown: float
    win_rate: float
    equity_curve: list[dict] # 格式: [{'time': '2023-01-01', 'value': 10100}, ...]
    trades: list[dict] # 交易紀錄