# src/views/result_tabs.py
import pickle
import datetime
import pandas as pd
from PySide6.QtCore import QUrl, Signal, Qt
from PySide6.QtWidgets import (
    QTabWidget, QTableView, QHeaderView, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QComboBox, QPushButton, QLineEdit, QFileDialog, QMessageBox, QInputDialog, QSpinBox
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtGui import QStandardItemModel, QStandardItem

from core.paths import SRC_DIR, SAVES_DIR
from models import LeaderboardModel, GridHeatmapModel, StockBestModel, StrategyBestModel
from ui import chart
from core.analysis import BHComparisonAnalyzer
from core.plots.advanced import generate_advanced_chart

_UI_BASE = QUrl.fromLocalFile(str(SRC_DIR / "ui") + "/")


class PandasModel(QStandardItemModel):
    """用於顯示交易明細與表格的簡易 TableModel。"""
    def set_df(self, df: pd.DataFrame):
        self.clear()
        if df is None or df.empty: return
        self.setHorizontalHeaderLabels(df.columns)
        for _, row in df.iterrows():
            self.appendRow([QStandardItem(str(val)) for val in row])


class ResultTabs(QTabWidget):
    def __init__(self):
        super().__init__()
        self._all_results = []
        self._df_cache = {}
        self._best_metric = "Total_Return"
        self._current_result = None
        self._kline_loaded = False

        self._build_ui()

    def _build_ui(self):
        # 1. 排行榜
        self.tab_leaderboard = QWidget()
        lb_layout = QVBoxLayout(self.tab_leaderboard)
        
        lb_tools = QHBoxLayout()
        self.metric_combo = QComboBox()
        self.metric_combo.addItems(["Total_Return", "CAGR", "Sharpe_Ratio", "Max_Drawdown", "Win_Rate"])
        self.metric_combo.currentTextChanged.connect(self._on_metric_changed)
        lb_tools.addWidget(QLabel("排序指標:"))
        lb_tools.addWidget(self.metric_combo)
        
        lb_tools.addStretch()
        self.btn_save_bt = QPushButton("💾 儲存此次回測")
        self.btn_save_bt.setStyleSheet("background-color: #094771; color: white; font-weight: bold;")
        self.btn_save_bt.clicked.connect(self._save_backtest)
        lb_tools.addWidget(self.btn_save_bt)
        lb_layout.addLayout(lb_tools)

        self.view_leaderboard = QTableView()
        self.model_leaderboard = LeaderboardModel()
        self.view_leaderboard.setModel(self.model_leaderboard)
        self.view_leaderboard.setSortingEnabled(True)
        self.view_leaderboard.doubleClicked.connect(self._on_leaderboard_double_click)
        lb_layout.addWidget(self.view_leaderboard)
        self.addTab(self.tab_leaderboard, "🏆 排行榜")

        # 2. 漸層矩陣
        self.tab_heatmap = QWidget()
        hm_layout = QVBoxLayout(self.tab_heatmap)
        self.view_heatmap = QTableView()
        self.model_heatmap = GridHeatmapModel(columns=15)
        self.view_heatmap.setModel(self.model_heatmap)
        self.view_heatmap.horizontalHeader().setVisible(False)
        self.view_heatmap.verticalHeader().setVisible(False)
        self.view_heatmap.setShowGrid(True)
        self.view_heatmap.horizontalHeader().setDefaultSectionSize(70)
        self.view_heatmap.verticalHeader().setDefaultSectionSize(45)
        self.view_heatmap.doubleClicked.connect(self._on_heatmap_double_click)
        hm_layout.addWidget(self.view_heatmap)
        self.addTab(self.tab_heatmap, "🔥 漸層網格")

        # 3. 個股最佳
        self.view_stock_best = QTableView()
        self.model_stock_best = StockBestModel()
        self.view_stock_best.setModel(self.model_stock_best)
        self.view_stock_best.doubleClicked.connect(self._on_stock_best_double_click)
        self.addTab(self.view_stock_best, "📌 個股最佳")

        # 4. 策略最佳
        self.view_strategy_best = QTableView()
        self.model_strategy_best = StrategyBestModel()
        self.view_strategy_best.setModel(self.model_strategy_best)
        self.view_strategy_best.doubleClicked.connect(self._on_strategy_best_double_click)
        self.addTab(self.view_strategy_best, "🎯 策略最佳")

        # 5. K 線圖
        self.tab_kline = QWidget()
        kl_layout = QVBoxLayout(self.tab_kline)
        kl_layout.setContentsMargins(0, 0, 0, 0)
        
        kl_tools = QHBoxLayout()
        kl_tools.setContentsMargins(10, 5, 10, 5)
        self.lbl_kline_title = QLabel("請先從排行榜雙擊選擇一筆結果")
        self.lbl_kline_title.setStyleSheet("font-weight: bold;")
        kl_tools.addWidget(self.lbl_kline_title)
        kl_tools.addStretch()

        kl_tools.addWidget(QLabel("Top N:"))
        self.spin_top_n = QSpinBox()
        self.spin_top_n.setRange(1, 50)
        self.spin_top_n.setValue(5)
        kl_tools.addWidget(self.spin_top_n)

        kl_tools.addWidget(QLabel("前天數:"))
        self.spin_pad_before = QSpinBox()
        self.spin_pad_before.setRange(1, 60)
        self.spin_pad_before.setValue(10)
        kl_tools.addWidget(self.spin_pad_before)

        kl_tools.addWidget(QLabel("後天數:"))
        self.spin_pad_after = QSpinBox()
        self.spin_pad_after.setRange(1, 60)
        self.spin_pad_after.setValue(10)
        kl_tools.addWidget(self.spin_pad_after)
        
        self.btn_export_ai = QPushButton("📋 複製 AI 包")
        self.btn_export_ai.setStyleSheet("background-color: #e0a800; color: white; font-weight: bold;")
        self.btn_export_ai.clicked.connect(self._export_ai_package)
        self.btn_export_ai.setEnabled(False)
        kl_tools.addWidget(self.btn_export_ai)
        
        kl_layout.addLayout(kl_tools)
        
        self.view_kline = QWebEngineView()
        kl_layout.addWidget(self.view_kline)
        self.addTab(self.tab_kline, "📈 K線圖")

        # 6. 交易明細
        self.view_trades = QTableView()
        self.model_trades = PandasModel()
        self.view_trades.setModel(self.model_trades)
        self.addTab(self.view_trades, "📋 交易明細")

        # 7. ⚖️ 策略 vs 大盤 (B&H)
        self.tab_bh = QWidget()
        bh_layout = QVBoxLayout(self.tab_bh)
        
        bh_top = QHBoxLayout()
        self.lbl_bh_metrics = QLabel("請先從排行榜雙擊選擇一筆結果")
        self.lbl_bh_metrics.setStyleSheet("font-size: 14px; color: #00e676; font-weight: bold;")
        bh_top.addWidget(self.lbl_bh_metrics)
        bh_top.addStretch()
        bh_layout.addLayout(bh_top)

        self.view_bh_chart = QWebEngineView()
        bh_layout.addWidget(self.view_bh_chart, 3)

        self.view_bh_table = QTableView()
        self.model_bh_table = PandasModel()
        self.view_bh_table.setModel(self.model_bh_table)
        bh_layout.addWidget(self.view_bh_table, 1)
        
        self.addTab(self.tab_bh, "⚖️ 策略 vs 大盤")

        # 8. 🎛️ 進階指標分析
        self.tab_advanced = QWidget()
        adv_layout = QVBoxLayout(self.tab_advanced)
        
        adv_tools = QHBoxLayout()
        adv_tools.addWidget(QLabel("選擇圖表類型:"))
        self.combo_chart = QComboBox()
        self.combo_chart.addItems([
            "多變數迴歸分析",
            "一維敏感度 (散點+折線)", 
            "箱型圖 (穩定度)",
            "熱力圖 (2參數)", 
            "3D 散佈圖 (3參數)", 
            "平行座標圖 (多參數)", 
            "分面熱力圖 (3參數)",
            "氣泡圖 (3參數)"
        ])
        self.combo_chart.currentTextChanged.connect(self._update_advanced_chart)
        adv_tools.addWidget(self.combo_chart)
        adv_tools.addStretch()
        adv_layout.addLayout(adv_tools)

        self.view_advanced = QWebEngineView()
        adv_layout.addWidget(self.view_advanced)
        self.addTab(self.tab_advanced, "🎛️ 進階指標分析")

    # ================= 信號處理 =================
    def _on_metric_changed(self, metric: str):
        self._best_metric = metric
        self.set_results(self._all_results, self._df_cache)

    def set_results(self, results: list, df_cache: dict):
        self._all_results = results
        self._df_cache = df_cache
        
        ok_results = [r for r in results if r.get("success")]
        if not ok_results: return

        self.model_leaderboard.set_results(ok_results, self._best_metric)
        self.model_heatmap.set_results(ok_results, self._best_metric)
        self.model_stock_best.set_results(ok_results, self._best_metric)
        self.model_strategy_best.set_results(ok_results, self._best_metric)
        
        self.view_leaderboard.resizeColumnsToContents()
        self.view_stock_best.resizeColumnsToContents()
        self.view_strategy_best.resizeColumnsToContents()

        self._update_advanced_chart(self.combo_chart.currentText())

    # ================= 雙擊跳轉 =================
    def _on_leaderboard_double_click(self, index):
        self._show_detail(self.model_leaderboard.get_orig_index(index.row()))

    def _on_heatmap_double_click(self, index):
        cell = self.model_heatmap.get_cell_by_index(index.row(), index.column())
        if cell: self._show_detail(cell["orig_index"])

    def _on_stock_best_double_click(self, index):
        orig_idx = self.model_stock_best.get_orig_index(index.row())
        if orig_idx >= 0: self._show_detail(orig_idx)

    def _on_strategy_best_double_click(self, index):
        orig_idx = self.model_strategy_best.get_orig_index(index.row())
        if orig_idx >= 0: self._show_detail(orig_idx)

    def _show_detail(self, orig_idx):
        if orig_idx < 0 or orig_idx >= len(self._all_results): return
        r = self._all_results[orig_idx]
        if not r.get("success"): return

        self._current_result = r
        ticker = r["ticker"]
        trades_df = r["is"].get("trades_df", pd.DataFrame())
        self.model_trades.set_df(trades_df)

        self.lbl_kline_title.setText(f"目前檢視：{ticker} | {r['strat_id']} | {r['params']}")
        self.btn_export_ai.setEnabled(True)

        self._render_kline(ticker, r)
        self._render_bh_analysis(r)

        self.setCurrentIndex(4)

    def _render_kline(self, ticker, r):
        from strategies.base import STRATEGY_REGISTRY
        from core.engine import BacktestEngine
        from core.models import BacktestConfig

        if ticker not in self._df_cache: return
        df = self._df_cache[ticker]

        strat_cls = STRATEGY_REGISTRY.get(r["strat_id"])
        if not strat_cls: return
        strat = strat_cls(**r["params"])

        engine = BacktestEngine(BacktestConfig())
        df_proc = engine.run_indicator_only(df, strat)
        
        title = f"{ticker} | {r['strat_id']}"
        html_content = chart.generate_candle_html(df_proc, r["is"].get("trades_df"), title)
        self.view_kline.setHtml(html_content, _UI_BASE)

    def _render_bh_analysis(self, r):
        strat_eq = r["is"].get("equity_df")
        bh_eq = r["benchmark"]["is"].get("equity_df")
        
        if strat_eq is None or bh_eq is None:
            self.lbl_bh_metrics.setText("無 B&H 對比數據")
            return

        initial_cap = strat_eq["Equity"].iloc[0]
        analyzer = BHComparisonAnalyzer(strat_eq, bh_eq, initial_cap)
        
        # 1. 更新指標 Label
        m = analyzer.calculate_metrics()
        self.lbl_bh_metrics.setText(
            f"Beta: {m.get('Beta', 0):.2f} | "
            f"上漲捕捉: {m.get('Up_Capture', 0):.1%} | "
            f"下跌捕捉: {m.get('Down_Capture', 0):.1%} | "
            f"相對回撤: {m.get('Relative_MDD', 0):.2%} | "
            f"總超額報酬: {m.get('Excess_TotalRet', 0):.2%}"
        )
        
        # 2. 更新表格 (B方案)
        slices_df = analyzer.get_time_slices()
        self.model_bh_table.set_df(slices_df)
        self.view_bh_table.resizeColumnsToContents()

        # 3. 畫圖 (A方案)
        ts_df = analyzer.get_time_series()
        import plotly.graph_objects as go
        import plotly.io as pio
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ts_df.index, y=ts_df["Strategy_Ret"], name="策略報酬", line=dict(color="#ef5350")))
        fig.add_trace(go.Scatter(x=ts_df.index, y=ts_df["BH_Ret"], name="B&H報酬", line=dict(color="#26a69a")))
        
        fig.update_layout(
            title="策略 vs B&H 累積報酬對比",
            template="plotly_dark",
            margin=dict(l=40, r=40, t=40, b=40),
            height=400
        )
        
        html = pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
        full_html = f"<html><body style='margin:0; padding:0; background:#0e1117;'>{html}</body></html>"
        self.view_bh_chart.setHtml(full_html, _UI_BASE)

    def _update_advanced_chart(self, chart_type: str):
        if not self._all_results: return
        
        metric_zh_map = {
            "Total_Return": "總報酬率", "CAGR": "年化報酬率", "Volatility": "波動率",
            "Sharpe_Ratio": "夏普比率", "Max_Drawdown": "最大回撤", "Win_Rate": "勝率",
            "Total_Trades": "交易次數", "Avg_Trade_Return": "平均交易報酬",
            "Trade_Frequency": "交易密集度"
        }
        metric_zh = metric_zh_map.get(self._best_metric, self._best_metric)
        
        html = generate_advanced_chart(self._all_results, self._best_metric, chart_type, metric_zh)
        self.view_advanced.setHtml(html, _UI_BASE)

    # ================= 存檔與匯出 =================
    def _save_backtest(self):
        if not self._all_results: return
        default_name = f"backtest_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.pkl"
        path, _ = QFileDialog.getSaveFileName(self, "儲存回測結果", str(SAVES_DIR / default_name), "Pickle (*.pkl)")
        if not path: return
        
        try:
            with open(path, "wb") as f:
                pickle.dump({"results": self._all_results, "df_cache": self._df_cache}, f)
            QMessageBox.information(self, "成功", "回測結果已儲存！")
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"儲存失敗：{e}")

    def _export_ai_package(self):
        if not self._current_result: return
        r = self._current_result
        ticker = r["ticker"]
        df = self._df_cache.get(ticker)
        if df is None: return

        top_n = self.spin_top_n.value()
        pad_before = self.spin_pad_before.value()
        pad_after = self.spin_pad_after.value()

        from strategies.base import STRATEGY_REGISTRY
        from core.engine import BacktestEngine
        from core.models import BacktestConfig
        from core.export import ExportConfig, MarkdownFormatter
        from core.export.extractor import extract_trade_windows
        from core.paths import SAVES_DIR
        from PySide6.QtCore import QMimeData, QUrl
        from PySide6.QtWidgets import QApplication
        
        strat_cls = STRATEGY_REGISTRY.get(r["strat_id"])
        if not strat_cls: return
        strat = strat_cls(**r["params"])
        
        engine = BacktestEngine(BacktestConfig())
        df_proc = engine.run_indicator_only(df, strat)

        config = ExportConfig(top_n=top_n, pad_before=pad_before, pad_after=pad_after)
        
        windows = extract_trade_windows(r, df_proc, config)
        formatter = MarkdownFormatter()
        md_text = formatter.format(r, config, windows)
        
        default_name = f"ai_{ticker}_{r['strat_id']}_{datetime.datetime.now().strftime('%m%d_%H%M')}.md"
        file_path = SAVES_DIR / default_name
        file_path.write_text(md_text, encoding="utf-8")
        
        mime_data = QMimeData()
        mime_data.setUrls([QUrl.fromLocalFile(str(file_path))])
        QApplication.clipboard().setMimeData(mime_data)
        
        QMessageBox.information(self, "✅ 已生成並複製", f"已存至：\n{file_path}\n並複製檔案到剪貼簿！")