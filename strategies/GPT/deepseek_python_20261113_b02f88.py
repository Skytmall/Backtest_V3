import pandas as pd
from strategies.base import BaseStrategy

class KDS2Strategy(BaseStrategy):
    NAME = "KD_S2_超買賣區交叉"
    DESCRIPTION = "K<20且黃金交叉買進，K>80且死亡交叉賣出。"
    
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
        cross_up = (df["K"].iloc[idx-1] <= df["D"].iloc[idx-1]) and (df["K"].iloc[idx] > df["D"].iloc[idx])
        return bool(cross_up and (df["K"].iloc[idx] < 20))

    def check_exit_signal(self, df: pd.DataFrame, idx: int, trade_info: dict) -> tuple:
        if idx < 1: return False, ""
        cross_down = (df["K"].iloc[idx-1] >= df["D"].iloc[idx-1]) and (df["K"].iloc[idx] < df["D"].iloc[idx])
        if cross_down and (df["K"].iloc[idx] > 80):
            return True, "超買區死亡交叉"
        return False, ""