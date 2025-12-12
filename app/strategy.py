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
    # 這些參數會由外部傳入
    n1 = 10
    n2 = 20
    n_rsi = 14
    
    # 風險參數 (0 代表不啟用)
    sl_pct = 0.0  # 例如 5 代表 5%
    tp_pct = 0.0  # 例如 10 代表 10%

    def init(self):
        self.sma1 = self.I(SMA, self.data.Close, self.n1)
        self.sma2 = self.I(SMA, self.data.Close, self.n2)
        self.rsi = self.I(RSI, self.data.Close, self.n_rsi)

    def next(self):
        price = self.data.Close[-1]
        
        # 如果有持倉，檢查是否要平倉 (雖然設了 SL/TP，但策略反轉時也要平倉)
        if self.position:
            # 死叉出場
            if crossover(self.sma2, self.sma1):
                self.position.close()
        
        # 如果沒持倉，檢查進場條件
        else:
            # 黃金交叉 且 RSI < 70
            if crossover(self.sma1, self.sma2) and self.rsi[-1] < 70:
                
                # 計算停損停利價格
                sl_price = None
                tp_price = None
                
                if self.sl_pct > 0:
                    sl_price = price * (1 - self.sl_pct / 100)
                
                if self.tp_pct > 0:
                    tp_price = price * (1 + self.tp_pct / 100)
                
                # 執行買入，並帶入停損停利參數
                self.buy(sl=sl_price, tp=tp_price)