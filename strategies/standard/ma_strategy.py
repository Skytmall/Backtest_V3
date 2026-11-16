# strategies/ma_strategy.py
import pandas as pd
from strategies.base import BaseStrategy

class MAStrategy(BaseStrategy):
    NAME = "MA 均線交叉"
    DESCRIPTION = "短均線向上穿過長均線買進，向下穿過賣出"
    PARAM_SCHEMA = {
        "short_period": {"type": "int", "default": "10:30:5", "label": "快線週期"},
        "long_period":  {"type": "int", "default": "40:80:10", "label": "慢線週期"},
    }

    def __init__(self, short_period=20, long_period=60):
        self.short_period = int(short_period)
        self.long_period = int(long_period)

    def generate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df_proc = df.copy()
        df_proc[f"SMA_{self.short_period}"] = df_proc["Close"].rolling(self.short_period).mean()
        df_proc[f"SMA_{self.long_period}"] = df_proc["Close"].rolling(self.long_period).mean()

        fast = df_proc[f"SMA_{self.short_period}"]
        slow = df_proc[f"SMA_{self.long_period}"]
        
        # 判斷黃金交叉與死亡交叉
        df_proc["MA_Golden_Cross"] = (fast > slow) & (fast.shift(1) <= slow.shift(1))
        df_proc["MA_Death_Cross"] = (fast < slow) & (fast.shift(1) >= slow.shift(1))
        return df_proc

    def check_entry_signal(self, df: pd.DataFrame, idx: int) -> bool:
        if idx < 1: return False
        return bool(df["MA_Golden_Cross"].iloc[idx])

    def check_exit_signal(self, df: pd.DataFrame, idx: int, trade_info: dict) -> tuple:
        if idx < 1: return False, ""
        if df["MA_Death_Cross"].iloc[idx]:
            return True, "均線死亡交叉"
        return False, ""