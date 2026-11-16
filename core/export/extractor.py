# src/core/export/extractor.py
from dataclasses import dataclass
from typing import List, Dict
import pandas as pd
from .config import ExportConfig

# 基礎價格列，不算「指標」
_BASE_PRICE_COLS = {"Open", "High", "Low", "Close", "Volume", "VWAP", "VWAP_Calc"}

@dataclass
class TradeWindow:
    """單筆交易的擷取結果。"""
    rank:          int
    tag:           str               # "最賺" / "最虧"
    entry_date:    pd.Timestamp
    exit_date:     pd.Timestamp
    entry_price:   float
    exit_price:    float
    shares:        int
    ret:           float
    exit_reason:   str
    window_df:     pd.DataFrame      # 包含 mark 列的 DataFrame
    indicator_cols: list[str]

def _detect_indicator_cols(df: pd.DataFrame, config: ExportConfig) -> list[str]:
    """自動偵測指標欄位（排除 OHLCV 與布林值）。"""
    return [
        c for c in df.columns
        if c not in _BASE_PRICE_COLS
        and pd.api.types.is_numeric_dtype(df[c])
        and not pd.api.types.is_bool_dtype(df[c])
    ]

def _extract_one_window(df_proc: pd.DataFrame, entry_date: pd.Timestamp, exit_date: pd.Timestamp, config: ExportConfig) -> pd.DataFrame:
    """切出指定日期範圍的 K 線。"""
    idx = df_proc.index
    entry_pos = idx.searchsorted(entry_date, side="left")
    exit_pos  = idx.searchsorted(exit_date,  side="right")
    
    start = max(0, entry_pos - config.pad_before)
    end   = min(len(idx), exit_pos + config.pad_after)
    return df_proc.iloc[start:end].copy()

def _mark_window(window: pd.DataFrame, entry_date: pd.Timestamp, exit_date: pd.Timestamp) -> pd.DataFrame:
    """在首列加上 mark 欄位，標記 ENTRY 與 EXIT。"""
    entry_s = entry_date.strftime("%Y-%m-%d")
    exit_s  = exit_date.strftime("%Y-%m-%d")
    marks = []
    for d in window.index:
        ds = d.strftime("%Y-%m-%d")
        if ds == entry_s: marks.append("ENTRY")
        elif ds == exit_s: marks.append("EXIT")
        else: marks.append("")
    
    window.insert(0, "mark", marks)
    return window

def extract_trade_windows(result: dict, df_proc: pd.DataFrame, config: ExportConfig) -> List[TradeWindow]:
    """提取 Top N 賺與 Top N 虧的交易窗口（純排名制，保證不遺漏）。"""
    trades = result.get("is", {}).get("trades_df", pd.DataFrame()).copy()
    if trades.empty:
        return []

    cm = config.columns
    trades[cm.entry_date] = pd.to_datetime(trades[cm.entry_date])
    trades[cm.exit_date]  = pd.to_datetime(trades[cm.exit_date])

    # 按報酬率降序排序
    trades = trades.sort_values(by=cm.return_col, ascending=False).reset_index(drop=True)
    total_trades = len(trades)

    indicators = _detect_indicator_cols(df_proc, config) if config.include_indicator else []
    windows = []

    if total_trades <= config.top_n:
        # 如果總筆數很少，直接全部列出，不區分最賺最虧
        final_df = trades.copy()
        final_df["tag"] = final_df[cm.return_col].apply(lambda x: "獲利" if x > 0 else "虧損")
    else:
        # 抓前 N 名（最賺）
        best = trades.head(config.top_n).copy()
        best["tag"] = "最賺"
        # 抓後 N 名（最虧）
        worst = trades.tail(config.top_n).copy()
        worst["tag"] = "最虧"
        
        # 合併並去重（避免總數太少時發生重疊）
        final_df = pd.concat([best, worst]).drop_duplicates(
            subset=[cm.entry_date, cm.exit_date], keep="first"
        )

    for rank, (_, row) in enumerate(final_df.iterrows(), 1):
        entry = row[cm.entry_date]
        exit_ = row[cm.exit_date]
        w_df = _extract_one_window(df_proc, entry, exit_, config)
        if w_df.empty:
            continue
            
        w_df = _mark_window(w_df, entry, exit_)
        
        tag = row["tag"]
        # 如果標籤是「最虧」但其實是賺錢的，改叫「最不賺」比較直觀
        if tag == "最虧" and row[cm.return_col] > 0:
            tag = "最不賺"
        
        windows.append(TradeWindow(
            rank=rank, tag=tag,
            entry_date=entry, exit_date=exit_,
            entry_price=row[cm.entry_price], exit_price=row[cm.exit_price],
            shares=row[cm.shares], ret=row[cm.return_col],
            exit_reason=row[cm.exit_reason],
            window_df=w_df, indicator_cols=indicators
        ))

    return windows