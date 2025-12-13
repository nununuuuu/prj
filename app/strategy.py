from backtesting import Strategy
from backtesting.lib import crossover
import pandas as pd
import numpy as np

def SMA(values, n):
    return pd.Series(values).rolling(n).mean()

def RSI(values, n=14):
    """
    使用 Wilder's Smoothing 計算 RSI
    """
    close = pd.Series(values)
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # 使用 ewm(com=n-1) 模擬 Wilder's Smoothing
    avg_gain = gain.ewm(com=n - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=n - 1, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

class SmaRsiStrategy(Strategy):
    # 參數定義 (必須與 main.py bt.run 傳入的名稱一致)
    n1 = 10
    n2 = 60
    
    # 進場 RSI 參數
    n_rsi_entry = 14
    rsi_buy_threshold = 30 # [修正] 預設 30
    
    # 出場 RSI 參數
    n_rsi_exit = 14
    rsi_sell_threshold = 70 # [修正] 預設 70
    
    sl_pct = 0.0
    tp_pct = 0.0

    def init(self):
        # 計算均線
        self.sma1 = self.I(SMA, self.data.Close, self.n1)
        self.sma2 = self.I(SMA, self.data.Close, self.n2)
        
        # 計算兩條獨立的 RSI
        self.rsi_entry_line = self.I(RSI, self.data.Close, self.n_rsi_entry)
        self.rsi_exit_line = self.I(RSI, self.data.Close, self.n_rsi_exit)

    def next(self):
        price = self.data.Close[-1]

        # ==================================
        # 持有部位時 -> 檢查出場
        # ==================================
        if self.position:
            # 1. 趨勢反轉：死亡交叉
            if crossover(self.sma2, self.sma1):
                self.position.close()
            
            # 2. RSI 過熱出場
            elif self.rsi_exit_line[-1] > self.rsi_sell_threshold:
                self.position.close()

        # ==================================
        # 空手時 -> 檢查進場
        # ==================================
        elif not self.position:
            # 黃金交叉 AND 進場 RSI 低於閾值
            if crossover(self.sma1, self.sma2) and self.rsi_entry_line[-1] < self.rsi_buy_threshold:
                
                sl_price = price * (1 - self.sl_pct / 100) if self.sl_pct > 0 else None
                tp_price = price * (1 + self.tp_pct / 100) if self.tp_pct > 0 else None
                
                self.buy(sl=sl_price, tp=tp_price)