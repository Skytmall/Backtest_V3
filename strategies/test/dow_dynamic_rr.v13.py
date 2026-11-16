import pandas as pd
from strategies.base import BaseStrategy

class DowDynamicRRStrategy(BaseStrategy):
    NAME = "道氏動態風報比"
    DESCRIPTION = "V13版：移除 MA120 的滯後限制以提早進場，回歸純粹的波段防守，適合順勢突破。"
    
    PARAM_SCHEMA = {
        "lookback": {"type": "int", "default": "20", "label": "突破高點週期"}, 
        "swing_period": {"type": "int", "default": "10", "label": "防禦停損週期"}, 
        "rr_ratio": {"type": "float", "default": "2.0", "label": "風報比 (用來計算加碼距離)"},
        "entry_pct": {"type": "float", "default": "0.33", "label": "單次進場資金比例"},
    }

    def __init__(self, lookback=20, swing_period=10, rr_ratio=2.0, entry_pct=0.33):
        self.lookback = int(lookback)
        self.swing_period = int(swing_period)
        self.rr_ratio = float(rr_ratio)
        self.entry_pct = float(entry_pct)
        
        self.last_entry_price = 0.0

    def generate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df_proc = df.copy()
        
        # 1. 放寬趨勢定義：移除 MA120，只看中短期多頭
        df_proc["MA20"] = df_proc["Close"].rolling(20).mean()
        df_proc["MA60"] = df_proc["Close"].rolling(60).mean()
        
        df_proc["Trend_Up"] = (
            (df_proc["Close"] > df_proc["MA20"]) & 
            (df_proc["MA20"] > df_proc["MA60"]) & 
            (df_proc["MA60"] > df_proc["MA60"].shift(5))
        )

        # 2. 計算突破高點與防守低點
        df_proc["Roll_High"] = df_proc["High"].rolling(self.lookback).max()
        df_proc["Swing_Low"] = df_proc["Low"].rolling(self.swing_period).min().shift(1)
        
        # 3. 計算單位距離 (作為加碼間距)
        df_proc["Range"] = df_proc["Roll_High"] - df_proc["Swing_Low"]
        df_proc["Unit"] = df_proc["Range"].apply(lambda x: x / self.rr_ratio if pd.notna(x) and x > 0 else 0)
        
        return df_proc

    def check_entry_signal(self, df: pd.DataFrame, idx: int) -> bool:
        if pd.isna(df["MA60"].iloc[idx]): return False
        if not df["Trend_Up"].iloc[idx]: return False

        current_close = df["Close"].iloc[idx]
        prev_roll_high = df["Roll_High"].iloc[idx-1]
        unit = df["Unit"].iloc[idx]
        
        if pd.isna(prev_roll_high) or pd.isna(unit): return False
        
        # 條件：創下 N 日新高
        is_breakout = current_close > prev_roll_high
        
        if is_breakout:
            if self.last_entry_price > 0:
                # 如果已經有持倉，必須大於上次買價 + 1單位，才允許加碼
                if current_close >= self.last_entry_price + unit:
                    self.last_entry_price = current_close
                    return True
                else:
                    return False
            else:
                self.last_entry_price = current_close
                return True
                
        return False

    def get_entry_qty(self, df: pd.DataFrame, idx: int, current_price: float, available_cash: float) -> int:
        target_cash = available_cash * self.entry_pct
        if current_price <= 0: return 0
        return int(target_cash // current_price)

    def check_exit_signal(self, df: pd.DataFrame, idx: int, trade_info: dict) -> tuple:
        if idx < 1: return False, ""
        
        current_close = df["Close"].iloc[idx]
        total_shares = trade_info.get("total_shares", 0)
        
        swing_low = df["Swing_Low"].iloc[idx]
        ma20 = df["MA20"].iloc[idx]
        ma60 = df["MA60"].iloc[idx]
        
        # 空手時重置狀態
        if total_shares == 0:
            self.last_entry_price = 0.0
            return False, ""

        if pd.isna(swing_low) or pd.isna(ma20) or pd.isna(ma60):
            return False, ""

        # 1. 跌破 10 日前波低點
        if current_close < swing_low:
            return True, f"跌破10日前波低點 ({swing_low:.2f})"

        # 2. 跌破 20 日線且下彎
        if current_close < ma20 and ma20 < df["MA20"].shift(1).iloc[idx]:
            return True, "跌破20日線且下彎 (短線轉弱)"

        # 3. 跌破 60 日線
        if current_close < ma60:
            return True, "跌破60日線 (中期防線)"

        return False, ""