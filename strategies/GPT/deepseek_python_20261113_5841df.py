import pandas as pd
from strategies.base import BaseStrategy

class KDS4Strategy(BaseStrategy):
    NAME = "KD_S4_突破50跌破50"
    DESCRIPTION = "K向上突破50買進，K向下跌破50賣出。"
    
    PARAM_SCHEMA = {
        "period": {"type": "int", "default": "9", "label": "RSV 週期"},
        "k_smooth": {"type": "int", "default": "3", "label": "K 平滑"}
    }

    def __init__(self, period=9, k_smooth=3):
        self.period = int(period)
        self.k_smooth = int(k_smooth)

    def generate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df_proc = df.copy()
        low_min = df_proc["Low"].rolling(self.period).min()
        high_max = df_proc["High"].rolling(self.period).max()
        rsv = (df_proc["Close"] - low_min) / (high_max - low_min + 1e-9) * 100
        df_proc["K"] = rsv.ewm(alpha=1/self.k_smooth, adjust=False).mean()
        return df_proc

    def check_entry_signal(self, df: pd.DataFrame, idx: int) -> bool:
        if idx < 1: return False
        return bool((df["K"].iloc[idx-1] <= 50) and (df["K"].iloc[idx] > 50))

    def check_exit_signal(self, df: pd.DataFrame, idx: int, trade_info: dict) -> tuple:
        if idx < 1: return False, ""
        if (df["K"].iloc[idx-1] >= 50) and (df["K"].iloc[idx] < 50):
            return True, "跌破50"
        return False, ""