# strategies/kd_basic.py
import pandas as pd
from strategies.base import BaseStrategy

class KDStrategy(BaseStrategy):
    NAME = "KD 基礎策略"
    DESCRIPTION = "傳統 KD 策略（還原 V1 寬鬆進場邏輯）"
    
    PARAM_SCHEMA = {
        "period":     {"type": "int",   "default": "9",     "label": "KD 週期"},
        "alpha_k":    {"type": "float", "default": "0.333", "label": "K值平滑權重"},
        "alpha_d":    {"type": "float", "default": "0.333", "label": "D值平滑權重"},
        "oversold":   {"type": "int",   "default": "20",    "label": "超賣線 (買進)"},
        "overbought": {"type": "int",   "default": "80",    "label": "超買線 (賣出)"}
    }

    def __init__(self, period=9, alpha_k=0.333, alpha_d=0.333, oversold=20, overbought=80):
        self.period = int(period)
        self.alpha_k = float(alpha_k)
        self.alpha_d = float(alpha_d)
        self.oversold = float(oversold)
        self.overbought = float(overbought)

    def generate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df_proc = df.copy()
        low_min = df_proc["Low"].rolling(window=self.period).min()
        high_max = df_proc["High"].rolling(window=self.period).max()
        rsv = (df_proc["Close"] - low_min) / (high_max - low_min + 1e-9) * 100
        
        df_proc["K"] = rsv.ewm(alpha=self.alpha_k, adjust=False).mean()
        df_proc["D"] = df_proc["K"].ewm(alpha=self.alpha_d, adjust=False).mean()
        return df_proc

    def check_entry_signal(self, df: pd.DataFrame, idx: int) -> bool:
        if idx < 1: return False
        if pd.isna(df["K"].iloc[idx]): return False
        
        # 💡 修正：還原 V1 的邏輯，只要 K > D 且 K < 超賣線就進場
        return bool((df["K"].iloc[idx] > df["D"].iloc[idx]) and (df["K"].iloc[idx] < self.oversold))

    def check_exit_signal(self, df: pd.DataFrame, idx: int, trade_info: dict) -> tuple:
        if idx < 1: return False, ""
        if pd.isna(df["K"].iloc[idx]): return False, ""
        
        # 💡 修正：還原 V1 的邏輯，只要 K < D 且 K > 超買線就出場
        if (df["K"].iloc[idx] < df["D"].iloc[idx]) and (df["K"].iloc[idx] > self.overbought):
            return True, "KD 超買死叉"
        return False, ""