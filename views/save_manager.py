# src/views/save_manager.py
import os
import shutil
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QIcon, QDrag
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QMenu,
    QInputDialog, QMessageBox, QFileDialog, QSplitter, QAbstractItemView
)

from core.paths import SAVES_DIR

class SaveManagerPanel(QWidget):
    # 發出信號讓 MainWindow 處理切換與載入
    load_env_requested = Signal(str)
    load_backtest_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self._build_ui()
        self._refresh_tree()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # ================= 頂部工具列 =================
        toolbar = QHBoxLayout()
        btn_new_folder = QPushButton("📁 新增資料夾")
        btn_new_folder.clicked.connect(self._create_folder)
        btn_refresh = QPushButton("🔄 重新整理")
        btn_refresh.clicked.connect(self._refresh_tree)
        btn_import = QPushButton("📂 從電腦匯入檔案")
        btn_import.clicked.connect(self._import_files)

        toolbar.addWidget(btn_new_folder)
        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_import)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # ================= 左右分割視窗 =================
        splitter = QSplitter(Qt.Horizontal)
        
        # 左側：資料夾樹
        self.tree_folders = QTreeWidget()
        self.tree_folders.setHeaderLabels(["資料夾"])
        self.tree_folders.setColumnWidth(0, 200)
        self.tree_folders.itemClicked.connect(self._on_folder_clicked)
        self.tree_folders.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_folders.customContextMenuRequested.connect(self._on_tree_context_menu)
        # 允許拖放接收
        self.tree_folders.setAcceptDrops(True)
        self.tree_folders.setDragDropMode(QAbstractItemView.DropOnly)
        self.tree_folders.dropEvent = self._on_tree_drop
        splitter.addWidget(self.tree_folders)

        # 右側：檔案列表
        self.table_files = QTableWidget()
        self.table_files.setColumnCount(4)
        self.table_files.setHorizontalHeaderLabels(["檔名", "類型", "修改時間", "大小(KB)"])
        self.table_files.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_files.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_files.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_files.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_files.doubleClicked.connect(self._on_file_double_clicked)
        self.table_files.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_files.customContextMenuRequested.connect(self._on_file_context_menu)
        # 允許拖出
        self.table_files.setDragEnabled(True)
        self.table_files.setDragDropMode(QAbstractItemView.DragOnly)
        splitter.addWidget(self.table_files)

        splitter.setSizes([200, 800])
        layout.addWidget(splitter)

        self._current_folder_path = str(SAVES_DIR)

    # ================= 資料夾樹邏輯 =================
    def _refresh_tree(self):
        """重新掃描 SAVES_DIR 並建立樹狀結構。"""
        self.tree_folders.clear()
        root_path = Path(SAVES_DIR)
        
        # 建立根節點
        root_item = QTreeWidgetItem(self.tree_folders)
        root_item.setText(0, "📁 全部存檔")
        root_item.setData(0, Qt.UserRole, str(root_path))
        root_item.setExpanded(True)
        
        self._build_tree_recursive(str(root_path), root_item)
        
        # 預設選中根節點並載入檔案
        self.tree_folders.setCurrentItem(root_item)
        self._current_folder_path = str(root_path)
        self._refresh_files()

    def _build_tree_recursive(self, current_path: str, parent_item: QTreeWidgetItem):
        """遞迴掃描子資料夾。"""
        try:
            for entry in os.scandir(current_path):
                if entry.is_dir():
                    item = QTreeWidgetItem(parent_item)
                    item.setText(0, f"📁 {entry.name}")
                    item.setData(0, Qt.UserRole, entry.path)
                    self._build_tree_recursive(entry.path, item)
        except Exception:
            pass

    def _on_folder_clicked(self, item, column):
        path = item.data(0, Qt.UserRole)
        if path and os.path.exists(path):
            self._current_folder_path = path
            self._refresh_files()

    def _create_folder(self):
        """在當前選中的資料夾下建立新資料夾。"""
        name, ok = QInputDialog.getText(self, "新增資料夾", "請輸入資料夾名稱:")
        if ok and name.strip():
            new_path = Path(self._current_folder_path) / name.strip()
            try:
                new_path.mkdir(parents=True, exist_ok=True)
                self._refresh_tree()
                # 這裡可以做個展開的動作，但為了簡單先略過
            except Exception as e:
                QMessageBox.critical(self, "錯誤", f"無法建立資料夾：{e}")

    def _on_tree_context_menu(self, pos):
        item = self.tree_folders.itemAt(pos)
        if not item: return
        path = Path(item.data(0, Qt.UserRole))
        
        # 不允許對根目錄操作
        if path == SAVES_DIR: return

        menu = QMenu()
        act_rename = menu.addAction("✏️ 重新命名")
        act_delete = menu.addAction("🗑️ 刪除資料夾")
        
        action = menu.exec_(self.tree_folders.mapToGlobal(pos))
        if action == act_rename:
            new_name, ok = QInputDialog.getText(self, "重新命名", "新名稱:", text=path.name)
            if ok and new_name.strip():
                new_path = path.parent / new_name.strip()
                try:
                    path.rename(new_path)
                    self._refresh_tree()
                except Exception as e:
                    QMessageBox.critical(self, "錯誤", f"重命名失敗：{e}")
        elif action == act_delete:
            reply = QMessageBox.question(self, "確認", f"確定要刪除資料夾 '{path.name}' 及裡面所有檔案嗎？", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                try:
                    shutil.rmtree(path)
                    self._refresh_tree()
                except Exception as e:
                    QMessageBox.critical(self, "錯誤", f"刪除失敗：{e}")

    # ================= 檔案列表邏輯 =================
    def _refresh_files(self):
        self.table_files.setRowCount(0)
        folder = Path(self._current_folder_path)
        if not folder.exists(): return

        try:
            files = [f for f in folder.iterdir() if f.is_file()]
            # 排序：最近修改的排前面
            files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            for row, f in enumerate(files):
                self.table_files.insertRow(row)
                stat = f.stat()
                
                # 判斷類型
                if f.name.endswith(".pkl"):
                    f_type = "📊 回測結果"
                elif f.name.endswith(".json"):
                    f_type = "⚙️ 參數設定"
                else:
                    f_type = "📄 未知"
                    
                import datetime
                mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                size_kb = f"{stat.st_size / 1024:.1f}"
                
                self.table_files.setItem(row, 0, QTableWidgetItem(f.name))
                self.table_files.setItem(row, 1, QTableWidgetItem(f_type))
                self.table_files.setItem(row, 2, QTableWidgetItem(mtime))
                self.table_files.setItem(row, 3, QTableWidgetItem(size_kb))
                
                # 把完整路徑存在第一格
                self.table_files.item(row, 0).setData(Qt.UserRole, str(f))
        except Exception:
            pass

    def _on_file_double_clicked(self, index):
        row = index.row()
        file_path = self.table_files.item(row, 0).data(Qt.UserRole)
        if not file_path: return

        if file_path.endswith(".json"):
            self.load_env_requested.emit(file_path)
        elif file_path.endswith(".pkl"):
            self.load_backtest_requested.emit(file_path)

    def _on_file_context_menu(self, pos):
        menu = QMenu()
        act_rename = menu.addAction("✏️ 重新命名")
        act_delete = menu.addAction("🗑️ 刪除選取")
        
        action = menu.exec_(self.table_files.mapToGlobal(pos))
        if action == act_rename:
            self._rename_selected_file()
        elif action == act_delete:
            self._delete_selected_files()

    def _rename_selected_file(self):
        row = self.table_files.currentRow()
        if row < 0: return
        item = self.table_files.item(row, 0)
        old_path = Path(item.data(Qt.UserRole))
        
        new_name, ok = QInputDialog.getText(self, "重新命名", "新檔名:", text=old_path.name)
        if ok and new_name.strip():
            new_path = old_path.parent / new_name.strip()
            try:
                old_path.rename(new_path)
                self._refresh_files()
            except Exception as e:
                QMessageBox.critical(self, "錯誤", f"重新命名失敗：{e}")

    def _delete_selected_files(self):
        selected_rows = set(index.row() for index in self.table_files.selectedIndexes())
        if not selected_rows: return
        
        reply = QMessageBox.question(self, "確認", f"確定要刪除選取的 {len(selected_rows)} 個檔案嗎？", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            for row in selected_rows:
                path = self.table_files.item(row, 0).data(Qt.UserRole)
                try:
                    os.remove(path)
                except Exception:
                    pass
            self._refresh_files()

    # ================= 匯入與拖拽 =================
    def _import_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "匯入檔案", "", "支援的檔案 (*.json *.pkl);;所有檔案 (*.*)"
        )
        if not paths: return
        
        for p in paths:
            try:
                dest = Path(self._current_folder_path) / Path(p).name
                shutil.copy2(p, dest)
            except Exception as e:
                QMessageBox.warning(self, "錯誤", f"匯入 {Path(p).name} 失敗：{e}")
        self._refresh_files()

    def _on_tree_drop(self, event):
        """處理把右側檔案拖拽到左側資料夾的邏輯。"""
        target_item = self.tree_folders.itemAt(event.position().toPoint())
        if not target_item:
            return
            
        target_path = Path(target_item.data(0, Qt.UserRole))
        if not target_path.is_dir(): return

        # 獲取拖拽的檔案路徑
        mime_data = event.mimeData()
        if not mime_data.hasUrls(): return

        for url in mime_data.urls():
            src_path = Path(url.toLocalFile())
            if src_path.is_file():
                try:
                    dest = target_path / src_path.name
                    # 如果同名，自動加後綴
                    if dest.exists():
                        import time
                        dest = target_path / f"{src_path.stem}_{int(time.time())}{src_path.suffix}"
                    shutil.move(str(src_path), str(dest))
                except Exception as e:
                    QMessageBox.warning(self, "移動失敗", str(e))
                    
        self._refresh_files()
        self._refresh_tree()