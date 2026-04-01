"""Main window"""

from __future__ import annotations

import html
import threading
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt, QTimer, Signal, QSettings
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QIcon,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from qbt_search_manager import (
    APP_NAME_FULL,
    APP_AUTHOR_DISPLAY,
    HELP_LINK_GITHUB,
    HELP_LINK_DONATE,
    __version__,
)
from qbt_search_manager.core.install import (
    expected_dest_path,
    install_plugin,
    is_plugin_installed,
    pick_download_url,
    remove_installed_plugin,
)
from qbt_search_manager.core.net import fetch_bytes, fetch_text, probe_url_status
from qbt_search_manager.core.paths import default_engines_dir
from qbt_search_manager.core.shell_open import open_folder_in_file_manager
from qbt_search_manager.core.wiki_parser import (
    WIKI_URL,
    PluginRow,
    parse_wiki,
    plain_author_display,
)

# 16×16: generic search glyph (no bundled asset, no qBittorrent trademark).
_DEFAULT_ENGINE_ICON: QIcon | None = None
_ENGINE_ICON_PX = QSize(16, 16)


def _default_engine_icon() -> QIcon:
    global _DEFAULT_ENGINE_ICON
    if _DEFAULT_ENGINE_ICON is not None:
        return _DEFAULT_ENGINE_ICON
    pm = QPixmap(16, 16)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor("#8b9299"))
    pen.setWidth(1)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(1, 1, 8, 8)
    p.drawLine(8, 8, 14, 14)
    p.end()
    _DEFAULT_ENGINE_ICON = QIcon(pm)
    return _DEFAULT_ENGINE_ICON


