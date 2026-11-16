# src/views/main_window.py
import pickle
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget, QMessageBox, QStatusBar
)
from PySide6.QtCore import Qt

from views.param_panel import ParamPanel
from views.result_tabs import ResultTabs
from views.save_manager import SaveManagerPanel
from controllers.backtest_worker import BacktestWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("台股量化回測系統 V3")
        self.resize(1400, 900)
        
        self._worker = None
        self._df_cache = {}

        # 主佈局：三個大分頁
        self.main_tabs = QTabWidget()
        self.setCentralWidget(self.main_tabs)

        # 分頁 1：參數設定
        self.param_panel = ParamPanel()
        self.main_tabs.addTab(self.param_panel, "⚙️ 參數設定")

        # 分頁 2：回測結果
        self.result_tabs = ResultTabs()
        self.main_tabs.addTab(self.result_tabs, "📊 回測結果")

        # 分頁 3：存檔管理
        self.save_manager = SaveManagerPanel()
        self.main_tabs.addTab(self.save_manager, "📁 存檔管理")

        self.setStatusBar(QStatusBar())

        # 信號連接
        self.param_panel.run_requested.connect(self._start_backtest)
        self.param_panel.btn_cancel.clicked.connect(self._cancel_backtest)
        
        # 存檔管理的信號連接
        self.save_manager.load_env_requested.connect(self._on_load_env)
        self.save_manager.load_backtest_requested.connect(self._on_load_backtest)

    def _start_backtest(self, payload: dict):
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "提示", "回測進行中，請稍候。")
            return

        self.param_panel.set_running(True)
        self.statusBar().showMessage("準備開始...")
        
        self._worker = BacktestWorker(
            tickers=payload["tickers"],
            start_date=payload["start_date"],
            end_date=payload["end_date"],
            strategy_grids=payload["strategy_grids"],
            config=payload["config"],
            split_date=payload["split_date"],
            max_workers=payload["max_workers"]
        )
        
        self._worker.progress.connect(self.param_panel.update_progress)
        self._worker.log.connect(self.statusBar().showMessage)
        self._worker.data_ready.connect(self._on_data_ready)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        
        self._worker.start()

    def _cancel_backtest(self):
        if self._worker:
            self._worker.cancel()
            self.param_panel.btn_cancel.setEnabled(False)

    def _on_data_ready(self, df_dict: dict):
        self._df_cache.update(df_dict)

    def _on_finished(self, results: list):
        self.param_panel.set_running(False)
        self.statusBar().showMessage("回測完成")
        
        ok_count = len([r for r in results if r.get("success")])
        if ok_count > 0:
            self.result_tabs.set_results(results, self._df_cache)
            self.main_tabs.setCurrentIndex(1)
        else:
            QMessageBox.warning(self, "回測結束", "沒有成功的回測結果。")

    def _on_failed(self, msg: str):
        self.param_panel.set_running(False)
        self.statusBar().showMessage("回測失敗")
        QMessageBox.critical(self, "錯誤", msg)

    # ================= 存檔載入處理 =================
    def _on_load_env(self, file_path: str):
        """從存檔管理雙擊讀取環境設定。"""
        self.param_panel.load_from_path(file_path)
        self.main_tabs.setCurrentIndex(0)  # 切回參數頁
        self.statusBar().showMessage(f"已載入設定：{Path(file_path).name}", 5000)

    def _on_load_backtest(self, file_path: str):
        """從存檔管理雙擊讀取歷史回測結果。"""
        try:
            with open(file_path, "rb") as f:
                data = pickle.load(f)
                
            results = data.get("results", [])
            df_cache = data.get("df_cache", {})
            
            self._df_cache.update(df_cache)
            self.result_tabs.set_results(results, self._df_cache)
            self.main_tabs.setCurrentIndex(1)  # 切回結果頁
            self.statusBar().showMessage(f"已載入回測：{Path(file_path).name}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "載入失敗", f"無法讀取回測存檔：\n{e}")