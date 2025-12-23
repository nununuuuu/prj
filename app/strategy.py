from backtesting import Strategy
from backtesting.lib import crossover
import pandas as pd
import numpy as np

# ==========================================
#  技術指標計算函數庫 
# ==========================================
def SMA(values, n):
    """ 簡單移動平均線 """
    return pd.Series(values).rolling(n).mean()

def RSI(values, n=14):
    """ 相對強弱指標 """
    close = pd.Series(values)
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(com=n - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=n - 1, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def MACD(values, fast=12, slow=26, signal=9):
    """ MACD """
    close = pd.Series(values)
    exp1 = close.ewm(span=fast, adjust=False).mean()
    exp2 = close.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def KD(high, low, close, n=9):
    """ KD 指標 """
    lowest_low = pd.Series(low).rolling(n).min()
    highest_high = pd.Series(high).rolling(n).max()
    rsv = (pd.Series(close) - lowest_low) / (highest_high - lowest_low) * 100
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    return k, d

def BBANDS(values, n=20, std=2.0):
    """ 布林通道 """
    close = pd.Series(values)
    ma = close.rolling(n).mean()
    sigma = close.rolling(n).std()
    upper = ma + (std * sigma)
    lower = ma - (std * sigma)
    return upper, lower

def WILLR(high, low, close, n=14):
    """ 威廉指標 %R """
    highest_high = pd.Series(high).rolling(n).max()
    lowest_low = pd.Series(low).rolling(n).min()
    # 公式: (最高 - 收盤) / (最高 - 最低) * -100 (範圍 -100 ~ 0)
    res = (highest_high - pd.Series(close)) / (highest_high - lowest_low) * -100
    return res

def DONCHIAN_HIGH(high, n=20):
    """ 海龜法則: 過去 N 日的最高價 (不含今日) """
    return pd.Series(high).rolling(n).max().shift(1)

def DONCHIAN_LOW(low, n=20):
    """ 海龜法則: 過去 N 日的最低價 (不含今日) """
    return pd.Series(low).rolling(n).min().shift(1)

# ==========================================
#  通用策略類別
# ==========================================
class UniversalStrategy(Strategy):
    mode = "basic"
    n1 = 10; n2 = 60
    n_rsi_entry = 14; rsi_buy_threshold = 70
    n_rsi_exit = 14; rsi_sell_threshold = 80
    entry_config = []; exit_config = []
    sl_pct = 0.0; tp_pct = 0.0; trailing_stop_pct = 0.0
    monthly_contribution_amount = 0.0
    monthly_contribution_fee = 1.0
    monthly_contribution_days = []
    commission_rate = 0.0

    def init(self):
        self.price = self.data.Close
        self.total_bars = len(self.data) # 記錄總 K 線數，用於判斷回測結束
        
        # 定期定額輔助變數
        self.last_month = -1
        self.deposited_targets = set()
        self.initial_bought = False
        self.order_log = [] # 用於記錄定期定額的買入點位 (因 Backtesting 可能將多次買入視為單一倉位)

        if self.mode == "basic":
            self.sma1 = self.I(SMA, self.price, self.n1)
            self.sma2 = self.I(SMA, self.price, self.n2)
            self.rsi_entry = self.I(RSI, self.price, self.n_rsi_entry)
            self.rsi_exit = self.I(RSI, self.price, self.n_rsi_exit)

        elif self.mode == "advanced":
            all_configs = self.entry_config + self.exit_config
            for cfg in all_configs:
                stype = cfg.get('type')
                p = cfg.get('params', {})
                
                if stype in ['SMA_CROSS', 'SMA_DEATH']:
                    n_s = int(p.get('n_short', 10))
                    n_l = int(p.get('n_long', 60))
                    self._register_indicator(f"SMA_{n_s}", SMA, self.price, n_s)
                    self._register_indicator(f"SMA_{n_l}", SMA, self.price, n_l)
                elif stype in ['RSI_OVERSOLD', 'RSI_OVERBOUGHT']:
                    per = int(p.get('period', 14))
                    self._register_indicator(f"RSI_{per}", RSI, self.price, per)
                elif stype in ['MACD_GOLDEN', 'MACD_DEATH']:
                    f = int(p.get('fast', 12))
                    s = int(p.get('slow', 26))
                    sig = int(p.get('signal', 9))
                    self._register_indicator(f"MACD_{f}_{s}_{sig}", MACD, self.price, f, s, sig)
                elif stype in ['KD_GOLDEN', 'KD_DEATH']:
                    per = int(p.get('period', 9))
                    self._register_indicator(f"KD_{per}", KD, self.data.High, self.data.Low, self.data.Close, per)
                elif stype in ['BB_LOWER', 'BB_UPPER', 'BB_BREAK', 'BB_REVERSE']:
                    per = int(p.get('period', 20))
                    std = float(p.get('std', 2.0))
                    self._register_indicator(f"BB_{per}_{std}", BBANDS, self.price, per, std)
                elif stype in ['WILLR_OVERSOLD', 'WILLR_OVERBOUGHT']:
                    per = int(p.get('period', 14))
                    self._register_indicator(f"WILLR_{per}", WILLR, self.data.High, self.data.Low, self.data.Close, per)
                elif stype in ['TURTLE_ENTRY', 'TURTLE_EXIT']:
                    per = int(p.get('period', 20))
                    if 'ENTRY' in stype:
                        self._register_indicator(f"DONCHIAN_HIGH_{per}", DONCHIAN_HIGH, self.data.High, per)
                    else:
                        self._register_indicator(f"DONCHIAN_LOW_{per}", DONCHIAN_LOW, self.data.Low, per)

    def _register_indicator(self, key, func, *args):
        if not hasattr(self, key): setattr(self, key, self.I(func, *args))

    def check_signal(self, config_list, is_entry=True):
        if not config_list: return False
        
        # 只要有一個策略符合就觸發 (OR 邏輯)
        for conf in config_list:
            stype = conf.get('type')
            params = conf.get('params', {})
            
            try:
                if stype == 'SMA_CROSS':
                    # 預設: 短10, 長60
                    n_s = int(params.get('n_short', 10))
                    n_l = int(params.get('n_long', 60))
                    ma_s = getattr(self, f"SMA_{n_s}")
                    ma_l = getattr(self, f"SMA_{n_l}")
                    if is_entry:
                        if crossover(ma_s, ma_l): return True
                    else:
                        if crossover(ma_l, ma_s): return True

                elif stype == 'RSI_OVERSOLD' or stype == 'RSI_OVERBOUGHT':
                    # 預設: 14, 閥值 30/70
                    p = int(params.get('period', 14))
                    rsi = getattr(self, f"RSI_{p}")
                    thresh = float(params.get('threshold', 30 if is_entry else 70))
                    if is_entry:
                        if rsi[-1] < thresh: return True
                    else:
                        if rsi[-1] > thresh: return True

                elif stype == 'MACD_GOLDEN' or stype == 'MACD_DEATH':
                    # 預設: 12, 26, 9
                    f = int(params.get('fast', 12))
                    s = int(params.get('slow', 26))
                    sig = int(params.get('signal', 9))
                    key = f"MACD_{f}_{s}_{sig}"
                    macd_line = getattr(self, key)[0]
                    sig_line = getattr(self, key)[1]
                    if is_entry: # 黃金交叉
                        if crossover(macd_line, sig_line) and macd_line[-1] < 0: return True
                    else: # 死亡交叉
                        if crossover(sig_line, macd_line): return True

                elif stype == 'KD_GOLDEN' or stype == 'KD_DEATH':
                    # 預設: 9
                    p = int(params.get('period', 9))
                    key = f"KD_{p}"
                    k = getattr(self, key)[0]
                    d = getattr(self, key)[1]
                    if is_entry:
                        if crossover(k, d) and k[-1] < 20: return True
                    else:
                        if crossover(d, k) and k[-1] > 80: return True

                elif stype == 'BB_LOWER' or stype == 'BB_UPPER':
                    # 預設: 20, 2.0
                    p = int(params.get('period', 20))
                    std = float(params.get('std', 2.0))
                    key = f"BB_{p}_{std}"
                    upper = getattr(self, key)[0]
                    lower = getattr(self, key)[1]
                    close = self.data.Close
                    if is_entry: # 觸碰下通道
                        if close[-1] < lower[-1]: return True
                    else: # 觸碰上通道
                        if close[-1] > upper[-1]: return True

                elif stype == 'WILLR_OVERSOLD' or stype == 'WILLR_OVERBOUGHT':
                    # 預設: 14, -80/-20
                    p = int(params.get('period', 14))
                    wr = getattr(self, f"WILLR_{p}")
                    thresh = float(params.get('threshold', -80 if is_entry else -20))
                    if is_entry:
                        if wr[-1] < thresh: return True
                    else:
                        if wr[-1] > thresh: return True
                
                elif stype == 'TURTLE_ENTRY' or stype == 'TURTLE_EXIT':
                    # 預設: 20
                    p = int(params.get('period', 20))
                    if is_entry:
                        h = getattr(self, f"DONCHIAN_HIGH_{p}")
                        if self.data.Close[-1] > h[-2]: return True
                    else:
                        l = getattr(self, f"DONCHIAN_LOW_{p}")
                        if self.data.Close[-1] < l[-2]: return True

            except Exception as e:
                print(f"[Strategy Error] {stype}: {e}")
                continue

        return False

    def next(self):
        # 使用 self.data.Close[-1] 確保獲取當前 Bar 的收盤價
        price = self.data.Close[-1]
        
        # -----------------------------
        # 0. 定期定額入金 (Monthly Contribution)
        # -----------------------------
        if self.monthly_contribution_amount > 0 and self.monthly_contribution_days:
            current_date = self.data.index[-1]
            current_month = current_date.month
            current_day = current_date.day
            
            # 如果換月了，重置已入金的目標日
            if current_month != self.last_month:
                self.deposited_targets = set()
                self.last_month = current_month
                
            # 檢查是否有應入金但尚未入金的日子 (遇到假日順延)
            # 邏輯: 只要今天日期 >= 目標日，且該目標日尚未在本月執行過，就補執行
            for target_day in self.monthly_contribution_days:
                if current_day >= target_day and target_day not in self.deposited_targets:
                    self._broker._cash += self.monthly_contribution_amount
                    self.deposited_targets.add(target_day)
                    
                    # [Periodic Only] 如果是定期定額模式，入金後立即全額買入
                    if self.mode == 'periodic':
                        # 1. 扣除定額手續費 (直接從現金扣除)
                        self._broker._cash -= self.monthly_contribution_fee
                        
                        # 2. 計算可用於買股的資金
                        # (扣款金額 - 手續費) / 股價，取整數 (無條件捨去)
                        available_for_stock = self.monthly_contribution_amount - self.monthly_contribution_fee
                        
                        if available_for_stock > 0:

                            buy_size = int(available_for_stock / price)
                            if buy_size > 0:
                                self.buy(size=buy_size)
                                # 記錄買入訊號供前端繪圖
                                self.order_log.append({
                                    "time": self.data.index[-1],
                                    "type": "buy",
                                    "price": price
                                })

        # [Periodic Only] 定期定額模式：初始資金的處理 (Day 1 of Backtest execution)
        # 由於 Backtesting.py 會等待指標 (如 SMA 60) 計算完才開始執行 next()，
        # 此時 len(self.data) 可能已經 > 60，故不能用 len(self.data) < 5 判斷。
        # 改用 flag 確保只執行一次。
        if self.mode == 'periodic' and not self.initial_bought:
             available_cash = self._broker._cash
             if available_cash > self.price[-1]: # Check against price
                 # 1. 扣除定額手續費 (直接從現金扣除)
                 if available_cash > self.monthly_contribution_fee:
                     self._broker._cash -= self.monthly_contribution_fee
                     available_for_stock = available_cash - self.monthly_contribution_fee
                     
                     buy_size = int(available_for_stock / price)
                     if buy_size > 0:
                         self.buy(size=buy_size)
                         self.order_log.append({
                             "time": self.data.index[-1],
                             "type": "buy",
                             "price": self.price[-1]
                         })
             
             self.initial_bought = True
            
        # 定期定額模式不執行後續的指標出場邏輯，直接 return
        if self.mode == 'periodic':
            # 但在最後一根 K 線強制平倉，以產生交易紀錄供前端繪圖
            if len(self.data) == self.total_bars:  # 檢查是否為最後一根 K 線
                 self.position.close()
            return

        # -----------------------------
        # 1. 持倉管理 (移動停損 & 出場)
        # -----------------------------
        if self.position:
            # A. 移動停損 (Trailing Stop) - 手動實作
            if self.trailing_stop_pct > 0:
                # 更新最高價
                if not hasattr(self, 'peak_price') or self.peak_price < price:
                    self.peak_price = price
                
                # 檢查是否觸發移動停損
                ts_price = self.peak_price * (1 - self.trailing_stop_pct / 100)
                if price < ts_price:
                    self.position.close()
                    return # 已出場，跳過後續

            # B. 策略出場訊號檢查
            if self.mode == "basic":
                if crossover(self.sma2, self.sma1) or self.rsi_exit[-1] > self.rsi_sell_threshold:
                    self.position.close()
            elif self.mode == "advanced":
                if self.check_signal(self.exit_config, is_entry=False):
                    self.position.close()

        # -----------------------------
        # 2. 進場邏輯
        # -----------------------------
        else:
            # 重置最高價追蹤
            self.peak_price = 0

            signal = False
            if self.mode == "basic":
                if crossover(self.sma1, self.sma2) and self.rsi_entry[-1] < self.rsi_buy_threshold:
                    signal = True
            elif self.mode == "advanced":
                if self.check_signal(self.entry_config, is_entry=True):
                    signal = True
            
            if signal:
                sl = None
                tp = None
                
                # 計算固定停損/停利 (基於當前價格預估)
                # 注意: 實際成交價可能略有不同(隔日開盤)，但這是回測引擎的限制，
                # 我們傳入 sl/tp 給 buy()，引擎會幫我們掛單
                if self.sl_pct > 0:
                    sl = price * (1 - self.sl_pct/100)
                
                if self.tp_pct > 0:
                    tp = price * (1 + self.tp_pct/100)

                # 排除無效的 SL (如果計算錯誤導致 SL > Price)
                if sl and sl >= price: sl = None

                self.buy(sl=sl, tp=tp)
