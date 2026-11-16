# src/models/leaderboard_model.py
from typing import List
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor


# (key, 表頭, 格式)
COLUMNS = [
    ("rank",             "#",         "int"),
    ("ticker",           "股票",       "str"),
    ("strat_id",         "策略",       "str"),
    ("params_str",       "參數",       "str"),
    ("Total_Return",     "總報酬",     "pct"),
    ("CAGR",             "年化",       "pct"),
    ("Sharpe_Ratio",     "夏普",       "num2"),
    ("Max_Drawdown",     "最大回撤",   "pct"),
    ("Total_Trades",     "交易次數",   "int"),
    ("Win_Rate",         "勝率",       "pct"),
    ("Profit_Factor",    "盈虧比",     "num2"),
    ("Trade_Frequency",  "交易頻率",   "num1"),
    ("Execution_Time",   "Time (s)",   "num3"),
]


class LeaderboardModel(QAbstractTableModel):
    """Tab 1 排行榜。每行 = 一個 (策略, 股票, 參數) 結果。"""

    def __init__(self):
        super().__init__()
        self._rows: List[dict] = []
        self._best_metric = "Sharpe_Ratio"

    # ---------- 對外 API ----------
    def set_results(self, results: List[dict], best_metric: str = "Sharpe_Ratio") -> None:
        """results: 全部成功結果（已過濾 success=True）。
        每筆 result 的 index 會被存入 `_rows[i]['_orig_index']`。"""
        self.beginResetModel()
        self._best_metric = best_metric
        self._rows = []

        # 先計算排名（依 best_metric 降序）
        valid = [(i, r) for i, r in enumerate(results) if r.get("success")]
        valid.sort(
            key=lambda x: _metric_value(x[1], best_metric),
            reverse=_higher_is_better(best_metric),
        )

        for rank, (orig_idx, r) in enumerate(valid, 1):
            m = r.get("is", {}).get("metrics", {}) or {}
            self._rows.append({
                "rank":            rank,
                "ticker":          r.get("ticker", ""),
                "strat_id":        r.get("strat_id", ""),
                "params_str":      ", ".join(f"{k}={v}" for k, v in r.get("params", {}).items()),
                "Total_Return":    m.get("Total_Return", 0.0),
                "CAGR":            m.get("CAGR", 0.0),
                "Sharpe_Ratio":    m.get("Sharpe_Ratio", 0.0),
                "Max_Drawdown":    m.get("Max_Drawdown", 0.0),
                "Total_Trades":    int(m.get("Total_Trades", 0)),
                "Win_Rate":        m.get("Win_Rate", 0.0),
                "Profit_Factor":   m.get("Profit_Factor", 0.0),
                "Trade_Frequency": m.get("Trade_Frequency", 0.0),
                "Execution_Time":  r.get("is", {}).get("execution_time"),
                "_orig_index":     orig_idx,
            })
        self.endResetModel()

    def get_orig_index(self, row: int) -> int:
        """回傳該列對應的原始 result index（給 main_window 用）。"""
        return self._rows[row]["_orig_index"]

    # ---------- Qt 介面 ----------
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        key, _title, fmt = COLUMNS[index.column()]
        val = row.get(key, "")

        if role == Qt.DisplayRole:
            return _format(val, fmt)

        if role == Qt.UserRole:
            return val    # 給排序用（傳原始值）

        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignCenter)

        if role == Qt.ForegroundRole:
            color = _cell_color(key, val)
            if color is not None:
                return color

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None
        return COLUMNS[section][1]


# ============ 內部工具 ============

def _format(val, fmt: str) -> str:
    if fmt == "pct":
        return f"{val:.2%}" if isinstance(val, float) else str(val)
    if fmt == "num2":
        return f"{val:.2f}" if isinstance(val, float) else str(val)
    if fmt == "num1":
        return f"{val:.1f}" if isinstance(val, float) else str(val)
    if fmt == "num3":
        return f"{val:.3f}" if isinstance(val, (int, float)) else "—"
    if fmt == "int":
        return str(int(val)) if isinstance(val, (int, float)) else str(val)
    return str(val)


def _cell_color(key: str, val):
    if key == "Total_Return" and isinstance(val, float):
        return QColor("#00e676") if val > 0 else QColor("#ff1744")
    if key == "Sharpe_Ratio" and isinstance(val, float) and val > 1.0:
        return QColor("#00e676")
    if key == "Max_Drawdown" and isinstance(val, float) and val < -0.30:
        return QColor("#ff1744")
    if key == "Win_Rate" and isinstance(val, float) and val > 0.55:
        return QColor("#00e676")
    if key == "Profit_Factor" and isinstance(val, float) and val > 1.5:
        return QColor("#00e676")
    return None


def _metric_value(result: dict, metric: str) -> float:
    m = result.get("is", {}).get("metrics", {}) or {}
    v = m.get(metric, 0.0)
    return float(v) if isinstance(v, (int, float)) else 0.0


def _higher_is_better(metric: str) -> bool:
    """Max_Drawdown 是唯一越小越好的指標。"""
    return metric != "Max_Drawdown"