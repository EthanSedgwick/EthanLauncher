import os
import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from scr.mainWindow import GameLauncher

def apply_dark_theme(app):
    dark_style = """
    QWidget {
        background-color: #2E2E2E;
        color: #FFFFFF;
    }
    QMainWindow {
        background-color: #2E2E2E;
        color: #FFFFFF;
    }
    QWindow {
        background-color: #2E2E2E;
        color: #FFFFFF;
    }
    QStatusBar {
        background-color: #333333;
        color: #FFFFFF;
    }
    QPushButton {
        background-color: #444444;
        color: #FFFFFF;
    }
    QPushButton:hover {
        background-color: #555555;
    }
    QLineEdit {
        background-color: #333333;
        color: #FFFFFF;
    }
    """
    app.setStyleSheet(dark_style)
    _app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    app.setWindowIcon(QIcon(os.path.join(_app_dir, "scr", "icon.ico")))

      
if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = GameLauncher()
    apply_dark_theme(app)
    ex.show()
    sys.exit(app.exec())


