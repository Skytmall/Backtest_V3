# src/core/export/pipeline.py
from pathlib import Path
from typing import Optional
import pandas as pd

from .config import ExportConfig
from .extractor import extract_trade_windows
from .formatters import BaseFormatter, MarkdownFormatter

def export_ai_package(
    result: dict, 
    df_proc: pd.DataFrame, 
    output_path: str | Path, 
    config: ExportConfig = None,
    formatter: Optional[BaseFormatter] = None
) -> Path:
    """生成 AI 診斷包並寫入檔案。"""
    config = config or ExportConfig()
    output_path = Path(output_path)
    
    windows = extract_trade_windows(result, df_proc, config)
    
    formatter = formatter or MarkdownFormatter()
    text = formatter.format(result, config, windows)
    
    output_path.write_text(text, encoding="utf-8")
    return output_path