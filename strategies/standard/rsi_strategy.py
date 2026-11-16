# strategies/rsi_strategy.py
import pandas as pd
from strategies.base import BaseStrategy

class RSIStrategy(BaseStrategy):
    NAME = "RSI 相對強弱"
    DESCRIPTION = "RSI 向上穿過超賣線買進，向下穿過超買線賣出"
    PARAM_SCHEMA = {
        "period":     {"type": "int", "default": "14", "label": "RSI 週期"},
        "oversold":   {"type": "int", "default": "30", "label": "超賣買進線"},
        "overbought": {"type": "int", "default": "70", "label": "超買賣出線"},
    }

    def __init__(self, period=14, oversold=30, overbought=70):
        self.period = int(period)
        self.oversold = float(oversold)
        self.overbought = float(overbought)

    def generate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df_proc = df.copy()
        
        # 計算 RSI (使用 Wilder's Smoothing，這是業界標準)
        delta = df_proc["Close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        
        avg_gain = gain.ewm(alpha=1 / self.period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / self.period, adjust=False).mean()
        
        rs = avg_gain / (avg_loss + 1e-9)
        df_proc["RSI"] = 100 - (100 / (1 + rs))
        
        return df_proc

    def check_entry_signal(self, df: pd.DataFrame, idx: int) -> bool:
        if idx < 1: return False
        if pd.isna(df["RSI"].iloc[idx]): return False
        
        # 進場：RSI 由下往上穿過超賣線 (例如從 28 跑到 32)
        cross_up = (df["RSI"].iloc[idx-1] <= self.oversold) and (df["RSI"].iloc[idx] > self.oversold)
        return bool(cross_up)

    def check_exit_signal(self, df: pd.DataFrame, idx: int, trade_info: dict) -> tuple:
        if idx < 1: return False, ""
        if pd.isna(df["RSI"].iloc[idx]): return False, ""
        
        # 出場：RSI 由上往下穿過超買線 (例如從 72 跌到 68)
        cross_down = (df["RSI"].iloc[idx-1] >= self.overbought) and (df["RSI"].iloc[idx] < self.overbought)
        if cross_down:
            return True, "RSI 跌破超買線"
            
        return False, ""