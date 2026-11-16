# src/models/table_models.py
import pandas as pd
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex


class PandasTableModel(QAbstractTableModel):
    """把 DataFrame 塞進 QTableView 的最小實作。"""

    def __init__(self, df: pd.DataFrame | None = None):
        super().__init__()
        self._df = df.reset_index(drop=True) if df is not None else pd.DataFrame()

    def set_dataframe(self, df: pd.DataFrame | None) -> None:
        self.beginResetModel()
        self._df = df.reset_index(drop=True) if df is not None else pd.DataFrame()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._df)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._df.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            v = self._df.iat[index.row(), index.column()]
            if isinstance(v, float):
                return f"{v:.4f}"
            return str(v)
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignCenter)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self._df.columns[section])
        return str(section + 1)