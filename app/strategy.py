from backtesting import Strategy
from backtesting.lib import crossover

def SMA(values, n):
    """簡單移動平均線輔助函式"""
    import pandas as pd
    return pd.Series(values).rolling(n).mean()

def RSI(values, n):
    """RSI 相對強弱指標輔助函式 (使用 pandas 簡易實作以防無 talib)"""
    import pandas as pd
    delta = pd.Series(values).diff()
    gain = (delta.where(delta > 0, 0)).rolling(n).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(n).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

class SmaRsiStrategy(Strategy):
    # 定義可調整參數 (這些將由網頁前端傳入)
    n1 = 10  # 短期均線
    n2 = 20  # 長期均線
    n_rsi = 14 # RSI 週期
    rsi_upper = 70 # RSI 超買界線

    def init(self):
        # 計算指標
        self.sma1 = self.I(SMA, self.data.Close, self.n1)
        self.sma2 = self.I(SMA, self.data.Close, self.n2)
        self.rsi = self.I(RSI, self.data.Close, self.n_rsi)

    def next(self):
        # 進場邏輯：黃金交叉 且 RSI 沒有過熱
        if crossover(self.sma1, self.sma2) and self.rsi[-1] < self.rsi_upper:
            self.buy()
        
        # 出場邏輯：死亡交叉
        elif crossover(self.sma2, self.sma1):
            self.position.close()