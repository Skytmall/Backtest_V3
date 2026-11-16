# src/main.py
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from PySide6.QtCore import Qt, QCoreApplication
QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

from PySide6.QtWidgets import QApplication
from strategies.loader import load_all_strategies
from views.main_window import MainWindow

def main():
    load_all_strategies()
    
    app = QApplication(sys.argv)
    app.setApplicationName("台股量化回測 V3")
    
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()