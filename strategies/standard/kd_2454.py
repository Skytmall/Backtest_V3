import pandas as pd
from strategies.base import BaseStrategy

class KDTrendFilterStrategy(BaseStrategy):
    NAME = "KD_2454"
    DESCRIPTION = "V2版：加入 MA20 跌破出場，避免高檔鈍化導致變成買入持有。"
    
    PARAM_SCHEMA = {
        "period":     {"type": "int",   "default": "9",     "label": "KD 週期"},
        "alpha_k":    {"type": "float", "default": "0.333", "label": "K值平滑權重"},
        "alpha_d":    {"type": "float", "default": "0.333", "label": "D值平滑權重"},
        "oversold":   {"type": "int",   "default": "50",    "label": "多頭時超賣線 (建議50~60)"},
        "overbought": {"type": "int",   "default": "70",    "label": "超買線 (賣出)"} # 💡 預設調低到 70
    }

    def __init__(self, period=9, alpha_k=0.333, alpha_d=0.333, oversold=50, overbought=70):
        self.period = int(period)
        self.alpha_k = float(alpha_k)
        self.alpha_d = float(alpha_d)
        self.oversold = float(oversold)
        self.overbought = float(overbought)

    def generate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df_proc = df.copy()
        
        # 1. 計算 KD
        low_min = df_proc["Low"].rolling(window=self.period).min()
        high_max = df_proc["High"].rolling(window=self.period).max()
        rsv = (df_proc["Close"] - low_min) / (high_max - low_min + 1e-9) * 100
        
        df_proc["K"] = rsv.ewm(alpha=self.alpha_k, adjust=False).mean()
        df_proc["D"] = df_proc["K"].ewm(alpha=self.alpha_d, adjust=False).mean()
        
        # 2. 計算 60 日均線 (趨勢) 與 20 日均線 (防守)
        df_proc["MA60"] = df_proc["Close"].rolling(60).mean()
        df_proc["MA20"] = df_proc["Close"].rolling(20).mean()
        
        return df_proc

    def check_entry_signal(self, df: pd.DataFrame, idx: int) -> bool:
        if idx < 60: return False
        if pd.isna(df["K"].iloc[idx]) or pd.isna(df["MA60"].iloc[idx]): return False
        
        # 黃金交叉條件
        is_cross_up = (df["K"].iloc[idx] > df["D"].iloc[idx]) and (df["K"].iloc[idx-1] <= df["D"].iloc[idx-1])
        if not is_cross_up:
            return False
            
        current_k = df["K"].iloc[idx]
        current_close = df["Close"].iloc[idx]
        ma60 = df["MA60"].iloc[idx]
        
        # 依據趨勢決定進場門檻
        if current_close > ma60:
            return bool(current_k < self.oversold)
        else:
            return bool(current_k < 20)

    def check_exit_signal(self, df: pd.DataFrame, idx: int, trade_info: dict) -> tuple:
        if idx < 1: return False, ""
        if pd.isna(df["K"].iloc[idx]) or pd.isna(df["MA20"].iloc[idx]): return False, ""
        
        current_close = df["Close"].iloc[idx]
        current_k = df["K"].iloc[idx]
        current_d = df["D"].iloc[idx]
        prev_k = df["K"].iloc[idx-1]
        prev_d = df["D"].iloc[idx-1]
        
        # 💡 新增防線 1：跌破 20 日均線，無條件出場 (不管 KD 是多少)
        if current_close < df["MA20"].iloc[idx]:
            return True, "跌破20日均線 (波段結束)"

        # 💡 原本防線 2：高檔死叉 (但把門檻從 80 降到 70，更容易觸發)
        is_cross_down = (current_k < current_d) and (prev_k >= prev_d)
        if is_cross_down and current_k > self.overbought:
            return True, f"KD 高檔死叉 (K>{self.overbought})"
            
        return False, ""