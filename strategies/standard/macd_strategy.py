# strategies/macd_strategy.py
import pandas as pd
from strategies.base import BaseStrategy

class MACDStrategy(BaseStrategy):
    NAME = "MACD 動能"
    DESCRIPTION = "DIF 向上穿過訊號線買進，向下穿過賣出"
    PARAM_SCHEMA = {
        "fast_period":   {"type": "int", "default": "12", "label": "快線週期"},
        "slow_period":   {"type": "int", "default": "26", "label": "慢線週期"},
        "signal_period": {"type": "int", "default": "9",  "label": "訊號線週期"},
    }

    def __init__(self, fast_period=12, slow_period=26, signal_period=9):
        self.fast_period = int(fast_period)
        self.slow_period = int(slow_period)
        self.signal_period = int(signal_period)

    def generate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df_proc = df.copy()
        
        # 計算 EMA 與 MACD
        ema_fast = df_proc["Close"].ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = df_proc["Close"].ewm(span=self.slow_period, adjust=False).mean()
        
        df_proc["MACD_DIF"] = ema_fast - ema_slow
        df_proc["MACD_Signal"] = df_proc["MACD_DIF"].ewm(span=self.signal_period, adjust=False).mean()
        df_proc["MACD_Hist"] = df_proc["MACD_DIF"] - df_proc["MACD_Signal"]
        
        # 判斷交叉
        df_proc["MACD_Golden_Cross"] = (df_proc["MACD_DIF"] > df_proc["MACD_Signal"]) & (df_proc["MACD_DIF"].shift(1) <= df_proc["MACD_Signal"].shift(1))
        df_proc["MACD_Death_Cross"] = (df_proc["MACD_DIF"] < df_proc["MACD_Signal"]) & (df_proc["MACD_DIF"].shift(1) >= df_proc["MACD_Signal"].shift(1))
        
        return df_proc

    def check_entry_signal(self, df: pd.DataFrame, idx: int) -> bool:
        if idx < 1: return False
        return bool(df["MACD_Golden_Cross"].iloc[idx])

    def check_exit_signal(self, df: pd.DataFrame, idx: int, trade_info: dict) -> tuple:
        if idx < 1: return False, ""
        if df["MACD_Death_Cross"].iloc[idx]:
            return True, "MACD 死亡交叉"
        return False, ""