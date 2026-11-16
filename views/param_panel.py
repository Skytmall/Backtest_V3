# src/views/param_panel.py
import os
import json
import re
from typing import Dict, List, Any, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, 
    QPushButton, QProgressBar, QGroupBox, QLabel, QListWidget, 
    QListWidgetItem, QTreeWidget, QTreeWidgetItem, QFileDialog, 
    QMessageBox, QSpinBox, QDoubleSpinBox, QComboBox, QInputDialog, QAbstractItemView
)

from core.models import BacktestConfig
from core.paths import SAVES_ENV_DIR, SAVES_STOCKS_DIR, SAVES_STRATEGIES_DIR, WATCHLIST_FILE
from strategies.base import STRATEGY_REGISTRY


def parse_range(text: str, typ: str) -> List[Any]:
    s = str(text).strip()
    if not s: return []
    if "," in s or "、" in s:
        parts = [x.strip() for x in s.replace("、", ",").split(",") if x.strip()]
        return [int(x) if typ == "int" else float(x) for x in parts] if typ != "str" else parts
    if typ == "int":
        if ":" in s:
            p = [int(x) for x in s.split(":")]
            return list(range(p[0], p[1] + 1, p[2] if len(p) == 3 else 1))
        return [int(s)]
    if typ == "float":
        if ":" in s:
            p = [float(x) for x in s.split(":")]
            import numpy as np
            step = p[2] if len(p) == 3 else 1.0
            return [round(x, 6) for x in np.arange(p[0], p[1] + 1e-9, step)]
        return [float(s)]
    return [s]


class StrategyParamWidget(QWidget):
    changed = Signal()
    def __init__(self, strat_cls):
        super().__init__()
        self.strat_cls = strat_cls
        self.param_edits = {}
        layout = QFormLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        schema = getattr(strat_cls, "PARAM_SCHEMA", {}) or {}
        for key, spec in schema.items():
            ed = QLineEdit(str(spec.get("default", "")))
            ed.textChanged.connect(self.changed.emit)
            self.param_edits[key] = ed
            layout.addRow(spec.get("label", key), ed)

    def get_grid(self) -> Dict[str, List[Any]]:
        grid = {}
        schema = getattr(self.strat_cls, "PARAM_SCHEMA", {}) or {}
        for key, ed in self.param_edits.items():
            typ = schema[key].get("type", "str")
            vals = parse_range(ed.text(), typ)
            if vals: grid[key] = vals
        return grid