class _HelpDimBackdrop(QWidget):
    """Full-window dim; click outside the card dismisses help."""

    def __init__(
        self, on_dismiss: Callable[[], None], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._on_dismiss = on_dismiss
        self._card: QWidget | None = None

    def set_card(self, card: QWidget) -> None:
        self._card = card

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._card is None:
            super().mousePressEvent(event)
            return
        w = self.childAt(event.pos())
        if w is None:
            self._on_dismiss()
            return
        p: QWidget | None = w
        while p is not None:
            if p is self._card:
                super().mousePressEvent(event)
                return
            p = p.parentWidget()
        self._on_dismiss()


class _PluginRow(QWidget):
    """Plugin list row; right-click shows remove when that engine is installed."""

    def __init__(
        self,
        main: MainWindow,
        row: PluginRow,
        installed: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._main = main
        self._row = row
        self._installed = installed

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        if self._installed:
            self._main._offer_remove_engine(self._row, event.globalPos())
        else:
            super().contextMenuEvent(event)


class _LabelToggleEventFilter(QObject):
    """QCheckBox"""

    def __init__(self, checkbox: QCheckBox) -> None:
        super().__init__(checkbox)
        self._cb = checkbox

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if not self._cb.isEnabled():
            return False
        if event.type() != QEvent.Type.MouseButtonRelease:
            return False
        if not isinstance(event, QMouseEvent):
            return False
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        self._cb.setChecked(not self._cb.isChecked())
        return True


class _Bridge(QObject):
    """Thread-safe signals into the GUI thread."""

    log_line = Signal(str)
    fetch_done = Signal(object, object)
    fetch_failed = Signal(str)
    install_finished = Signal()
    icon_ready = Signal(
        int, int, int, object
    )  # generation, tab index, row index, bytes|None
    url_health_ready = Signal(int, int, int, str)  # generation, tab, row, status


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        # Persistent UI settings.
        self._settings = QSettings("qbt-plugin-tool-qt")
        self.setWindowTitle(APP_NAME_FULL)
        self.resize(920, 500)
        self.setMinimumSize(720, 500)
        self._bridge = _Bridge()
        self._bridge.fetch_done.connect(self._on_fetch_done)
        self._bridge.fetch_failed.connect(self._on_fetch_failed)
        self._bridge.log_line.connect(self._append_log)
        self._bridge.install_finished.connect(self._on_install_finished)
        self._bridge.icon_ready.connect(self._on_icon_ready)
        self._bridge.url_health_ready.connect(self._on_url_health_ready)
        self._rows_public: list[PluginRow] = []
        self._rows_private: list[PluginRow] = []
        self._checks_public: list[QCheckBox] = []
        self._checks_private: list[QCheckBox] = []
        self._labels_public: list[QLabel] = []
        self._labels_private: list[QLabel] = []
        self._installed_public: list[bool] = []
        self._installed_private: list[bool] = []
        self._pending_private_reminder = False
        self._successful_private_installs = 0
        self._failed_installs = 0
        # In-memory icon cache keyed by icon URL.
        self._icon_cache: dict[str, QIcon | None] = {}
        self._url_health_cache: dict[str, str] = {}
        self._url_health_inflight: set[str] = set()
        self._list_generation = 0
        # List-load overlay: 1 step for wiki+populate, +1 per icon HTTP thread.
        self._list_loading = False
        self._list_load_total_steps = 1
        self._list_load_done_steps = 0
        self._list_load_icon_threads = 0

        self._build_ui()
        self._restore_window_geometry()
        sc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
        sc.activated.connect(self._hide_help_if_visible)
        QTimer.singleShot(200, self._load_list_async)

    def _get_setting_bool(self, key: str, default: bool) -> bool:
        value = self._settings.value(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _restore_window_geometry(self) -> None:
        data = self._settings.value("windowGeometry")
        if data:
            self.restoreGeometry(data)

    def _save_window_geometry(self) -> None:
        self._settings.setValue("windowGeometry", self.saveGeometry())

    def moveEvent(self, event) -> None:
        self._save_window_geometry()
        super().moveEvent(event)

    def resizeEvent(self, event) -> None:
        self._save_window_geometry()
        self._sync_list_overlay_geometry()
        self._sync_help_backdrop_geometry()
        super().resizeEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._tabs and event.type() == QEvent.Type.Resize:
            self._sync_list_overlay_geometry()
        return False

    def _sync_list_overlay_geometry(self) -> None:
        if hasattr(self, "_list_overlay"):
            self._list_overlay.setGeometry(self._tabs.rect())

    def _sync_help_backdrop_geometry(self) -> None:
        c = self.centralWidget()
        if c and getattr(self, "_help_backdrop", None):
            self._help_backdrop.setGeometry(c.rect())

    def _hide_help_if_visible(self) -> None:
        if getattr(self, "_help_backdrop", None) and self._help_backdrop.isVisible():
            self._hide_help_panel()

    def _show_help_panel(self) -> None:
        self._sync_help_backdrop_geometry()
        self._help_backdrop.raise_()
        self._help_backdrop.show()

    def _hide_help_panel(self) -> None:
        self._help_backdrop.hide()

    def closeEvent(self, event) -> None:
        self._save_window_geometry()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        # Layout + controls only. Styling is centralized in theme.py.
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 14, 16, 10)
        root.setSpacing(8)

        header = QHBoxLayout()
        app_title = QLabel(APP_NAME_FULL)
        app_title.setObjectName("appHeaderTitle")
        header.addWidget(app_title, alignment=Qt.AlignmentFlag.AlignVCenter)
        header.addStretch(1)
        self._help_btn = QToolButton()
        self._help_btn.setObjectName("helpButton")
        self._help_btn.setText("?")
        self._help_btn.setFixedSize(28, 28)
        self._help_btn.setToolTip("Quick tips about this app")
        self._help_btn.clicked.connect(self._show_help_panel)
        header.addWidget(self._help_btn)
        root.addLayout(header)
        top_row_gap = 10
        root.addSpacing(top_row_gap)

        root.addWidget(QLabel("<b>Search Engines folder</b>"))

        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(6)
        self._path_edit = QLineEdit(str(default_engines_dir()))
        self._path_edit.setObjectName("enginesPathEdit")
        self._path_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        browse = QPushButton("Browse…")
        browse.setObjectName("browsePathButton")
        path_h = self._path_edit.sizeHint().height()
        self._path_edit.setFixedHeight(path_h)
        browse.setFixedHeight(path_h)
        browse.clicked.connect(self._browse)
        va = Qt.AlignmentFlag.AlignVCenter
        path_row.addWidget(self._path_edit, 1, va)
        path_row.addWidget(browse, 0, va)
        root.addLayout(path_row)

        btn_row = QHBoxLayout()
        self._reload_btn = QPushButton("Reload List")
        self._reload_btn.clicked.connect(self._load_list_async)
        self._install_btn = QPushButton("Install selected")
        self._install_btn.setObjectName("accent")
        self._install_btn.setAutoDefault(True)
        self._install_btn.clicked.connect(self._install_async)
        btn_row.addWidget(self._reload_btn)
        btn_row.addWidget(self._install_btn)
        root.addLayout(btn_row)

        legend = QLabel(
            '<span style="color:#e8eaed;">Available</span>'
            "  |  "
            '<span style="color:#22c55e;">Installed</span>'
            "  |  "
            '<span style="color:#ef4444;">Unavailable</span>'
        )
        legend.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(legend)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.tabBar().setDrawBase(False)

        self._tab_public, self._content_public, self._lay_public = (
            self._make_plugin_tab("Search Engines")
        )
        self._tab_private, self._content_private, self._lay_private = (
            self._make_plugin_tab("Search Engines")
        )

        self._tabs.addTab(self._tab_public, "Public")
        self._tabs.addTab(self._tab_private, "Private")
        root.addWidget(self._tabs, stretch=1)

        self._list_overlay = QWidget(self._tabs)
        self._list_overlay.setObjectName("listLoadOverlay")
        self._list_overlay.hide()
        self._list_overlay.setStyleSheet(
            "#listLoadOverlay { background-color: rgba(26, 29, 31, 0.94); }"
        )
        ol = QVBoxLayout(self._list_overlay)
        ol.addStretch(1)
        mid = QHBoxLayout()
        mid.addStretch(1)
        stack = QVBoxLayout()
        stack.setSpacing(10)
        self._list_progress_label = QLabel("Loading…")
        self._list_progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._list_progress_label.setStyleSheet("color: #9aa0a6; font-size: 12px;")
        self._list_progress = QProgressBar()
        self._list_progress.setFixedWidth(280)
        self._list_progress.setTextVisible(False)
        stack.addWidget(self._list_progress_label)
        stack.addWidget(self._list_progress)
        mid.addLayout(stack)
        mid.addStretch(1)
        ol.addLayout(mid)
        ol.addStretch(1)
        self._tabs.installEventFilter(self)

        self._help_card = QWidget()
        self._help_card.setObjectName("helpCard")
        self._help_card.setFixedWidth(440)
        hl = QVBoxLayout(self._help_card)
        hl.setContentsMargins(20, 20, 20, 16)
        hl.setSpacing(12)
        ht = QLabel("About this app")
        ht.setObjectName("helpTitle")
        hb = QLabel()
        hb.setObjectName("helpBody")
        hb.setWordWrap(True)
        hb.setTextFormat(Qt.TextFormat.RichText)
        hb.setOpenExternalLinks(True)
        gh = (
            html.escape(HELP_LINK_GITHUB.strip(), quote=True)
            if HELP_LINK_GITHUB.strip()
            else ""
        )
        kf = (
            html.escape(HELP_LINK_DONATE.strip(), quote=True)
            if HELP_LINK_DONATE.strip()
            else ""
        )
        link_bits: list[str] = []
        if gh:
            link_bits.append(f'<a href="{gh}">GitHub</a>')
        if kf:
            link_bits.append(f'<a href="{kf}">Donate</a>')
        links_line = (" · ".join(link_bits)) if link_bits else ""
        hb.setText(
            "<p style='margin:0 0 30 0;'>"
            "A focused GUI to manage community qBittorrent search engines."
            "<p style='margin:0 0 20 0;'>"
            " · Right-click an <b>installed</b> plugin and select "
            "'Remove Plugin' to remove it."
            "<p style='margin:0 0 100px 0;'>"
            " · Hover a plugin to check its compatibility status.</p>"
            + (
                f"<p style='margin:0 0 10px 0;'>{links_line}</p>"
                if links_line
                else ("<p style='margin:0 0 10px 0;color:#9aa0a6;font-size:12px;'>")
            )
        )
        hm = QLabel(f"Made by {APP_AUTHOR_DISPLAY} · v {__version__}")
        hm.setObjectName("helpMuted")
        close_row = QHBoxLayout()
        close_row.addStretch(1)
        h_close = QPushButton("Close")
        h_close.setDefault(True)
        h_close.clicked.connect(self._hide_help_panel)
        close_row.addWidget(h_close)
        hl.addWidget(ht)
        hl.addWidget(hb)
        hl.addWidget(hm)
        hl.addLayout(close_row)

        self._help_backdrop = _HelpDimBackdrop(self._hide_help_panel, central)
        self._help_backdrop.setObjectName("helpBackdrop")
        self._help_backdrop.set_card(self._help_card)
        self._help_backdrop.hide()
        bl = QVBoxLayout(self._help_backdrop)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.addStretch(1)
        bh = QHBoxLayout()
        bh.addStretch(1)
        bh.addWidget(self._help_card)
        bh.addStretch(1)
        bl.addLayout(bh)
        bl.addStretch(1)

        self._log_group = QGroupBox("Activity")
        log_outer = QVBoxLayout(self._log_group)
        show_row = QHBoxLayout()
        show_row.setContentsMargins(0, 0, 0, 3)
        show_row.setSpacing(0)
        self._show_log = QCheckBox("Show log")
        self._show_log.setObjectName("showLogToggle")
        self._show_log.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._show_log.setChecked(self._get_setting_bool("showLog", False))
        self._show_log.toggled.connect(self._toggle_log)
        show_row.addWidget(
            self._show_log,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        show_row.addStretch()
        log_outer.addLayout(show_row)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        # self._log.setPlaceholderText("Log appears here.")
        log_outer.addWidget(self._log)
        self._log.setVisible(self._show_log.isChecked())
        root.addWidget(self._log_group)

        self._status = QLabel("Ready.")
        self._status.setStyleSheet("color: #9aa0a6; font-size: 11px;")
        root.addWidget(self._status)

    def _make_plugin_tab(self, subtitle: str) -> tuple[QWidget, QWidget, QVBoxLayout]:
        wrap = QWidget()
        outer = QVBoxLayout(wrap)
        outer.setContentsMargins(4, 8, 4, 4)
        lab = QLabel(subtitle)
        lab.setWordWrap(True)
        outer.addWidget(lab)

        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll, stretch=1)
        return wrap, content, lay

    def _engines_path(self) -> Path:
        return Path(self._path_edit.text().strip())

    def _offer_remove_engine(self, row: PluginRow, global_pos: QPoint) -> None:
        menu = QMenu(self)
        act = menu.addAction("Remove Plugin")
        if menu.exec(global_pos) == act:
            self._confirm_remove_engine(row)

    def _confirm_remove_engine(self, row: PluginRow) -> None:
        engines = self._engines_path()
        if not engines.exists():
            QMessageBox.warning(self, "Remove", "Engines folder does not exist.")
            return
        p = expected_dest_path(row, engines)
        if p is None:
            QMessageBox.warning(
                self, "Remove", "This plugin has no install path (no download URL)."
            )
            return
        if not p.is_file():
            QMessageBox.warning(self, "Remove", f"Not found on disk:\n{p}")
            return
        title_safe = row.title.replace("&", "&&")
        ans = QMessageBox.question(
            self,
            "Remove plugin?",
            f"Are you sure you want to delete {title_safe}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        try:
            removed = remove_installed_plugin(row, engines)
            self._append_log(f"Removed {removed.name}.\n")
        except OSError as e:
            QMessageBox.critical(self, "Remove failed", str(e))
            return
        self._populate_lists()

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "Engines folder", self._path_edit.text()
        )
        if d:
            self._path_edit.setText(d)

    def _append_log(self, msg: str) -> None:
        self._log.appendPlainText(msg.rstrip("\n"))

    def _toggle_log(self, visible: bool) -> None:
        self._log.setVisible(visible)
        self._settings.setValue("showLog", visible)

    def _load_list_async(self) -> None:
        self._list_loading = True
        self._status.setText("Loading list…")
        self._reload_btn.setEnabled(False)
        self._list_progress_label.setText("Fetching plugin list…")
        self._list_progress.setRange(0, 1)
        self._list_progress.setValue(0)
        self._list_overlay.show()
        self._list_overlay.raise_()
        self._sync_list_overlay_geometry()

        def work() -> None:
            try:
                text = fetch_text(WIKI_URL)
                pub, priv = parse_wiki(text)
                self._bridge.fetch_done.emit(pub, priv)
            except Exception as e:
                self._bridge.fetch_failed.emit(str(e))

        threading.Thread(target=work, daemon=True).start()

    def _on_fetch_done(self, pub: list[PluginRow], priv: list[PluginRow]) -> None:
        self._rows_public = pub
        self._rows_private = priv
        self._populate_lists()
        self._status.setText(f"Loaded {len(pub)} public, {len(priv)} private plugins.")

    def _on_fetch_failed(self, msg: str) -> None:
        self._hide_list_load_overlay()
        QMessageBox.critical(self, "Wiki", msg)
        self._status.setText("Failed to load list.")

    def _populate_lists(self) -> None:
        # Increment generation so stale async icon responses can be ignored.
        self._list_generation += 1
        engines = self._engines_path()
        if self._list_loading:
            self._list_load_icon_threads = 0
        self._fill_tab(
            self._lay_public,
            self._rows_public,
            self._checks_public,
            self._labels_public,
            self._installed_public,
            engines,
            tab_index=0,
        )
        self._fill_tab(
            self._lay_private,
            self._rows_private,
            self._checks_private,
            self._labels_private,
            self._installed_private,
            engines,
            tab_index=1,
        )
        if self._list_loading:
            self._list_load_total_steps = max(1, 1 + self._list_load_icon_threads)
            self._list_load_done_steps = 1
            self._list_progress_label.setText("Loading plugin list…")
            self._apply_list_load_progress()

    def _apply_list_load_progress(self) -> None:
        if not self._list_loading:
            return
        t = self._list_load_total_steps
        self._list_progress.setMaximum(t)
        self._list_progress.setValue(min(self._list_load_done_steps, t))
        if self._list_load_done_steps >= t:
            self._hide_list_load_overlay()

    def _hide_list_load_overlay(self) -> None:
        self._list_loading = False
        self._list_overlay.hide()
        self._reload_btn.setEnabled(True)

    def _clear_layout(self, lay: QVBoxLayout) -> None:
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _fill_tab(
        self,
        lay: QVBoxLayout,
        rows: list[PluginRow],
        checks_out: list[QCheckBox],
        labels_out: list[QLabel],
        installed_out: list[bool],
        engines_dir: Path,
        tab_index: int,
    ) -> None:
        self._clear_layout(lay)
        checks_out.clear()
        labels_out.clear()
        installed_out.clear()
        for r in rows:
            installed = (
                is_plugin_installed(r, engines_dir) if engines_dir.exists() else False
            )
            installed_out.append(installed)
            author = plain_author_display(r.author_cell)
            chosen_url = pick_download_url(r.download_urls) if r.download_urls else None
            status = (
                self._url_health_cache.get(chosen_url, "unknown")
                if chosen_url
                else "unreachable"
            )
            unavailable = (not installed) and (status in {"unreachable", "timeout"})

            row_w = _PluginRow(self, r, installed)
            row_lay = QHBoxLayout(row_w)
            row_lay.setContentsMargins(0, 2, 0, 0)
            row_lay.setSpacing(2)

            cb = QCheckBox()
            cb.setObjectName("engineRow")
            cb.setAccessibleName(f"{r.title} by {author} — v{r.version}")
            cb.setChecked(installed)
            cb.setEnabled((not installed) and (not unavailable))
            if installed:
                row_status = "installed"
            elif unavailable:
                row_status = "unavailable"
            else:
                row_status = "available"
            cb.setProperty("rowStatus", row_status)
            cb.style().polish(cb)

            color = "#22c55e" if installed else "#ef4444" if unavailable else "#e8eaed"
            lab = QLabel(
                f'<span style="color:{color}"><b>{html.escape(r.title)}</b>'
                f" by {html.escape(author)}  —  v{html.escape(r.version)}</span>"
            )
            lab.setTextFormat(Qt.TextFormat.RichText)
            lab.setWordWrap(False)
            lab.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
            )
            lab.installEventFilter(_LabelToggleEventFilter(cb))

            tip = r.comments.strip()
            if tip:
                row_w.setToolTip(tip)

            cb.setIconSize(_ENGINE_ICON_PX)
            if not r.icon_url:
                cb.setIcon(_default_engine_icon())
            elif r.icon_url not in self._icon_cache:
                cb.setIcon(_default_engine_icon())
                self._queue_icon_load(
                    self._list_generation, tab_index, len(checks_out), r.icon_url
                )
            else:
                cached = self._icon_cache[r.icon_url]
                cb.setIcon(cached if cached is not None else _default_engine_icon())
            if (not installed) and chosen_url and status == "unknown":
                self._queue_url_health_check(
                    self._list_generation, tab_index, len(checks_out), chosen_url
                )

            va = Qt.AlignmentFlag.AlignVCenter
            row_lay.addWidget(cb, 0, va)
            row_lay.addWidget(lab, 1, va)
            lay.addWidget(row_w)
            checks_out.append(cb)
            labels_out.append(lab)
        lay.addStretch()

    def _queue_icon_load(
        self, generation: int, tab_index: int, row_index: int, icon_url: str
    ) -> None:
        # Fetch icon in background so list rendering remains responsive.
        if not icon_url:
            return
        if icon_url in self._icon_cache:
            return
        if self._list_loading:
            self._list_load_icon_threads += 1

        def work() -> None:
            try:
                data = fetch_bytes(icon_url, timeout=20.0)
            except Exception:
                data = None
            self._bridge.icon_ready.emit(generation, tab_index, row_index, data)

        threading.Thread(target=work, daemon=True).start()

    def _queue_url_health_check(
        self, generation: int, tab_index: int, row_index: int, url: str
    ) -> None:
        if not url:
            return
        if url in self._url_health_cache or url in self._url_health_inflight:
            return
        self._url_health_inflight.add(url)

        def work() -> None:
            status = probe_url_status(url, timeout=12.0)
            self._bridge.url_health_ready.emit(generation, tab_index, row_index, status)

        threading.Thread(target=work, daemon=True).start()

    def _on_icon_ready(
        self, generation: int, tab_index: int, row_index: int, data: object
    ) -> None:
        # Ignore stale icon responses from older list generations/reloads.
        if generation != self._list_generation:
            return
        rows = self._rows_public if tab_index == 0 else self._rows_private
        checks = self._checks_public if tab_index == 0 else self._checks_private
        if row_index >= len(rows) or row_index >= len(checks):
            return

        icon_url = rows[row_index].icon_url
        if not icon_url:
            return

        icon: QIcon | None = None
        if isinstance(data, (bytes, bytearray)):
            pix = QPixmap()
            if pix.loadFromData(bytes(data)):
                icon = QIcon(pix)
        self._icon_cache[icon_url] = icon
        checks[row_index].setIcon(icon if icon is not None else _default_engine_icon())
        checks[row_index].setIconSize(_ENGINE_ICON_PX)
        if self._list_loading:
            self._list_load_done_steps += 1
            self._apply_list_load_progress()

    def _on_url_health_ready(
        self, generation: int, tab_index: int, row_index: int, status: str
    ) -> None:
        rows = self._rows_public if tab_index == 0 else self._rows_private
        checks = self._checks_public if tab_index == 0 else self._checks_private
        labels = self._labels_public if tab_index == 0 else self._labels_private
        installed = (
            self._installed_public if tab_index == 0 else self._installed_private
        )
        if (
            row_index >= len(rows)
            or row_index >= len(checks)
            or row_index >= len(labels)
        ):
            return
        row = rows[row_index]
        chosen_url = pick_download_url(row.download_urls) if row.download_urls else None
        if not chosen_url:
            return
        self._url_health_inflight.discard(chosen_url)
        self._url_health_cache[chosen_url] = status

        # Update visible row only for current generation to avoid stale repaint.
        if generation != self._list_generation:
            return
        if row_index < len(installed) and installed[row_index]:
            return
        unavailable = status in {"unreachable", "timeout"}
        checks[row_index].setEnabled(not unavailable)
        checks[row_index].setProperty(
            "rowStatus", "unavailable" if unavailable else "available"
        )
        checks[row_index].style().polish(checks[row_index])
        author = plain_author_display(row.author_cell)
        color = "#ef4444" if unavailable else "#e8eaed"
        labels[row_index].setText(
            f'<span style="color:{color}"><b>{html.escape(row.title)}</b>'
            f" by {html.escape(author)}  —  v{html.escape(row.version)}</span>"
        )

    def _selected_rows(self) -> list[PluginRow]:
        out: list[PluginRow] = []
        for rows, checks, inst in (
            (self._rows_public, self._checks_public, self._installed_public),
            (self._rows_private, self._checks_private, self._installed_private),
        ):
            for i, r in enumerate(rows):
                if i >= len(checks) or i >= len(inst):
                    continue
                if checks[i].isChecked() and not inst[i]:
                    out.append(r)
        return out

    def _install_async(self) -> None:
        selected = self._selected_rows()
        if not selected:
            QMessageBox.information(
                self,
                "Install",
                "Tick one or more plugins that are not already installed.",
            )
            return
        engines = self._engines_path()
        if not engines.exists():
            r = QMessageBox.question(
                self,
                "Create folder?",
                f"This folder does not exist yet:\n{engines}\n\nCreate it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if r != QMessageBox.StandardButton.Yes:
                return

        self._pending_private_reminder = any(r.category == "private" for r in selected)
        self._successful_private_installs = 0
        self._failed_installs = 0
        self._status.setText("Installing…")
        self._install_btn.setEnabled(False)
        self._reload_btn.setEnabled(False)

        def work() -> None:
            n = len(selected)
            failed_count = 0
            successful_private_installs = 0
            self._bridge.log_line.emit(f"Installing {n} plugin(s)…\n")
            for row in selected:
                if not row.download_urls:
                    self._bridge.log_line.emit(
                        f"Skipped: {row.title} (no download URL)\n"
                    )
                    failed_count += 1
                    continue
                try:
                    install_plugin(
                        row, engines, lambda m, b=self._bridge: b.log_line.emit(m)
                    )
                    if row.category == "private":
                        successful_private_installs += 1
                except Exception as e:
                    self._bridge.log_line.emit(f"Failed: {row.title} — {e}\n")
                    failed_count += 1
            self._successful_private_installs = successful_private_installs
            self._failed_installs = failed_count
            self._bridge.log_line.emit("Finished.\n")
            self._bridge.install_finished.emit()

        threading.Thread(target=work, daemon=True).start()

    def _on_install_finished(self) -> None:
        self._status.setText("Done.")
        self._install_btn.setEnabled(True)
        self._reload_btn.setEnabled(True)
        self._populate_lists()
        if self._pending_private_reminder and (self._successful_private_installs > 0):
            self._show_private_plugins_reminder(self._engines_path())
        if self._failed_installs > 0:
            self._show_install_failures(self._failed_installs)
        self._pending_private_reminder = False
        self._successful_private_installs = 0
        self._failed_installs = 0

    def _show_private_plugins_reminder(self, engines: Path) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Warning")
        dlg.setModal(True)
        layout = QVBoxLayout(dlg)
        text = QLabel(
            "Private search engines usually need configuration before you can "
            "use them.\n\n"
            "Follow the author's instructions to edit downloaded `.py` files "
            "in your engines folder."
        )
        text.setWordWrap(True)
        text.setMinimumWidth(420)
        layout.addWidget(text)
        row = QHBoxLayout()
        row.addStretch()
        open_btn = QPushButton("Open engines folder")
        open_btn.clicked.connect(lambda: open_folder_in_file_manager(engines))
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(dlg.accept)
        row.addWidget(open_btn)
        row.addWidget(ok_btn)
        layout.addLayout(row)
        dlg.exec()

    def _show_install_failures(self, failed_count: int) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Some plugins failed")
        dlg.setModal(True)
        layout = QVBoxLayout(dlg)
        text = QLabel(
            f"{failed_count} plugin(s) failed to install.\n\n"
            "Check Activity log for details (404, timeout, or source URL changes)."
        )
        text.setWordWrap(True)
        text.setMinimumWidth(420)
        layout.addWidget(text)
        row = QHBoxLayout()
        row.addStretch()
        open_log_btn = QPushButton("Open log")
        open_log_btn.clicked.connect(lambda: self._show_log.setChecked(True))
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(dlg.accept)
        row.addWidget(open_log_btn)
        row.addWidget(ok_btn)
        layout.addLayout(row)
        dlg.exec()
