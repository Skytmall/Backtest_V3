# src/core/analysis.py
import pandas as pd
import numpy as np

class BHComparisonAnalyzer:
    def __init__(self, eq_df: pd.DataFrame, bh_df: pd.DataFrame, initial_cap: float):
        """
        參數：
        eq_df: 策略權益曲線 (index為日期, 需有 'Equity' 欄位)
        bh_df: B&H權益曲線 (index為日期, 需有 'Equity' 欄位)
        initial_cap: 初始資金
        """
        # 對齊時間軸
        self.df = pd.DataFrame({
            "Strategy": eq_df["Equity"],
            "BH": bh_df["Equity"]
        }).ffill().dropna()
        
        self.initial_cap = initial_cap
        self.daily_ret = self.df.pct_change().dropna()
        
    def calculate_metrics(self) -> dict:
        """計算 Beta、捕捉率與回撤"""
        if self.daily_ret.empty:
            return {}

        # 1. Beta
        cov = self.daily_ret["Strategy"].cov(self.daily_ret["BH"])
        var = self.daily_ret["BH"].var()
        beta = cov / var if var != 0 else 0.0

        # 2. 上漲/下跌捕捉率 (使用日報酬)
        up_days = self.daily_ret[self.daily_ret["BH"] > 0]
        down_days = self.daily_ret[self.daily_ret["BH"] < 0]
        
        up_capture = (up_days["Strategy"].mean() / up_days["BH"].mean()) if not up_days.empty else 0.0
        down_capture = (down_days["Strategy"].mean() / down_days["BH"].mean()) if not down_days.empty else 0.0

        # 3. 相對回撤
        def get_mdd(series):
            cummax = series.cummax()
            dd = (series - cummax) / cummax
            return dd.min()

        strat_mdd = get_mdd(self.df["Strategy"])
        bh_mdd = get_mdd(self.df["BH"])
        relative_mdd = strat_mdd - bh_mdd  # 如果是正數，代表策略回撤比大盤小(少賠)

        # 4. 全期間超額報酬
        strat_total_ret = self.df["Strategy"].iloc[-1] / self.initial_cap - 1
        bh_total_ret = self.df["BH"].iloc[-1] / self.initial_cap - 1

        return {
            "Beta": beta,
            "Up_Capture": up_capture,
            "Down_Capture": down_capture,
            "Strategy_MDD": strat_mdd,
            "BH_MDD": bh_mdd,
            "Relative_MDD": relative_mdd,
            "Strategy_TotalRet": strat_total_ret,
            "BH_TotalRet": bh_total_ret,
            "Excess_TotalRet": strat_total_ret - bh_total_ret
        }

    def get_time_series(self) -> pd.DataFrame:
        """回傳 A 方案需要的時間序列"""
        df = pd.DataFrame(index=self.df.index)
        
        # 累積報酬率 (%)
        df["Strategy_Ret"] = (self.df["Strategy"] / self.initial_cap - 1) * 100
        df["BH_Ret"] = (self.df["BH"] / self.initial_cap - 1) * 100
        
        # 相對強弱曲線 (策略淨值 / B&H淨值)
        df["Relative_Strength"] = self.df["Strategy"] / self.df["BH"]
        
        # 滾動 12 個月 (252個交易日) 超額報酬 (%)
        rolling_strat = self.df["Strategy"].pct_change(252)
        rolling_bh = self.df["BH"].pct_change(252)
        df["Rolling_12M_Excess"] = (rolling_strat - rolling_bh) * 100
        
        return df.dropna(subset=["Rolling_12M_Excess"], how="all")

    def get_time_slices(self) -> pd.DataFrame:
        """回傳 B 方案需要的切片表格 (近 1M, 3M, 6M, 1Y, 3Y, 5Y, All)"""
        end_date = self.df.index[-1]
        periods = {
            "近 1 個月": 21,
            "近 3 個月": 63,
            "近 6 個月": 126,
            "近 1 年": 252,
            "近 3 年": 252 * 3,
            "近 5 年": 252 * 5,
            "全期間": len(self.df) - 1
        }
        
        results = []
        for name, days in periods.items():
            if days >= len(self.df):
                # 如果資料長度不足該區間，就用全期間
                days = len(self.df) - 1
            
            if days <= 0: continue
            
            start_date = self.df.index[-days - 1]
            strat_ret = self.df["Strategy"].iloc[-1] / self.df["Strategy"].iloc[-days - 1] - 1
            bh_ret = self.df["BH"].iloc[-1] / self.df["BH"].iloc[-days - 1] - 1
            excess = strat_ret - bh_ret
            
            results.append({
                "時間尺度": name,
                "區間": f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}",
                "策略報酬": f"{strat_ret:.2%}",
                "B&H報酬": f"{bh_ret:.2%}",
                "超額報酬": f"{excess:.2%}",
                "勝負": "贏" if excess > 0 else "輸"
            })
            
        return pd.DataFrame(results)