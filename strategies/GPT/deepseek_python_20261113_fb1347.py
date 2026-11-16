import pandas as pd
from strategies.base import BaseStrategy

class KDS5Strategy(BaseStrategy):
    NAME = "KD_S5_高檔鈍化"
    DESCRIPTION = "K連續3日>80買進，跌破80賣出。"
    
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
        if idx < 3: return False
        cond = (df["K"].iloc[idx] > 80) and (df["K"].iloc[idx-1] > 80) and (df["K"].iloc[idx-2] > 80)
        prev_cond = (df["K"].iloc[idx-1] > 80) and (df["K"].iloc[idx-2] > 80) and (df["K"].iloc[idx-3] > 80)
        return bool(cond and not prev_cond)

    def check_exit_signal(self, df: pd.DataFrame, idx: int, trade_info: dict) -> tuple:
        if idx < 1: return False, ""
        if (df["K"].iloc[idx-1] >= 80) and (df["K"].iloc[idx] < 80):
            return True, "跌破80"
        return False, ""