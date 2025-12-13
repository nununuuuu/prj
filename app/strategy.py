# app/strategy.py
from backtesting import Strategy
from backtesting.lib import crossover
import pandas as pd

def SMA(values, n):
    return pd.Series(values).rolling(n).mean()

def RSI(values, n):
    delta = pd.Series(values).diff()
    gain = (delta.where(delta > 0, 0)).rolling(n).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(n).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

class SmaRsiStrategy(Strategy):
    # 參數預設值
    n1 = 10
    n2 = 60
    n_rsi = 14
    rsi_overbought = 70
    sl_pct = 0.0
    tp_pct = 0.0

    def init(self):
        self.sma1 = self.I(SMA, self.data.Close, self.n1)
        self.sma2 = self.I(SMA, self.data.Close, self.n2)
        self.rsi = self.I(RSI, self.data.Close, self.n_rsi)

    def next(self):
        price = self.data.Close[-1]

        # ==================================
        # 出場邏輯 1: 死叉 (Death Cross)
        # ==================================
        # 如果發生死叉，強制平倉
        # 注意：如果有設定 sl/tp，backtesting 會在 next() 執行前先檢查 K 線的 High/Low
        # 如果盤中已經觸發 sl/tp，這裡 self.position 已經是空倉，這段就不會執行
        if self.position:
            if crossover(self.sma2, self.sma1):
                self.position.close()

        # ==================================
        # 進場邏輯 (AND)
        # ==================================
        elif not self.position:
            if crossover(self.sma1, self.sma2) and self.rsi[-1] < self.rsi_overbought:
                
                # 計算具體價格
                sl_price = None
                tp_price = None
                
                if self.sl_pct > 0:
                    sl_price = price * (1 - self.sl_pct / 100)
                if self.tp_pct > 0:
                    tp_price = price * (1 + self.tp_pct / 100)
                
                # 執行買入，同時設定 出場邏輯 2(SL) & 3(TP)
                self.buy(sl=sl_price, tp=tp_price)