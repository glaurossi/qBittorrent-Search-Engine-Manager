import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from qbt_search_manager import APP_NAME_FULL, APP_ORG_NAME
from qbt_search_manager.ui.main import MainWindow
from qbt_search_manager.ui.theme import apply_dark_theme


def _load_application_icon() -> QIcon:
    icon_path = Path(__file__).resolve().parent / "assets" / "icons" / "app_icon.svg"
    icon = QIcon(str(icon_path))
    return icon if not icon.isNull() else QIcon()


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME_FULL)
    app.setApplicationDisplayName(APP_NAME_FULL)
    app.setOrganizationName(APP_ORG_NAME)
    app_icon = _load_application_icon()
    app.setWindowIcon(app_icon)
    sh = app.styleHints()
    if hasattr(sh, "setToolTipShowDelay"):
        sh.setToolTipShowDelay(1000)
    apply_dark_theme(app)
    w = MainWindow()
    w.setWindowIcon(app_icon)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
