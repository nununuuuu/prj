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
    """ 相對強弱指標 (Wilder's Smoothing) """
    close = pd.Series(values)
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(com=n - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=n - 1, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def MACD(values, fast=12, slow=26, signal=9):
    """ MACD (回傳: 快線 DIF, 訊號線 DEM) """
    close = pd.Series(values)
    exp1 = close.ewm(span=fast, adjust=False).mean()
    exp2 = close.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def KD(high, low, close, n=9):
    """ 隨機指標 KD """
    lowest_low = pd.Series(low).rolling(n).min()
    highest_high = pd.Series(high).rolling(n).max()
    rsv = (pd.Series(close) - lowest_low) / (highest_high - lowest_low) * 100
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    return k, d

def BBANDS(values, n=20, std=2.0):
    """ 布林通道 (回傳: 上軌, 下軌) """
    close = pd.Series(values)
    ma = close.rolling(n).mean()
    sigma = close.rolling(n).std()
    upper = ma + (std * sigma)
    lower = ma - (std * sigma)
    return upper, lower

# ==========================================
#  通用策略類別 (Universal Strategy)
# ==========================================
class UniversalStrategy(Strategy):
    # 模式選擇: 'basic' (基礎) 或 'advanced' (進階)
    mode = "basic"
    
    # --- 基礎模式參數 (Basic Mode) ---
    n1 = 10
    n2 = 60
    n_rsi_entry = 14
    rsi_buy_threshold = 70
    n_rsi_exit = 14
    rsi_sell_threshold = 80
    
    # --- 進階模式設定 ---
    entry_config = [] 
    exit_config = []
    
    # --- 風險控制參數 ---
    sl_pct = 0.0 # 固定停損 %
    tp_pct = 0.0 # 固定停利 %
    trailing_stop_pct = 0.0 # 移動停損 % (全域)

    def init(self):
        self.price = self.data.Close
        
        # 1. 基礎模式：初始化固定指標
        if self.mode == "basic":
            self.sma1 = self.I(SMA, self.price, self.n1)
            self.sma2 = self.I(SMA, self.price, self.n2)
            self.rsi_entry = self.I(RSI, self.price, self.n_rsi_entry)
            self.rsi_exit = self.I(RSI, self.price, self.n_rsi_exit)

        # 2. 進階模式：動態初始化指標
        elif self.mode == "advanced":
            # 整合進場與出場的所有設定，一次性計算所需指標
            all_configs = self.entry_config + self.exit_config
            
            for cfg in all_configs:
                stype = cfg.get('type')
                p = cfg.get('params', {})
                
                # 使用 _register_indicator 註冊指標，確保 backtesting.py 能自動處理數據切片
                if stype in ['SMA_CROSS', 'SMA_DEATH']:
                    self._register_indicator(f"SMA_{int(p['n_short'])}", SMA, self.price, int(p['n_short']))
                    self._register_indicator(f"SMA_{int(p['n_long'])}", SMA, self.price, int(p['n_long']))
                    
                elif stype in ['RSI_OVERSOLD', 'RSI_OVERBOUGHT']:
                    self._register_indicator(f"RSI_{int(p['period'])}", RSI, self.price, int(p['period']))
                    
                elif stype in ['MACD_GOLDEN', 'MACD_DEATH']:
                    k = f"MACD_{int(p['fast'])}_{int(p['slow'])}_{int(p['signal'])}"
                    self._register_indicator(k, MACD, self.price, int(p['fast']), int(p['slow']), int(p['signal']))

                elif stype in ['KD_GOLDEN', 'KD_DEATH']:
                    k = f"KD_{int(p['period'])}"
                    self._register_indicator(k, KD, self.data.High, self.data.Low, self.price, int(p['period']))

                elif stype in ['BB_BREAK', 'BB_REVERSE']:
                    k = f"BB_{int(p['period'])}_{p['std']}"
                    self._register_indicator(k, BBANDS, self.price, int(p['period']), p['std'])

    def _register_indicator(self, key, func, *args):
        """ 輔助函數：將指標計算結果綁定到 self 上 (如果尚未存在) """
        if not hasattr(self, key):
            setattr(self, key, self.I(func, *args))

    def check_signal(self, config_list, is_entry=True):
        """
        檢查訊號邏輯：
        - 進場 (Entry): 使用 AND (且)，所有條件成立才買進。
        - 出場 (Exit): 使用 OR (或)，任一條件成立就賣出。
        """
        if not config_list: return False
        
        # 設定初始狀態
        if is_entry:
            combined_result = True  # AND 的初始值設為 True
        else:
            combined_result = False # OR 的初始值設為 False
        
        for cfg in config_list:
            stype = cfg.get('type')
            p = cfg.get('params', {})
            res = False
            
            try:
                # --- 均線策略 ---
                if stype == 'SMA_CROSS': # 黃金交叉
                    s = getattr(self, f"SMA_{int(p['n_short'])}")
                    l = getattr(self, f"SMA_{int(p['n_long'])}")
                    res = crossover(s, l)
                elif stype == 'SMA_DEATH': # 死亡交叉
                    s = getattr(self, f"SMA_{int(p['n_short'])}")
                    l = getattr(self, f"SMA_{int(p['n_long'])}")
                    res = crossover(l, s)

                # --- RSI 策略 ---
                elif stype == 'RSI_OVERSOLD': # RSI < 閾值 (超賣)
                    rsi = getattr(self, f"RSI_{int(p['period'])}")
                    res = rsi[-1] < p['threshold']
                elif stype == 'RSI_OVERBOUGHT': # RSI > 閾值 (超買)
                    rsi = getattr(self, f"RSI_{int(p['period'])}")
                    res = rsi[-1] > p['threshold']

                # --- MACD 策略 ---
                elif stype == 'MACD_GOLDEN': # 快線突破慢線
                    macd_lines = getattr(self, f"MACD_{int(p['fast'])}_{int(p['slow'])}_{int(p['signal'])}")
                    line, sig = macd_lines
                    res = crossover(line, sig)
                elif stype == 'MACD_DEATH': # 快線跌破慢線
                    macd_lines = getattr(self, f"MACD_{int(p['fast'])}_{int(p['slow'])}_{int(p['signal'])}")
                    line, sig = macd_lines
                    res = crossover(sig, line)

                # --- KD 策略 ---
                elif stype == 'KD_GOLDEN': # K 突破 D 且 D 處於低檔
                    kd_lines = getattr(self, f"KD_{int(p['period'])}")
                    k, d = kd_lines
                    res = crossover(k, d) and d[-1] < p['threshold']
                elif stype == 'KD_DEATH': # K 跌破 D 且 D 處於高檔
                    kd_lines = getattr(self, f"KD_{int(p['period'])}")
                    k, d = kd_lines
                    res = crossover(d, k) and d[-1] > p['threshold']

                # --- 布林通道策略 ---
                elif stype == 'BB_BREAK': # 價格突破上軌
                    bb_lines = getattr(self, f"BB_{int(p['period'])}_{p['std']}")
                    upper, lower = bb_lines
                    res = self.price[-1] > upper[-1]
                elif stype == 'BB_REVERSE': # 價格跌回上軌之下 (反轉)
                    bb_lines = getattr(self, f"BB_{int(p['period'])}_{p['std']}")
                    upper, lower = bb_lines
                    res = self.price[-1] < upper[-1] and self.price[-2] > upper[-2]

            except Exception:
                # 若指標計算出錯，視為無訊號
                res = False
            
            # --- 邏輯組合 (AND / OR) ---
            if is_entry:
                combined_result = combined_result and res
            else:
                combined_result = combined_result or res
            
        return combined_result

    def next(self):
        price = self.price[-1]

        # ==========================================================
        #  全域風控：移動停損邏輯 (Trailing Stop)
        # ==========================================================
        # 只有在持有部位，且有設定移動停損時才執行
        if self.position and self.trailing_stop_pct > 0:
            if self.position.is_long:
                # 計算當前價格回檔後的價格
                new_sl = price * (1 - self.trailing_stop_pct / 100)
                
                # 取得目前的停損價 (如果沒有設 SL，預設為 0)
                current_sl = self.position.sl or 0
                
                # 移動停損的核心：只能往上移，不能往下移 (Ratchet)
                if new_sl > current_sl:
                    self.position.sl = new_sl

        # ==========================================================
        #  基礎模式 (Basic Mode)
        # ==========================================================
        if self.mode == "basic":
            if self.position:
                # 出場：死亡交叉 OR RSI過熱
                if crossover(self.sma2, self.sma1) or self.rsi_exit[-1] > self.rsi_sell_threshold:
                    self.position.close()
            else:
                # 進場：黃金交叉 AND RSI低檔
                if crossover(self.sma1, self.sma2) and self.rsi_entry[-1] < self.rsi_buy_threshold:
                    # 計算固定停損/停利價格
                    sl = price * (1 - self.sl_pct/100) if self.sl_pct > 0 else None
                    tp = price * (1 + self.tp_pct/100) if self.tp_pct > 0 else None
                    
                    # 處理移動停損的初始值 (進場時，如果移動停損算出來的 SL 比固定 SL 高，就用移動停損)
                    if self.trailing_stop_pct > 0:
                        initial_ts = price * (1 - self.trailing_stop_pct / 100)
                        if sl:
                            sl = max(sl, initial_ts)
                        else:
                            sl = initial_ts

                    self.buy(sl=sl, tp=tp)

        # ==========================================================
        #  進階模式 (Advanced Mode)
        # ==========================================================
        elif self.mode == "advanced":
            if self.position:
                # 檢查是否滿足任一出場條件 (OR)
                if self.check_signal(self.exit_config, is_entry=False):
                    self.position.close()
            else:
                # 檢查是否滿足所有進場條件 (AND)
                if self.check_signal(self.entry_config, is_entry=True):
                    # 計算固定停損/停利價格
                    sl = price * (1 - self.sl_pct/100) if self.sl_pct > 0 else None
                    tp = price * (1 + self.tp_pct/100) if self.tp_pct > 0 else None
                    
                    # 處理移動停損的初始值
                    if self.trailing_stop_pct > 0:
                        initial_ts = price * (1 - self.trailing_stop_pct / 100)
                        if sl:
                            sl = max(sl, initial_ts)
                        else:
                            sl = initial_ts

                    self.buy(sl=sl, tp=tp)