class ParamPanel(QWidget):
    run_requested = Signal(dict)
    
    def __init__(self):
        super().__init__()
        self._strategy_widgets = {}
        self._build_ui()
        self._load_watchlist()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # ================= 第一列：環境 + 測試股票 =================
        col_left = QVBoxLayout()
        
        env_group = QGroupBox("📂 環境設定 (全局)")
        env_layout = QHBoxLayout(env_group)
        btn_env_load = QPushButton("📥 讀取")
        btn_env_save = QPushButton("💾 儲存")
        btn_env_load.clicked.connect(lambda: self._load_json_partial(SAVES_ENV_DIR))
        btn_env_save.clicked.connect(lambda: self._save_json_partial("env"))
        env_layout.addWidget(btn_env_load)
        env_layout.addWidget(btn_env_save)
        col_left.addWidget(env_group)

        stock_group = QGroupBox("1. 測試股票")
        stock_layout = QVBoxLayout(stock_group)
        
        stock_io_layout = QHBoxLayout()
        btn_stock_load = QPushButton("📥 讀取名單")
        btn_stock_save = QPushButton("💾 儲存名單")
        btn_stock_load.clicked.connect(lambda: self._load_json_partial(SAVES_STOCKS_DIR))
        btn_stock_save.clicked.connect(lambda: self._save_json_partial("stocks"))
        stock_io_layout.addWidget(btn_stock_load)
        stock_io_layout.addWidget(btn_stock_save)
        stock_layout.addLayout(stock_io_layout)

        tool_layout = QHBoxLayout()
        btn_batch = QPushButton("📋 批次新增")
        btn_batch.clicked.connect(self._batch_add_tickers)
        btn_clear = QPushButton("🗑️ 清除選取")
        btn_clear.clicked.connect(self._remove_selected_tickers)
        tool_layout.addWidget(btn_batch)
        tool_layout.addWidget(btn_clear)
        stock_layout.addLayout(tool_layout)

        self.ed_new_ticker = QLineEdit()
        self.ed_new_ticker.setPlaceholderText("輸入代號 (按 Enter 新增)")
        self.ed_new_ticker.returnPressed.connect(self._add_ticker)
        stock_layout.addWidget(self.ed_new_ticker)
        
        self.list_tickers = QListWidget()
        self.list_tickers.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_tickers.itemChanged.connect(self._on_ticker_check_changed)
        stock_layout.addWidget(self.list_tickers)
        
        col_left.addWidget(stock_group, 1)

        # ================= 第二列：時間、資金與風控 =================
        col_mid = QVBoxLayout()
        
        basic_group = QGroupBox("2. 資金、時間與進階風控")
        form_basic = QFormLayout(basic_group)
        
        self.ed_start = QLineEdit("2020-01-01")
        self.ed_end = QLineEdit("2024-01-01")
        self.ed_oos = QLineEdit()
        self.ed_oos.setPlaceholderText("留空不分割")
        
        form_basic.addRow("起始日", self.ed_start)
        form_basic.addRow("結束日", self.ed_end)
        form_basic.addRow("OOS分割", self.ed_oos)
        
        self.ed_capital = QLineEdit("1000000")
        self.ed_fee = QLineEdit("0.001425")
        self.ed_tax = QLineEdit("0.003")
        
        form_basic.addRow("本金", self.ed_capital)
        form_basic.addRow("手續費率", self.ed_fee)
        form_basic.addRow("證交稅率", self.ed_tax)

        # 💡 新增風控與交易單位
        self.ed_stop_loss = QDoubleSpinBox()
        self.ed_stop_loss.setRange(0, 1.0)
        self.ed_stop_loss.setSingleStep(0.01)
        self.ed_stop_loss.setValue(0.0)
        self.ed_stop_loss.setSpecialValueText("關閉")
        
        self.ed_trailing = QDoubleSpinBox()
        self.ed_trailing.setRange(0, 1.0)
        self.ed_trailing.setSingleStep(0.01)
        self.ed_trailing.setValue(0.0)
        self.ed_trailing.setSpecialValueText("關閉")

        self.ed_take_profit = QDoubleSpinBox()
        self.ed_take_profit.setRange(0, 2.0)
        self.ed_take_profit.setSingleStep(0.01)
        self.ed_take_profit.setValue(0.0)
        self.ed_take_profit.setSpecialValueText("關閉")

        self.spin_max_days = QSpinBox()
        self.spin_max_days.setRange(0, 1000)
        self.spin_max_days.setValue(0)
        self.spin_max_days.setSpecialValueText("關閉")

        self.cbo_lot_size = QComboBox()
        self.cbo_lot_size.addItem("整張 (1000股)", 1000)
        self.cbo_lot_size.addItem("零股 (1股)", 1)

        form_basic.addRow("停損 %", self.ed_stop_loss)
        form_basic.addRow("移停 %", self.ed_trailing)
        form_basic.addRow("停利 %", self.ed_take_profit)
        form_basic.addRow("最大持股天數", self.spin_max_days)
        form_basic.addRow("交易單位", self.cbo_lot_size)
        
        col_mid.addWidget(basic_group)

        run_group = QGroupBox("4. 執行")
        run_layout = QVBoxLayout(run_group)
        
        ctrl_layout = QHBoxLayout()
        self.lbl_total = QLabel("總組合數：0")
        self.lbl_total.setStyleSheet("font-weight: bold; color: #00e676;")
        self.spin_workers = QSpinBox()
        self.spin_workers.setRange(1, 32)
        self.spin_workers.setValue(4)
        
        ctrl_layout.addWidget(QLabel("線程:"))
        ctrl_layout.addWidget(self.spin_workers)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.lbl_total)
        run_layout.addLayout(ctrl_layout)
        
        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton("🚀 執行回測")
        self.btn_run.setStyleSheet("font-weight:bold; padding:10px; background-color: #094771;")
        self.btn_run.clicked.connect(self._on_run_clicked)
        
        self.btn_cancel = QPushButton("⏹ 取消")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setStyleSheet("padding:10px;")
        
        btn_layout.addWidget(self.btn_run, 2)
        btn_layout.addWidget(self.btn_cancel, 1)
        run_layout.addLayout(btn_layout)
        
        self.progress = QProgressBar()
        self.progress.setValue(0)
        run_layout.addWidget(self.progress)
        
        col_mid.addWidget(run_group)
        col_mid.addStretch()

        # ================= 第三列：策略 =================
        col_right = QVBoxLayout()
        
        strat_group = QGroupBox("3. 策略與參數")
        strat_layout = QVBoxLayout(strat_group)
        
        strat_io_layout = QHBoxLayout()
        btn_strat_load = QPushButton("📥 讀取策略")
        btn_strat_save = QPushButton("💾 儲存策略")
        btn_strat_load.clicked.connect(lambda: self._load_json_partial(SAVES_STRATEGIES_DIR))
        btn_strat_save.clicked.connect(lambda: self._save_json_partial("strategies"))
        strat_io_layout.addWidget(btn_strat_load)
        strat_io_layout.addWidget(btn_strat_save)
        strat_layout.addLayout(strat_io_layout)

        self.tree_strategies = QTreeWidget()
        self.tree_strategies.setHeaderLabels(["啟用", "策略名稱", "參數設定"])
        self.tree_strategies.setColumnWidth(0, 50)
        self.tree_strategies.setColumnWidth(1, 150)
        strat_layout.addWidget(self.tree_strategies)
        
        self._init_strategies()
        col_right.addWidget(strat_group)

        main_layout.addLayout(col_left, 1)
        main_layout.addLayout(col_mid, 1)
        main_layout.addLayout(col_right, 2)

    # ================= 存讀檔與資料收集 =================
    def _save_json_partial(self, mode: str):
        if mode == "env":
            default_dir = SAVES_ENV_DIR
            default_name = "env_all.json"
            data = {
                "tickers": self._get_tickers_data(),
                "backtest": self._get_backtest_data(),
                "strategies": self._get_strategies_data()
            }
        elif mode == "stocks":
            default_dir = SAVES_STOCKS_DIR
            default_name = "stock_list.json"
            data = {"tickers": self._get_tickers_data()}
        elif mode == "strategies":
            default_dir = SAVES_STRATEGIES_DIR
            default_name = "strat_config.json"
            data = {"strategies": self._get_strategies_data()}
        else: return

        path, _ = QFileDialog.getSaveFileName(self, f"儲存 {mode}", str(default_dir / default_name), "JSON (*.json)")
        if not path: return
        
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "成功", f"已儲存至 {path}")
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"儲存失敗：{e}")

    def _load_json_partial(self, default_dir):
        path, _ = QFileDialog.getOpenFileName(self, "讀取設定", str(default_dir), "JSON (*.json)")
        if not path: return
        self.load_from_path(path)

    def load_from_path(self, file_path: str):
        if not os.path.exists(file_path): return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if "tickers" in data:
                self.list_tickers.clear()
                for item_data in data["tickers"]:
                    t = item_data["ticker"]
                    chk = item_data.get("checked", True)
                    self._add_ticker_text(t)
                    for i in range(self.list_tickers.count()):
                        if self.list_tickers.item(i).text() == t:
                            self.list_tickers.item(i).setCheckState(Qt.Checked if chk else Qt.Unchecked)
                            break
                            
            if "backtest" in data:
                bt = data["backtest"]
                if "start_date" in bt: self.ed_start.setText(bt["start_date"])
                if "end_date" in bt: self.ed_end.setText(bt["end_date"])
                if "split_date" in bt: self.ed_oos.setText(bt["split_date"])
                if "capital" in bt: self.ed_capital.setText(str(bt["capital"]))
                if "fee" in bt: self.ed_fee.setText(str(bt["fee"]))
                if "tax" in bt: self.ed_tax.setText(str(bt["tax"]))
                if "workers" in bt: self.spin_workers.setValue(int(bt["workers"]))
                # 新增風控讀取
                if "stop_loss" in bt: self.ed_stop_loss.setValue(float(bt["stop_loss"]))
                if "trailing" in bt: self.ed_trailing.setValue(float(bt["trailing"]))
                if "take_profit" in bt: self.ed_take_profit.setValue(float(bt["take_profit"]))
                if "max_days" in bt: self.spin_max_days.setValue(int(bt["max_days"]))
                if "lot_size" in bt: 
                    idx = self.cbo_lot_size.findData(int(bt["lot_size"]))
                    if idx >= 0: self.cbo_lot_size.setCurrentIndex(idx)

            if "strategies" in data:
                for name in self._strategy_widgets.keys():
                    item = self._get_strategy_item(name)
                    if item: item.setCheckState(0, Qt.Unchecked)
                    
                for name, grid in data["strategies"].items():
                    item = self._get_strategy_item(name)
                    if item:
                        item.setCheckState(0, Qt.Checked)
                        w = self._strategy_widgets[name]
                        for key, vals in grid.items():
                            if key in w.param_edits:
                                val_str = ",".join(str(v) for v in vals)
                                w.param_edits[key].setText(val_str)

            self._update_total_combos()
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"讀取失敗：{e}")

    def _get_tickers_data(self) -> list:
        return [{"ticker": self.list_tickers.item(i).text(), "checked": self.list_tickers.item(i).checkState() == Qt.Checked} for i in range(self.list_tickers.count())]

    def _get_backtest_data(self) -> dict:
        return {
            "start_date": self.ed_start.text().strip(),
            "end_date": self.ed_end.text().strip(),
            "split_date": self.ed_oos.text().strip(),
            "capital": self.ed_capital.text().strip(),
            "fee": self.ed_fee.text().strip(),
            "tax": self.ed_tax.text().strip(),
            "workers": self.spin_workers.value(),
            "stop_loss": self.ed_stop_loss.value(),
            "trailing": self.ed_trailing.value(),
            "take_profit": self.ed_take_profit.value(),
            "max_days": self.spin_max_days.value(),
            "lot_size": self.cbo_lot_size.currentData()
        }

    def _get_strategies_data(self) -> dict:
        res = {}
        for name, w in self._strategy_widgets.items():
            item = self._get_strategy_item(name)
            if item and item.checkState(0) == Qt.Checked:
                grid = w.get_grid()
                if grid: res[name] = grid
        return res

    # ================= 股票處理 =================
    def _add_ticker(self):
        text = self.ed_new_ticker.text().strip().upper()
        if text:
            self._add_ticker_text(text)
            self.ed_new_ticker.clear()

    def _batch_add_tickers(self):
        text, ok = QInputDialog.getMultiLineText(self, "批次新增股票", "請輸入股票代號 (換行、逗號分隔):")
        if not ok or not text.strip(): return
        raw = re.split(r'[\s,;\t]+', text.strip())
        added = 0
        for t in raw:
            if self._add_ticker_text(t.strip().upper()): added += 1
        self._save_watchlist()
        QMessageBox.information(self, "完成", f"成功新增 {added} 檔股票。")

    def _add_ticker_text(self, ticker: str) -> bool:
        for i in range(self.list_tickers.count()):
            if self.list_tickers.item(i).text() == ticker: return False
        item = QListWidgetItem(ticker)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        self.list_tickers.addItem(item)
        self._update_total_combos()
        return True

    def _remove_selected_tickers(self):
        for item in self.list_tickers.selectedItems():
            self.list_tickers.takeItem(self.list_tickers.row(item))
        self._save_watchlist()
        self._update_total_combos()

    def _get_checked_tickers(self) -> List[str]:
        return [self.list_tickers.item(i).text() for i in range(self.list_tickers.count()) if self.list_tickers.item(i).checkState() == Qt.Checked]

    def _on_ticker_check_changed(self, item):
        self._update_total_combos()

    def _save_watchlist(self):
        try:
            with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
                json.dump(self._get_tickers_data(), f, ensure_ascii=False, indent=2)
        except Exception: pass

    def _load_watchlist(self):
        if not WATCHLIST_FILE.exists():
            for t in ["2330.TW", "2454.TW", "2317.TW"]: self._add_ticker_text(t)
            return
        try:
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                t, chk = item["ticker"], item.get("checked", True)
                self._add_ticker_text(t)
                for i in range(self.list_tickers.count()):
                    if self.list_tickers.item(i).text() == t:
                        self.list_tickers.item(i).setCheckState(Qt.Checked if chk else Qt.Unchecked)
                        break
        except Exception: pass

    # ================= 策略與執行 =================
    def _init_strategies(self):
        for name, cls in STRATEGY_REGISTRY.items():
            item = QTreeWidgetItem(self.tree_strategies)
            item.setText(1, name)
            item.setCheckState(0, Qt.Unchecked)
            w = StrategyParamWidget(cls)
            w.changed.connect(self._update_total_combos)
            self._strategy_widgets[name] = w
            child = QTreeWidgetItem(item)
            self.tree_strategies.setItemWidget(child, 2, w)
        self.tree_strategies.itemChanged.connect(self._on_tree_item_changed)

    def _on_tree_item_changed(self, item, column):
        if column == 0: self._update_total_combos()

    def _update_total_combos(self):
        try:
            tickers = self._get_checked_tickers()
            total = 0
            for name, w in self._strategy_widgets.items():
                item = self._get_strategy_item(name)
                if item and item.checkState(0) == Qt.Checked:
                    grid = w.get_grid()
                    combos = 1
                    for vals in grid.values(): combos *= len(vals)
                    total += (combos * len(tickers))
            self.lbl_total.setText(f"總組合數：{total}")
        except Exception: pass

    def _get_strategy_item(self, name) -> Optional[QTreeWidgetItem]:
        root = self.tree_strategies.invisibleRootItem()
        for i in range(root.childCount()):
            if root.child(i).text(1) == name: return root.child(i)
        return None

    def _on_run_clicked(self):
        tickers = self._get_checked_tickers()
        if not tickers: return QMessageBox.warning(self, "錯誤", "請至少勾選一支股票。")
        strategy_grids = self._get_strategies_data()
        if not strategy_grids: return QMessageBox.warning(self, "錯誤", "請至少勾選一個策略。")
        
        # 💡 將風控與零股參數傳入 BacktestConfig
        config = BacktestConfig(
            initial_capital=float(self.ed_capital.text() or 1000000),
            fee_rate=float(self.ed_fee.text() or 0.001425),
            tax_rate=float(self.ed_tax.text() or 0.003),
            stop_loss_pct=self.ed_stop_loss.value() if self.ed_stop_loss.value() > 0 else None,
            trailing_stop_pct=self.ed_trailing.value() if self.ed_trailing.value() > 0 else None,
            take_profit_pct=self.ed_take_profit.value() if self.ed_take_profit.value() > 0 else None,
            max_holding_days=self.spin_max_days.value() if self.spin_max_days.value() > 0 else None,
            lot_size=self.cbo_lot_size.currentData()
        )
        
        payload = {
            "tickers": tickers,
            "start_date": self.ed_start.text().strip(),
            "end_date": self.ed_end.text().strip(),
            "split_date": self.ed_oos.text().strip() or None,
            "config": config,
            "strategy_grids": strategy_grids,
            "max_workers": self.spin_workers.value(),
        }
        self.run_requested.emit(payload)

    def set_running(self, running: bool):
        self.btn_run.setEnabled(not running)
        self.btn_cancel.setEnabled(running)
        if running: self.progress.setValue(0)

    def update_progress(self, current: int, total: int):
        self.progress.setMaximum(max(1, total))
        self.progress.setValue(current)
        self.progress.setFormat(f"{current}/{total}")