import pandas as pd
from strategies.base import BaseStrategy

class KDS1Strategy(BaseStrategy):
    NAME = "KD_S1_黃金死亡交叉"
    DESCRIPTION = "K向上突破D買進，K向下跌破D賣出。"
    
    PARAM_SCHEMA = {
        "period": {"type": "int", "default": "9", "label": "RSV 週期"},
        "k_smooth": {"type": "int", "default": "3", "label": "K 平滑"},
        "d_smooth": {"type": "int", "default": "3", "label": "D 平滑"}
    }

    def __init__(self, period=9, k_smooth=3, d_smooth=3):
        self.period = int(period)
        self.k_smooth = int(k_smooth)
        self.d_smooth = int(d_smooth)

    def generate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df_proc = df.copy()
        low_min = df_proc["Low"].rolling(self.period).min()
        high_max = df_proc["High"].rolling(self.period).max()
        rsv = (df_proc["Close"] - low_min) / (high_max - low_min + 1e-9) * 100
        df_proc["K"] = rsv.ewm(alpha=1/self.k_smooth, adjust=False).mean()
        df_proc["D"] = df_proc["K"].ewm(alpha=1/self.d_smooth, adjust=False).mean()
        return df_proc

    def check_entry_signal(self, df: pd.DataFrame, idx: int) -> bool:
        if idx < 1: return False
        return bool((df["K"].iloc[idx-1] <= df["D"].iloc[idx-1]) and (df["K"].iloc[idx] > df["D"].iloc[idx]))

    def check_exit_signal(self, df: pd.DataFrame, idx: int, trade_info: dict) -> tuple:
        if idx < 1: return False, ""
        if (df["K"].iloc[idx-1] >= df["D"].iloc[idx-1]) and (df["K"].iloc[idx] < df["D"].iloc[idx]):
            return True, "死亡交叉"
        return False, ""