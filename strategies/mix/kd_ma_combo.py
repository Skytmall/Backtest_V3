# strategies/kd_ma_combo.py
import pandas as pd
from strategies.base import BaseStrategy

class KDMAComboStrategy(BaseStrategy):
    NAME = "KD + MA 混血"
    DESCRIPTION = "大趨勢在均線之上，且 KD 發生黃金交叉時進場。跌破均線才出場。"
    PARAM_SCHEMA = {
        "ma_period":   {"type": "int",   "default": "60",  "label": "趨勢過濾均線(MA)"},
        "kd_period":   {"type": "int",   "default": "9",   "label": "KD 週期"},
        "oversold":    {"type": "int",   "default": "80",  "label": "進場K值上限(K<)"},
    }

    def __init__(self, ma_period=60, kd_period=9, oversold=80):
        self.ma_period = int(ma_period)
        self.kd_period = int(kd_period)
        self.oversold = float(oversold)

    def generate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df_proc = df.copy()
        
        # 1. 計算 MA
        df_proc["Trend_MA"] = df_proc["Close"].rolling(self.ma_period).mean()
        
        # 2. 計算 KD
        low_min = df_proc["Low"].rolling(window=self.kd_period).min()
        high_max = df_proc["High"].rolling(window=self.kd_period).max()
        rsv = (df_proc["Close"] - low_min) / (high_max - low_min + 1e-9) * 100
        
        df_proc["K"] = rsv.ewm(alpha=0.4, adjust=False).mean()
        df_proc["D"] = df_proc["K"].ewm(alpha=0.4, adjust=False).mean()
        
        return df_proc

    def check_entry_signal(self, df: pd.DataFrame, idx: int) -> bool:
        if idx < 1: return False
        if pd.isna(df["Trend_MA"].iloc[idx]) or pd.isna(df["K"].iloc[idx]): return False
        
        # 條件一：大趨勢向上 (收盤價站上 MA)
        trend_up = df["Close"].iloc[idx] > df["Trend_MA"].iloc[idx]
        
        # 條件二：KD 黃金交叉，且 K 值小於設定上限
        cross_up = (df["K"].iloc[idx] > df["D"].iloc[idx]) and (df["K"].iloc[idx-1] <= df["D"].iloc[idx-1])
        kd_cross = cross_up and (df["K"].iloc[idx] < self.oversold)
        
        return bool(trend_up and kd_cross)

    def check_exit_signal(self, df: pd.DataFrame, idx: int, trade_info: dict) -> tuple:
        if idx < 1: return False, ""
        if pd.isna(df["Trend_MA"].iloc[idx]): return False, ""
        
        # 出場：只要跌破趨勢均線就出場 (無視 KD 死叉，讓利潤奔跑)
        if (df["Close"].iloc[idx-1] >= df["Trend_MA"].iloc[idx-1]) and (df["Close"].iloc[idx] < df["Trend_MA"].iloc[idx]):
            return True, "跌破趨勢均線"
            
        return False, ""