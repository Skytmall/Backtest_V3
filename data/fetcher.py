# data/fetcher.py
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)
import os
import pandas as pd
import numpy as np
import yfinance as yf
from core.debug_logger import trace_call

class DataFetcher:
    CACHE_DIR = os.path.join(os.getcwd(), "data_cache")
    REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]
    NUMERIC_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

    @classmethod
    @trace_call
    def get_data(cls, ticker: str, start_date: str, end_date: str, is_debug: bool = False) -> pd.DataFrame:
        ticker = ticker.strip().upper()
        if not ticker: raise ValueError("股票代號不能為空。")

        os.makedirs(cls.CACHE_DIR, exist_ok=True)
        safe_ticker = ticker.replace('.', '_')
        debug_file = os.path.join(cls.CACHE_DIR, f"{safe_ticker}_{start_date}_{end_date}_debug.csv")

        if is_debug:
            if os.path.exists(debug_file):
                try:
                    df = pd.read_csv(debug_file, index_col=0, parse_dates=True)
                    return cls._clean_data(df)
                except Exception as e:
                    raise RuntimeError(f"讀取除錯快照失敗：{e}")
            else:
                raise FileNotFoundError(f"找不到除錯快照：{debug_file}")

        try:
            df = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True, multi_level_index=False)
            if df is None or df.empty:
                raise ValueError(f"無法下載 {ticker} 的數據。")
            df = cls._clean_data(df)
            df.to_csv(debug_file)
            return df
        except Exception as e:
            raise RuntimeError(f"獲取資料失敗: {e}")

    @staticmethod
    def _clean_data(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).capitalize() for c in df.columns]
        if not pd.api.types.is_datetime64_any_dtype(df.index): df.index = pd.to_datetime(df.index)
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        df = df.sort_index()
        if "Volume" not in df.columns: df["Volume"] = 0.0
        missing_cols = [c for c in ["Open", "High", "Low", "Close"] if c not in df.columns]
        if missing_cols: raise ValueError(f"缺少必要欄位: {missing_cols}")
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype(np.float64)
        df = df.ffill().dropna(subset=["Open", "High", "Low", "Close"])
        return df[["Open", "High", "Low", "Close", "Volume"]]