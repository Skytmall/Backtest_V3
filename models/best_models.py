# src/models/best_models.py
from typing import List, Dict, Tuple
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from models.leaderboard_model import _metric_value, _higher_is_better, _format


class _BestModel(QAbstractTableModel):
    """Tab 3 / Tab 4 共用基底。子類別定義 group_key 是「股票」還是「策略」。"""

    group_key: str = ""       # "ticker" 或 "strat_id"
    peer_key:  str = ""       # 對應的另一維

    def __init__(self):
        super().__init__()
        self._rows: List[dict] = []
        self._best_metric = "Sharpe_Ratio"

    def set_results(self, results: List[dict], best_metric: str = "Sharpe_Ratio") -> None:
        self.beginResetModel()
        self._best_metric = best_metric
        higher = _higher_is_better(best_metric)

        # 按 group_key 分組，並記錄原始 index
        groups: Dict[str, List[dict]] = {}
        for idx, r in enumerate(results):
            if not r.get("success"):
                continue
            r_copy = r.copy()
            r_copy["_orig_index"] = idx
            groups.setdefault(r[self.group_key], []).append(r_copy)

        self._rows = []
        for g, rs in groups.items():
            rs.sort(key=lambda x: _metric_value(x, best_metric), reverse=higher)
            best = rs[0]
            second = rs[1] if len(rs) > 1 else None

            best_v = _metric_value(best, best_metric)
            second_v = _metric_value(second, best_metric) if second else None
            gap = (best_v - second_v) if (second and second_v is not None) else None
            if gap is not None and not higher:
                gap = -gap

            peers = {r[self.peer_key] for r in rs}
            avg = sum(_metric_value(r, best_metric) for r in rs) / len(rs) if rs else 0.0

            self._rows.append({
                "group":       g,
                "best":        best,
                "best_v":      best_v,
                "second":      second,
                "second_v":    second_v,
                "gap":         gap,
                "peer_count":  len(peers),
                "avg":         avg,
            })

        self._rows.sort(key=lambda x: x["best_v"], reverse=higher)
        self.endResetModel()

    def get_result(self, row: int) -> dict | None:
        """回傳該列「最佳」的原始 result dict。"""
        if 0 <= row < len(self._rows):
            return self._rows[row]["best"]
        return None

    # ==== 新增這個方法 ====
    def get_orig_index(self, row: int) -> int:
        if 0 <= row < len(self._rows):
            return self._rows[row]["best"].get("_orig_index", -1)
        return -1

    # ---------- Qt 介面 ----------
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._columns())

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col_def = self._columns()[index.column()]
        key, _title, fmt = col_def

        if role == Qt.DisplayRole:
            v = self._get_value(row, key)
            return _format(v, fmt) if not isinstance(v, str) else v

        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignCenter)

        if role == Qt.ForegroundRole and key == "gap":
            v = self._get_value(row, key)
            if isinstance(v, float):
                return QColor("#00e676") if v > 0 else QColor("#ff1744")

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None
        return self._columns()[section][1]

    # ---------- 子類別覆寫 ----------
    def _columns(self) -> List[Tuple[str, str, str]]:
        raise NotImplementedError

    def _get_value(self, row: dict, key: str):
        """從 row dict 取出指定 key 的值。"""
        best = row["best"]
        second = row["second"]
        if key == "group":
            return row["group"]
        if key == "best_peer":
            return best.get(self.peer_key, "")
        if key == "best_params":
            return ", ".join(f"{k}={v}" for k, v in best.get("params", {}).items())
        if key == "best_value":
            return row["best_v"]
        if key == "second_peer":
            return second.get(self.peer_key, "") if second else "—"
        if key == "second_value":
            return row["second_v"] if second else None
        if key == "gap":
            return row["gap"]
        if key == "avg":
            return row["avg"]
        return None


class StockBestModel(_BestModel):
    """Tab 3：個股最佳策略。
    每行 = 一支股票，欄位顯示它的最佳策略 + 第二強策略。"""

    group_key = "ticker"
    peer_key  = "strat_id"

    def _columns(self):
        return [
            ("group",        "股票",       "str"),
            ("best_peer",    "最佳策略",   "str"),
            ("best_params",  "最佳參數",   "str"),
            ("best_value",   "績效",       "num2"),
            ("second_peer",  "第二名策略", "str"),
            ("second_value", "第二名績效", "num2"),
            ("gap",          "差距",       "num2"),
        ]


class StrategyBestModel(_BestModel):
    """Tab 4：策略最佳個股。
    每行 = 一個策略，欄位顯示它的最佳股票 + 第二強股票 + 全股票平均。"""

    group_key = "strat_id"
    peer_key  = "ticker"

    def _columns(self):
        return [
            ("group",        "策略",       "str"),
            ("best_peer",    "最佳股票",   "str"),
            ("best_params",  "最佳參數",   "str"),
            ("best_value",   "績效",       "num2"),
            ("second_peer",  "第二名股票", "str"),
            ("second_value", "第二名績效", "num2"),
            ("gap",          "差距",       "num2"),
            ("avg",          "全股票平均", "num2"),
        ]