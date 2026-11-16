import pandas as pd
import numpy as np
from strategies.base import BaseStrategy

class KDS6Strategy(BaseStrategy):
    NAME = "KD_S6_多頭底背離"
    DESCRIPTION = "價格破底但K值未破底，確認後10日內黃金交叉買進，死亡交叉賣出。"
    
    PARAM_SCHEMA = {
        "period": {"type": "int", "default": "9", "label": "RSV 週期"},
        "k_smooth": {"type": "int", "default": "3", "label": "K 平滑"},
        "d_smooth": {"type": "int", "default": "3", "label": "D 平滑"}
    }

    def __init__(self, period=9, k_smooth=3, d_smooth=3):
        self.period = int(period)
        self.k_smooth = int(k_smooth)
        self.d_smooth = int(d_smooth)
        self.pending_buy = False
        self.pending_days = 0

    def generate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df_proc = df.copy()
        low_min = df_proc["Low"].rolling(self.period).min()
        high_max = df_proc["High"].rolling(self.period).max()
        rsv = (df_proc["Close"] - low_min) / (high_max - low_min + 1e-9) * 100
        df_proc["K"] = rsv.ewm(alpha=1/self.k_smooth, adjust=False).mean()
        df_proc["D"] = df_proc["K"].ewm(alpha=1/self.d_smooth, adjust=False).mean()
        
        # 標記局部低點 (左右各3天)
        df_proc["Pivot_Low"] = False
        for i in range(3, len(df_proc) - 3):
            if df_proc["Low"].iloc[i] == df_proc["Low"].iloc[i-3:i+4].min():
                df_proc.loc[df_proc.index[i], "Pivot_Low"] = True
                
        return df_proc

    def check_entry_signal(self, df: pd.DataFrame, idx: int) -> bool:
        if idx < 60: return False
        
        # 避免未來函數：確認 idx-3 是否為低點
        check_idx = idx - 3
        if df["Pivot_Low"].iloc[check_idx]:
            curr_low = df["Low"].iloc[check_idx]
            curr_k = df["K"].iloc[check_idx]
            
            # 往前找前一個低點 (相距 5~60 天)
            for j in range(check_idx - 5, check_idx - 60, -1):
                if j < 0: break
                if df["Pivot_Low"].iloc[j]:
                    prev_low = df["Low"].iloc[j]
                    prev_k = df["K"].iloc[j]
                    if curr_low < prev_low and curr_k > prev_k:
                        self.pending_buy = True
                        self.pending_days = 10
                    break

        if self.pending_buy and self.pending_days > 0:
            is_cross_up = (df["K"].iloc[idx] > df["D"].iloc[idx]) and (df["K"].iloc[idx-1] <= df["D"].iloc[idx-1])
            if is_cross_up:
                self.pending_buy = False
                self.pending_days = 0
                return True
            else:
                self.pending_days -= 1
                if self.pending_days == 0:
                    self.pending_buy = False
        return False

    def check_exit_signal(self, df: pd.DataFrame, idx: int, trade_info: dict) -> tuple:
        if idx < 1: return False, ""
        if (df["K"].iloc[idx-1] >= df["D"].iloc[idx-1]) and (df["K"].iloc[idx] < df["D"].iloc[idx]):
            return True, "死亡交叉"
        return False, ""