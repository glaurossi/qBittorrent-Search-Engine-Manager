from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def apply_dark_theme(app: QApplication) -> None:
    """Apply global app palette and stylesheet.

    Keep all static visual rules in one place so window code only sets state
    via widget properties (for example rowStatus=installed/unavailable).
    """
    app.setStyle("Fusion")
    pal = QPalette()
    window = QColor("#1a1d1f")
    base = QColor("#25282c")
    text = QColor("#e8eaed")
    muted = QColor("#9aa0a6")
    accent = QColor("#437AD2")
    disabled = QColor("#6b7280")

    pal.setColor(QPalette.ColorRole.Window, window)
    pal.setColor(QPalette.ColorRole.WindowText, text)
    pal.setColor(QPalette.ColorRole.Base, base)
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#2d3339"))
    pal.setColor(QPalette.ColorRole.Text, text)
    pal.setColor(QPalette.ColorRole.Button, QColor("#2d3339"))
    pal.setColor(QPalette.ColorRole.ButtonText, text)
    pal.setColor(QPalette.ColorRole.Highlight, accent)
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, muted)
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled)
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled)
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled)

    app.setPalette(pal)

    app.setStyleSheet(
        """
        QTabWidget::pane { top: 0px; left: 0px; border: none; }
        QTabWidget::tab-bar { left: 0px; top: 0px; }
        QTabBar { border-bottom: 1px solid #3d4450; }

        QTabBar::tab {
            background: #2d2d2d;
            color: #e8eaed;
            padding: 6px 14px;
            margin-right: 2px;
            margin-bottom: 0px;
            background-color: #25282c;
        }

        QTabBar::tab:selected { background: #3c3c3c; }

        QPushButton {
            padding: 8px 16px;
            min-height: 22px;
            background-color: #2d3339;
            color: #e8eaed;
            border: none;
            border-radius: 4px;
        }
        QPushButton#browsePathButton {
            padding-top: 0px;
            padding-bottom: 0px;
            min-height: 32px;
        }

        QPushButton:hover {
            background-color: #3d4450;
        }

        QPushButton:pressed {
            background-color: #2d3339;
        }

        QPushButton#accent {
            background-color: #3b82f6;
            color: #ffffff;
        }

        QPushButton#accent:hover {
            background-color: #2563eb;
        }

        QPushButton#accent:pressed {
            background-color: #1d4ed8;
        }

        QGroupBox {
            font-weight: bold;
            border: 1px solid #3d4450;
            margin-top: 8px;
            padding-top: 8px;
            background-color: #25282c;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
            color: #9aa0a6;
            font-weight: normal;
            font-size: 11px;
        }

        QScrollArea { border: none; background: #1a1d1f; }

        QLineEdit {
            padding: 6px 8px;
            border: 1px solid #3d4450;
            border-radius: 4px;
        }

        QPlainTextEdit {
            background: #25282c; color: #e8eaed;
            border: 1px solid #3d4450;
            border-radius: 4px;
            padding: 8px;
        }

        QProgressBar {
            background-color: #2d3339;
            border: none;
            border-radius: 3px;
            min-height: 6px;
            max-height: 6px;
        }
        QProgressBar::chunk { background-color: #3b82f6; border-radius: 3px; }

        QCheckBox#engineRow { spacing: 10px; }
        QCheckBox[rowStatus="available"] { color: #e8eaed; }
        QCheckBox[rowStatus="installed"] { color: #22c55e; }
        QCheckBox[rowStatus="unavailable"] { color: #ef4444; }
        QCheckBox:disabled[rowStatus="installed"] { color: #22c55e; }
        QCheckBox:disabled[rowStatus="unavailable"] { color: #ef4444; }

        QCheckBox#showLogToggle {
            margin: 0;
            padding: 0;
            spacing: 6px;
            min-height: 20px;
        }

        QCheckBox#showLogToggle::indicator {
            margin: 0;
        }

        QToolButton#helpButton {
            border: none;
            border-radius: 4px;
            background: transparent;
            color: #9aa0a6;
            font-weight: bold;
            font-size: 14px;
            padding: 2px;
        }

        QToolButton#helpButton:hover {
            background: #2d3339;
            color: #e8eaed;
        }

        #helpBackdrop { background-color: rgba(26, 29, 31, 0.72); }
        #helpCard {
            background-color: #25282c;
            border: 1px solid #3d4450;
            border-radius: 8px;
        }

        QLabel#helpTitle {
            margin-top: 0;
            font-size: 16px;
            font-weight: bold;
            color: #e8eaed;
        }

        #helpCard QLabel#helpBody {
            margin-top: 0;
            color: #e8eaed;
            font-size: 13px;
        }

        #helpCard a { color: #60a5fa; text-decoration: none; }
        #helpCard a:hover { text-decoration: underline; }

        QLabel#helpMuted {
            margin-top: 0;
            color: #9aa0a6;
            font-size: 11px;
        }

        QLabel#appHeaderTitle {
            color: #e8eaed;
            font-size: 15px;
            font-weight: bold;
        }
        """
    )
