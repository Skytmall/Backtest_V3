# src/models/matrix_model.py
import math
from typing import List
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from models.leaderboard_model import _metric_value, _higher_is_better


class GridHeatmapModel(QAbstractTableModel):
    """排序網格熱力圖。
    放棄行與列的對應關係，將所有結果按分數降序排列，
    填入固定欄數的網格中，呈現完美的左上紅、右下綠漸變。
    """

    def __init__(self, columns: int = 10):
        super().__init__()
        self._cols = columns
        self._data: List[dict] = []
        self._best_metric = "Sharpe_Ratio"
        self._higher_better = True
        self._color_min = 0.0
        self._color_max = 1.0

    def set_results(self, results: List[dict], best_metric: str = "Sharpe_Ratio") -> None:
        self.beginResetModel()
        self._best_metric = best_metric
        self._higher_better = _higher_is_better(best_metric)

        all_cells = []
        for idx, r in enumerate(results):
            if not r.get("success"):
                continue
            v = _metric_value(r, best_metric)
            all_cells.append({
                "value": v,
                "ticker": r.get("ticker", ""),
                "strat_id": r.get("strat_id", ""),
                "params": r.get("params", {}),
                "orig_index": idx,
            })

        all_cells.sort(key=lambda x: x["value"], reverse=self._higher_better)
        self._data = all_cells

        if all_cells:
            self._color_min = min(c["value"] for c in all_cells)
            self._color_max = max(c["value"] for c in all_cells)
        else:
            self._color_min = self._color_max = 0.0

        self.endResetModel()

    def set_columns(self, cols: int) -> None:
        if cols <= 0 or cols == self._cols:
            return
        self.beginResetModel()
        self._cols = cols
        self.endResetModel()

    def get_cell_by_index(self, row: int, col: int) -> dict | None:
        idx = row * self._cols + col
        if 0 <= idx < len(self._data):
            return self._data[idx]
        return None

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid() or not self._data:
            return 0
        return math.ceil(len(self._data) / self._cols)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else self._cols

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        
        cell = self.get_cell_by_index(index.row(), index.column())
        if cell is None:
            return None

        if role == Qt.DisplayRole:
            # 恢復顯示數值
            return self._fmt(cell["value"])

        if role == Qt.BackgroundRole:
            lo, hi = self._color_min, self._color_max
            if hi == lo:
                return QColor(60, 60, 60)
            
            t = (cell["value"] - lo) / (hi - lo)
            if not self._higher_better:
                t = 1.0 - t

            # 稍微加深顏色，確保白色文字清晰可見
            if t < 0.5:
                r = int(t * 2 * 200)
                g = 180
                b = 50
            else:
                r = 200
                g = int(180 - (t - 0.5) * 2 * 130)
                b = 50
            return QColor(r, g, b)

        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignCenter)

        if role == Qt.ToolTipRole:
            params = ", ".join(f"{k}={v}" for k, v in cell["params"].items())
            return (
                f"策略：{cell['strat_id']}\n"
                f"股票：{cell['ticker']}\n"
                f"參數：{params}\n"
                f"績效：{self._fmt(cell['value'])}"
            )

        if role == Qt.UserRole:
            return cell["orig_index"]

        return None

    def _fmt(self, v: float) -> str:
        if self._best_metric in ("Total_Return", "CAGR", "Max_Drawdown", "Win_Rate"):
            return f"{v:.2%}"
        return f"{v:.2f}"