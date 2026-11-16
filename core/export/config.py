# src/core/export/config.py
from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class ColumnMapping:
    """未來 trades_df 如果改欄位名稱，只需改這裡。"""
    entry_date:   str = "entry_date"
    exit_date:    str = "exit_date"
    entry_price:  str = "entry_price"
    exit_price:   str = "exit_price"
    shares:       str = "shares"
    return_col:   str = "return"
    exit_reason:  str = "exit_reason"

@dataclass
class ExportConfig:
    """AI 診斷包的設定。"""
    top_n:        int = 5        # 賺/虧各抓幾筆
    pad_before:   int = 10       # 進場前抓幾天
    pad_after:    int = 10       # 出場後抓幾天
    
    include_summary:   bool = True  # 是否包含全局績效表
    include_indicator: bool = True  # 是否包含 KD/MA 等指標欄位
    
    columns: ColumnMapping = field(default_factory=ColumnMapping)