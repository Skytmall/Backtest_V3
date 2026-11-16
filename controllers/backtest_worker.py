# src/controllers/backtest_worker.py
import threading
import traceback
from typing import Dict, List, Any, Optional
import pandas as pd
from PySide6.QtCore import QThread, Signal

from core.models import BacktestConfig
from core.runner import run_multi_strategy_multi_stock
from data.fetcher import DataFetcher


class BacktestWorker(QThread):
    progress = Signal(int, int)
    log = Signal(str)
    data_ready = Signal(dict)
    finished_ok = Signal(list)
    failed = Signal(str)

    def __init__(self, tickers, start_date, end_date, strategy_grids, config, split_date, max_workers):
        super().__init__()
        self._tickers = tickers
        self._start_date = start_date
        self._end_date = end_date
        self._strategy_grids = strategy_grids
        self._config = config
        self._split_date = split_date
        self._max_workers = max_workers
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def _progress_cb(self, completed, total, _results):
        self.progress.emit(completed, total)

    def run(self):
        try:
            if self._cancel_event.is_set(): return

            df_dict = {}
            for t in self._tickers:
                if self._cancel_event.is_set(): return
                self.log.emit(f"⬇ 正在下載 {t}...")
                try:
                    df_dict[t] = DataFetcher.get_data(t, self._start_date, self._end_date)
                except Exception as e:
                    self.log.emit(f"⚠ {t} 下載失敗：{e}")
            
            if not df_dict:
                self.failed.emit("所有股票都下載失敗，無法回測。")
                return
                
            self.data_ready.emit(df_dict)
            self.log.emit("✅ 資料下載完成，開始回測...")

            results = run_multi_strategy_multi_stock(
                df_dict=df_dict,
                strategy_grids=self._strategy_grids,
                config=self._config,
                split_date=self._split_date,
                max_workers=self._max_workers,
                progress_callback=self._progress_cb,
                cancel_event=self._cancel_event,
            )
            
            if self._cancel_event.is_set():
                self.log.emit("⏹ 回測已取消")
            else:
                self.finished_ok.emit(results)
        except Exception as e:
            self.failed.emit(f"執行發生錯誤：\n{e}\n{traceback.format_exc()}")  