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

    def init(self):
        self.price = self.data.Close
        
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
                    self._register_indicator(f"SMA_{int(p['n_short'])}", SMA, self.price, int(p['n_short']))
                    self._register_indicator(f"SMA_{int(p['n_long'])}", SMA, self.price, int(p['n_long']))
                elif stype in ['RSI_OVERSOLD', 'RSI_OVERBOUGHT']:
                    self._register_indicator(f"RSI_{int(p['period'])}", RSI, self.price, int(p['period']))
                elif stype in ['MACD_GOLDEN', 'MACD_DEATH']:
                    self._register_indicator(f"MACD_{int(p['fast'])}_{int(p['slow'])}_{int(p['signal'])}", MACD, self.price, int(p['fast']), int(p['slow']), int(p['signal']))
                elif stype in ['KD_GOLDEN', 'KD_DEATH']:
                    self._register_indicator(f"KD_{int(p['period'])}", KD, self.data.High, self.data.Low, self.price, int(p['period']))
                elif stype in ['BB_BREAK', 'BB_REVERSE']:
                    self._register_indicator(f"BB_{int(p['period'])}_{p['std']}", BBANDS, self.price, int(p['period']), p['std'])
                elif stype in ['WILLR_OVERSOLD', 'WILLR_OVERBOUGHT']:
                    self._register_indicator(f"WILLR_{int(p['period'])}", WILLR, self.data.High, self.data.Low, self.price, int(p['period']))
                elif stype == 'TURTLE_ENTRY':
                    self._register_indicator(f"DONCHIAN_HIGH_{int(p['period'])}", DONCHIAN_HIGH, self.data.High, int(p['period']))
                elif stype == 'TURTLE_EXIT':
                    self._register_indicator(f"DONCHIAN_LOW_{int(p['period'])}", DONCHIAN_LOW, self.data.Low, int(p['period']))

    def _register_indicator(self, key, func, *args):
        if not hasattr(self, key): setattr(self, key, self.I(func, *args))

    def check_signal(self, config_list, is_entry=True):
        if not config_list: return False
        combined_result = True if is_entry else False
        
        for cfg in config_list:
            stype = cfg.get('type')
            p = cfg.get('params', {})
            res = False
            try:
                if stype == 'SMA_CROSS':
                    res = crossover(getattr(self, f"SMA_{int(p['n_short'])}"), getattr(self, f"SMA_{int(p['n_long'])}"))
                elif stype == 'SMA_DEATH':
                    res = crossover(getattr(self, f"SMA_{int(p['n_long'])}"), getattr(self, f"SMA_{int(p['n_short'])}"))
                elif stype == 'RSI_OVERSOLD':
                    res = getattr(self, f"RSI_{int(p['period'])}")[-1] < p['threshold']
                elif stype == 'RSI_OVERBOUGHT':
                    res = getattr(self, f"RSI_{int(p['period'])}")[-1] > p['threshold']
                elif stype == 'MACD_GOLDEN':
                    m, s = getattr(self, f"MACD_{int(p['fast'])}_{int(p['slow'])}_{int(p['signal'])}")
                    res = crossover(m, s)
                elif stype == 'MACD_DEATH':
                    m, s = getattr(self, f"MACD_{int(p['fast'])}_{int(p['slow'])}_{int(p['signal'])}")
                    res = crossover(s, m)
                elif stype == 'KD_GOLDEN':
                    k, d = getattr(self, f"KD_{int(p['period'])}")
                    res = crossover(k, d) and d[-1] < p['threshold']
                elif stype == 'KD_DEATH':
                    k, d = getattr(self, f"KD_{int(p['period'])}")
                    res = crossover(d, k) and d[-1] > p['threshold']
                elif stype == 'BB_BREAK':
                    u, l = getattr(self, f"BB_{int(p['period'])}_{p['std']}")
                    res = self.price[-1] > u[-1]
                elif stype == 'BB_REVERSE':
                    u, l = getattr(self, f"BB_{int(p['period'])}_{p['std']}")
                    res = self.price[-1] < u[-1] and self.price[-2] > u[-2]
                elif stype == 'WILLR_OVERSOLD':
                    res = getattr(self, f"WILLR_{int(p['period'])}")[-1] < p['threshold']
                elif stype == 'WILLR_OVERBOUGHT':
                    res = getattr(self, f"WILLR_{int(p['period'])}")[-1] > p['threshold']
                elif stype == 'TURTLE_ENTRY':
                    res = self.price[-1] > getattr(self, f"DONCHIAN_HIGH_{int(p['period'])}")[-1]
                elif stype == 'TURTLE_EXIT':
                    res = self.price[-1] < getattr(self, f"DONCHIAN_LOW_{int(p['period'])}")[-1]
            except: res = False
            
            if is_entry: combined_result = combined_result and res
            else: combined_result = combined_result or res
        return combined_result

    def next(self):
        price = self.price[-1]
        
        # 全域移動停損 (優先於指標)
        if self.position and self.trailing_stop_pct > 0:
            if self.position.is_long:
                new_sl = price * (1 - self.trailing_stop_pct / 100)
                current_sl = self.position.sl or 0
                if new_sl > current_sl: self.position.sl = new_sl

        if self.mode == "basic":
            if self.position:
                if crossover(self.sma2, self.sma1) or self.rsi_exit[-1] > self.rsi_sell_threshold:
                    self.position.close()
            else:
                if crossover(self.sma1, self.sma2) and self.rsi_entry[-1] < self.rsi_buy_threshold:
                    sl = price * (1 - self.sl_pct/100) if self.sl_pct > 0 else None
                    tp = price * (1 + self.tp_pct/100) if self.tp_pct > 0 else None
                    if self.trailing_stop_pct > 0:
                        initial_ts = price * (1 - self.trailing_stop_pct / 100)
                        sl = max(sl, initial_ts) if sl else initial_ts
                    self.buy(sl=sl, tp=tp)
        
        elif self.mode == "advanced":
            if self.position:
                if self.check_signal(self.exit_config, is_entry=False):
                    self.position.close()
            else:
                if self.check_signal(self.entry_config, is_entry=True):
                    sl = price * (1 - self.sl_pct/100) if self.sl_pct > 0 else None
                    tp = price * (1 + self.tp_pct/100) if self.tp_pct > 0 else None
                    if self.trailing_stop_pct > 0:
                        initial_ts = price * (1 - self.trailing_stop_pct / 100)
                        sl = max(sl, initial_ts) if sl else initial_ts
                    self.buy(sl=sl, tp=tp)