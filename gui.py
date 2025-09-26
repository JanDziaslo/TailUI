from __future__ import annotations

import sys
import time
from typing import Optional, Dict, Set, Callable, List
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QObject, QDateTime, QEvent, QRunnable, QThreadPool
from PySide6.QtGui import QIcon, QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout,
    QComboBox, QGroupBox, QFormLayout, QStatusBar, QMessageBox, QCheckBox,
    QTreeWidget, QTreeWidgetItem, QStyle, QSplitter, QSizePolicy, QSystemTrayIcon, QMenu,
    QToolButton, QHeaderView
)

from tailscale_client import TailscaleClient, TailscaleError, tailscale_available, Device, Status
from ip_info import PublicIPFetcher


ICON_FILENAMES = ("assets_icon_tailscale.svg", "assets_icon_tailscale.png")


def _resolve_app_icon_path() -> Optional[Path]:
    base_dir = Path(__file__).parent
    for name in ICON_FILENAMES:
        candidate = base_dir / name
        if candidate.exists():
            return candidate
    return None


def _load_app_icon() -> Optional[QIcon]:
    icon_path = _resolve_app_icon_path()
    if not icon_path:
        return None
    icon = QIcon(str(icon_path))
    return icon if not icon.isNull() else None


class WorkerSignals(QObject):
    error = Signal(str)
    finished = Signal(object)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)


class Worker(QRunnable):
    def __init__(self, fn, *, parent: Optional[QObject] = None):
        super().__init__()
        self.fn = fn
        self.signals = WorkerSignals(parent)

    def run(self):
        try:
            result = self.fn()
        except TailscaleError as e:
            self.signals.error.emit(str(e))
        except Exception as e:
            self.signals.error.emit(f"Nieoczekiwany błąd: {e}")
        else:
            self.signals.finished.emit(result)


class MainWindow(QMainWindow):
    REFRESH_MS = 5000
    INTERACTION_DEBOUNCE_MS = 350  # krótka zwłoka po interakcji
    DEVICE_IPV4_ROLE = Qt.UserRole + 1
    DEVICE_IPV6_ROLE = Qt.UserRole + 2

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tailscale GUI")
        self.resize(1000, 700)

        self.client: Optional[TailscaleClient] = None
        self.ip_fetcher = PublicIPFetcher(ttl=180)
        self._last_refresh_ts: Optional[float] = None
        self._busy_toggle = False  # blokada wielokrotnego przełączania
        self._exit_entries: Dict[str, str] = {}
        self._exit_alias_map: Dict[str, str] = {}
        self._exit_active_value: Optional[str] = None
        self._exit_has_nodes = False
        self._exit_busy = False
        self._tray_icon: Optional[QSystemTrayIcon] = None
        self._tray_connect_action = None
        self._tray_disconnect_action = None
        self._tray_show_action = None
        self._tray_message_shown = False
        self._tray_force_exit = False
        self.self_ips_copy_all_btn: Optional[QPushButton] = None
        self.self_ipv4_copy_btn: Optional[QPushButton] = None
        self.self_ipv6_copy_btn: Optional[QPushButton] = None
        self.public_ip_copy_btn: Optional[QPushButton] = None
        self._self_ipv4_list: List[str] = []
        self._self_ipv6_list: List[str] = []
        self._public_ip_pending = False

        # Timer interakcji (debounce)
        self._interaction_timer = QTimer(self)
        self._interaction_timer.setSingleShot(True)
        self._interaction_timer.timeout.connect(self._interaction_refresh)

        # Polling timer
        self._poll_timer: Optional[QTimer] = None
        self._poll_target: Optional[bool] = None
        self._poll_started_at: float = 0.0
        self._poll_timeout_sec = 15.0
        self._disconnect_timeout_sec = 6.0  # krótszy timeout dla rozłączania
        self._disconnect_grace_sec = 1.5    # po tym czasie uznaj rozłączenie jeśli brak błędów
        self._down_started_at: float = 0.0

        self._thread_pool = QThreadPool(self)
        self._active_workers = []

        self._init_client()
        self._build_ui()
        self._apply_styles()
        self._init_tray()

        # Instalacja filtra zdarzeń, aby reagować na aktywność użytkownika
        self.installEventFilter(self)

        # Timer okresowy
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(self.REFRESH_MS)
        self.refresh_status()
        self.fetch_public_ip(force=True)

    def _submit_worker(self, fn, on_success, on_error):
        worker = Worker(fn, parent=self)
        self._active_workers.append(worker)

        def _cleanup():
            if worker in self._active_workers:
                self._active_workers.remove(worker)

        def _handle_success(result):
            try:
                on_success(result)
            finally:
                _cleanup()

        def _handle_error(msg: str):
            try:
                on_error(msg)
            finally:
                _cleanup()

        worker.signals.finished.connect(_handle_success)
        worker.signals.error.connect(_handle_error)
        self._thread_pool.start(worker)

    # --- Inicjalizacja klienta ---
    def _init_client(self):
        if tailscale_available():
            try:
                self.client = TailscaleClient()
            except Exception as e:
                self.client = None
                print(f"Błąd inicjalizacji TailscaleClient: {e}")
        else:
            self.client = None

    # --- Budowa UI ---
    def _build_ui(self):
        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)
        self.setCentralWidget(central)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        app_icon = _load_app_icon()
        if app_icon:
            self.setWindowIcon(app_icon)
            pm = app_icon.pixmap(32, 32)
            if pm.isNull():
                icon_path = _resolve_app_icon_path()
                if icon_path:
                    pm = QPixmap(str(icon_path))
            if not pm.isNull():
                self.icon_label = QLabel()
                self.icon_label.setPixmap(pm.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.icon_label.setFixedSize(32, 32)
                top_bar.addWidget(self.icon_label)

        self.title_label = QLabel("Tailscale")
        self.title_label.setObjectName("AppTitle")
        top_bar.addWidget(self.title_label)
        top_bar.addStretch(1)

        self.last_refresh_label = QLabel("—")
        self.last_refresh_label.setObjectName("LastRefresh")
        top_bar.addWidget(self.last_refresh_label)

        self.refresh_btn = QPushButton("Odśwież")
        self.refresh_btn.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.refresh_btn.clicked.connect(self._manual_refresh)
        self.refresh_btn.setObjectName("RefreshButton")
        top_bar.addWidget(self.refresh_btn)

        self.toggle_button = QPushButton("Połącz")
        self.toggle_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.toggle_button.clicked.connect(self._handle_toggle_connection)
        self.toggle_button.setObjectName("ToggleButton")
        top_bar.addWidget(self.toggle_button)

        exit_group = QGroupBox("Exit node")
        exit_layout = QVBoxLayout(exit_group)
        exit_layout.setContentsMargins(8, 8, 8, 8)
        exit_layout.setSpacing(6)

        exit_controls = QHBoxLayout()
        exit_controls.setSpacing(6)

        self.exit_enable_checkbox = QCheckBox("Włącz exit node")
        self.exit_enable_checkbox.toggled.connect(self._on_exit_toggle_checkbox)

        self.exit_apply_btn = QPushButton("Zastosuj")
        self.exit_apply_btn.clicked.connect(self._on_exit_apply)

        exit_controls.addWidget(self.exit_enable_checkbox)
        exit_controls.addStretch(1)
        exit_controls.addWidget(self.exit_apply_btn)

        self.exit_node_combo = QComboBox()
        self.exit_node_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.exit_node_combo.currentIndexChanged.connect(self._on_exit_selection_changed)

        exit_layout.addLayout(exit_controls)
        exit_layout.addWidget(self.exit_node_combo)
        self.exit_node_combo.setEnabled(False)
        self.exit_apply_btn.setEnabled(False)

        devices_group = QGroupBox("Urządzenia w sieci")
        devices_layout = QVBoxLayout(devices_group)
        self.devices_tree = QTreeWidget()
        self.devices_tree.setColumnCount(5)
        self.devices_tree.setHeaderLabels(["Nazwa", "Adresy", "Status", "Exit", "System"])
        self.devices_tree.setRootIsDecorated(False)
        self.devices_tree.setAlternatingRowColors(True)
        self.devices_tree.setSortingEnabled(True)
        self.devices_tree.sortByColumn(0, Qt.AscendingOrder)
        self.devices_tree.setUniformRowHeights(False)
        self.devices_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.devices_tree.customContextMenuRequested.connect(self._on_device_context_menu)
        self.devices_tree.itemDoubleClicked.connect(self._on_device_item_double_clicked)
        devices_layout.addWidget(self.devices_tree)
        header = self.devices_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setMinimumSectionSize(120)
        header.resizeSection(1, 420)

        info_group = QGroupBox("Informacje o urządzeniu")
        info_form = QFormLayout(info_group)
        info_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.status_label = QLabel("-")
        self.status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.self_ips_label = QLabel("-")
        self.self_ips_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.self_ips_copy_all_btn = QPushButton("Kopiuj")
        self.self_ips_copy_all_btn.setObjectName("CopyButton")
        self.self_ips_copy_all_btn.setEnabled(False)
        self.self_ips_copy_all_btn.clicked.connect(
            lambda: self._copy_label_text(self.self_ips_label, "Adresy Tailnet")
        )

        self.self_ipv4_copy_btn = QPushButton("IPv4")
        self.self_ipv4_copy_btn.setObjectName("CopyButton")
        self.self_ipv4_copy_btn.setEnabled(False)
        self.self_ipv4_copy_btn.clicked.connect(
            lambda: self._copy_ips_list(self._self_ipv4_list, "Adresy IPv4 Tailnet")
        )

        self.self_ipv6_copy_btn = QPushButton("IPv6")
        self.self_ipv6_copy_btn.setObjectName("CopyButton")
        self.self_ipv6_copy_btn.setEnabled(False)
        self.self_ipv6_copy_btn.clicked.connect(
            lambda: self._copy_ips_list(self._self_ipv6_list, "Adresy IPv6 Tailnet")
        )

        self.public_ip_label = QLabel("-")
        self.public_ip_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.public_ip_copy_btn = QPushButton("Kopiuj")
        self.public_ip_copy_btn.setObjectName("CopyButton")
        self.public_ip_copy_btn.setEnabled(False)
        self.public_ip_copy_btn.clicked.connect(lambda: self._copy_label_text(self.public_ip_label, "Publiczne IP"))

        self.public_ip_details_label = QLabel("-")
        self.public_ip_details_label.setWordWrap(True)
        self.public_ip_details_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        info_form.addRow("Stan:", self.status_label)
        self_ips_container = QWidget()
        self_ips_layout = QHBoxLayout(self_ips_container)
        self_ips_layout.setContentsMargins(0, 0, 0, 0)
        self_ips_layout.setSpacing(6)
        self.self_ips_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self_ips_layout.addWidget(self.self_ips_label, 1)
        self_ips_layout.addWidget(self.self_ips_copy_all_btn)
        self_ips_layout.addWidget(self.self_ipv4_copy_btn)
        self_ips_layout.addWidget(self.self_ipv6_copy_btn)

        info_form.addRow("Adresy Tailnet:", self_ips_container)
        info_form.addRow("Publiczne IP:", self._wrap_with_copy(self.public_ip_label, self.public_ip_copy_btn))
        info_form.addRow("Szczegóły IP:", self.public_ip_details_label)

        main_splitter = QSplitter(Qt.Vertical)
        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)
        top_layout.addWidget(exit_group)
        top_layout.addWidget(devices_group)
        main_splitter.addWidget(top_container)
        main_splitter.addWidget(info_group)
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 1)

        root_layout.addLayout(top_bar)
        root_layout.addWidget(main_splitter, 1)

        self.setStatusBar(QStatusBar())

        if not self.client:
            self.toggle_button.setEnabled(False)
            self.exit_node_combo.setEnabled(False)
            self.exit_enable_checkbox.setEnabled(False)
            self.exit_apply_btn.setEnabled(False)
            self.statusBar().showMessage("Tailscale nie jest dostępny w systemie (brak binarki w PATH).")

        self._sync_copy_buttons()

    def _apply_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #282a36;
            }
            QLabel {
                color: #f8f8f2;
            }
            QLabel#AppTitle {
                font-size: 20px;
                font-weight: bold;
                color: #bd93f9;
            }
            QLabel#LastRefresh {
                color: #6272a4;
                font-size: 11px;
            }
            QGroupBox {
                background-color: #2c2e3a;
                border: 1px solid #44475a;
                border-radius: 8px;
                margin-top: 1ex;
                font-weight: bold;
                color: #bd93f9;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                background-color: #343746;
                border-radius: 4px;
                color: #f8f8f2;
                left: 10px;
            }
            QPushButton {
                background-color: #44475a;
                color: #f8f8f2;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a5c70;
            }
            QPushButton:pressed {
                background-color: #3a3c4a;
            }
            QPushButton:disabled {
                background-color: #3a3c4a;
                color: #6272a4;
            }

            QToolButton#AddressCopyButton {
                background-color: #44475a;
                color: #f8f8f2;
                border: none;
                padding: 4px 10px;
                border-radius: 4px;
                font-weight: bold;
            }
            QToolButton#AddressCopyButton:hover {
                background-color: #5a5c70;
            }
            QToolButton#AddressCopyButton:pressed {
                background-color: #3a3c4a;
            }
            QToolButton#AddressCopyButton:disabled {
                background-color: #3a3c4a;
                color: #6272a4;
            }

            QPushButton#ToggleButton[connected="true"] {
                background-color: #ff5555;
                color: #282a36;
            }
            QPushButton#ToggleButton[connected="true"]:hover {
                background-color: #ff7070;
            }
            QPushButton#ToggleButton[connected="false"] {
                background-color: #50fa7b;
                color: #282a36;
            }
            QPushButton#ToggleButton[connected="false"]:hover {
                background-color: #69ff8c;
            }
            QTreeWidget {
                background-color: #2c2e3a;
                border: 1px solid #44475a;
                border-radius: 6px;
                color: #f8f8f2;
            }
            QTreeWidget::item {
                padding: 4px 2px;
            }
            QTreeWidget::item:selected {
                background-color: #44475a;
            }
            QHeaderView::section {
                background-color: #343746;
                color: #bd93f9;
                padding: 6px;
                border: 1px solid #44475a;
                font-weight: bold;
            }
            QComboBox {
                background-color: #2c2e3a;
                border: 1px solid #44475a;
                border-radius: 4px;
                padding: 4px;
                color: #f8f8f2;
            }
            QComboBox:disabled {
                color: #6272a4;
            }
            QComboBox::drop-down {
                border: none;
            }
            QCheckBox {
                color: #f8f8f2;
            }
            QStatusBar {
                background-color: #21222c;
                color: #6272a4;
            }
            QSplitter::handle {
                background-color: #44475a;
            }
        """)

    # --- Zasobnik systemowy ---
    def _init_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        icon = self.windowIcon()
        if icon.isNull():
            icon = self.style().standardIcon(QStyle.SP_ComputerIcon)

        self._tray_icon = QSystemTrayIcon(icon, self)
        self._tray_icon.setToolTip("Tailscale GUI")

        menu = QMenu(self)
        self._tray_show_action = menu.addAction("Ukryj okno")
        self._tray_show_action.triggered.connect(self._toggle_tray_visibility)

        self._tray_connect_action = menu.addAction("Połącz")
        self._tray_connect_action.triggered.connect(self._on_tray_connect)

        self._tray_disconnect_action = menu.addAction("Rozłącz")
        self._tray_disconnect_action.triggered.connect(self._on_tray_disconnect)

        menu.addSeparator()
        quit_action = menu.addAction("Zakończ")
        quit_action.triggered.connect(self._quit_from_tray)

        self._tray_icon.setContextMenu(menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self._cleanup_tray)

        self._update_tray_menu_status()

    def _quit_from_tray(self):
        self._tray_force_exit = True
        QApplication.quit()

    def _cleanup_tray(self):
        if self._tray_icon:
            self._tray_icon.hide()

    def _toggle_tray_visibility(self):
        if self.isHidden():
            self._show_window_from_tray()
        else:
            self._hide_window_to_tray()

    def _on_tray_connect(self):
        if not self.client or self._busy_toggle:
            return
        try:
            status = self.client.status()
            if status.connected:
                self.statusBar().showMessage("Tailscale jest już połączony", 3000)
                return
        except TailscaleError:
            pass
        self.start_connection()

    def _on_tray_disconnect(self):
        if not self.client or self._busy_toggle:
            return
        try:
            status = self.client.status()
            if not status.connected:
                self.statusBar().showMessage("Tailscale jest już rozłączony", 3000)
                return
        except TailscaleError:
            pass
        self.stop_connection()

    def _show_window_from_tray(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self._update_tray_menu_status()

    def _hide_window_to_tray(self):
        self.hide()
        self._update_tray_menu_status()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._toggle_tray_visibility()

    def _update_tray_menu_status(self, status: Optional[Status] = None):
        if not self._tray_icon:
            return

        connected = False
        if status is not None:
            connected = status.connected
        else:
            connected = bool(self.toggle_button.property("connected"))

        can_interact = bool(self.client) and not self._busy_toggle

        if self._tray_connect_action:
            self._tray_connect_action.setEnabled(can_interact and not connected)

        if self._tray_disconnect_action:
            self._tray_disconnect_action.setEnabled(can_interact and connected)

        if self._tray_show_action:
            self._tray_show_action.setText("Ukryj okno" if not self.isHidden() else "Pokaż okno")

        tooltip_state = "połączony" if connected else "rozłączony"
        self._tray_icon.setToolTip(f"Tailscale GUI — {tooltip_state}")

    def closeEvent(self, event):
        if self._tray_icon and self._tray_icon.isVisible() and not self._tray_force_exit:
            event.ignore()
            self._hide_window_to_tray()
            if not self._tray_message_shown:
                self._tray_icon.showMessage(
                    "Tailscale GUI",
                    "Aplikacja działa w tle w zasobniku.",
                    QSystemTrayIcon.Information,
                    4000,
                )
                self._tray_message_shown = True
            return

        if self._tray_force_exit:
            self._cleanup_tray()
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self._update_tray_menu_status()

    # --- Pomocnicze busy ---
    def _set_busy(self, busy: bool):
        self._busy_toggle = busy
        self.toggle_button.setEnabled(not busy)
        self._update_tray_menu_status()

    def _start_poll(self, target_connected: bool, down_started: bool = False):
        if self._poll_timer:
            self._poll_timer.stop()
            self._poll_timer.deleteLater()
        self._poll_target = target_connected
        self._poll_started_at = time.time()
        if down_started:
            self._down_started_at = self._poll_started_at
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_iteration)
        self._poll_timer.start(300)

    def _poll_iteration(self):
        if not self.client:
            self._finish_transition(error_msg="Brak klienta")
            return

        elapsed = time.time() - self._poll_started_at
        timeout_limit = self._disconnect_timeout_sec if self._poll_target is False else self._poll_timeout_sec

        if elapsed > timeout_limit:
            self._finish_transition(error_msg="Przekroczono czas oczekiwania na zmianę stanu")
            return

        try:
            st = self.client.status()
            if st.connected == self._poll_target:
                self._finish_transition(status_msg="Połączono" if st.connected else "Rozłączono")
                return

            if self._poll_target is False and (time.time() - self._down_started_at) >= self._disconnect_grace_sec:
                if st.backend_state.lower() != 'running':
                    self._finish_transition(status_msg="Rozłączono (backend zatrzymany)")
                    return
        except TailscaleError:
            if self._poll_target is False:
                self._finish_transition(status_msg="Rozłączono (status niedostępny)")
                return

    def _finish_transition(self, error_msg: Optional[str] = None, status_msg: Optional[str] = None):
        if self._poll_timer:
            self._poll_timer.stop()
            self._poll_timer.deleteLater()
            self._poll_timer = None
        self._poll_target = None
        self._set_busy(False)
        self.refresh_status(force=True)
        self.fetch_public_ip(force=True)

        if error_msg:
            self._error(error_msg)
        elif status_msg:
            self.statusBar().showMessage(status_msg, 4000)

    def _handle_toggle_connection(self):
        if not self.client or self._busy_toggle:
            return

        try:
            status = self.client.status()
            if status.connected:
                self.stop_connection()
            else:
                self.start_connection()
        except TailscaleError as e:
            self._error(f"Nie można pobrać statusu: {e}")

    def start_connection(self):
        self._set_busy(True)
        self.toggle_button.setText("Łączenie…")
        self.statusBar().showMessage("Łączenie…")
        desired_exit_node = None
        if self.exit_enable_checkbox.isChecked():
            desired_exit_node = self.exit_node_combo.currentData()
            if desired_exit_node is None and self.exit_node_combo.count() > 0:
                self.exit_node_combo.blockSignals(True)
                self.exit_node_combo.setCurrentIndex(0)
                self.exit_node_combo.blockSignals(False)
                desired_exit_node = self.exit_node_combo.currentData()
            if desired_exit_node:
                desired_exit_node = str(desired_exit_node)
                self._exit_busy = True
                self._sync_exit_controls_enabled()

        def run_up_and_maybe_exit():
            self.client.up([])
            if desired_exit_node:
                self.client.set_exit_node(desired_exit_node)

        self._submit_worker(
            run_up_and_maybe_exit,
            lambda _: self._handle_connection_success(bool(desired_exit_node)),
            lambda msg: self._handle_connection_error(msg, bool(desired_exit_node))
        )

    def _handle_connection_success(self, exit_node_requested: bool):
        if exit_node_requested:
            self._exit_busy = False
            self.statusBar().showMessage("Połączono i ustawiono exit node", 4000)
        self._sync_exit_controls_enabled()
        self._start_poll(True)

    def _handle_connection_error(self, msg: str, exit_node_requested: bool):
        if exit_node_requested:
            self._exit_busy = False
            self._sync_exit_controls_enabled()
        self._finish_transition(error_msg=msg)

    def stop_connection(self):
        self._set_busy(True)
        self.toggle_button.setText("Rozłączanie…")
        self.statusBar().showMessage("Rozłączanie…")
        self._submit_worker(
            self.client.down,
            lambda _: self._start_poll(False, down_started=True),
            lambda msg: self._finish_transition(error_msg=msg)
        )

    def _manual_refresh(self):
        self.refresh_status(force=True)
        self.fetch_public_ip(force=True)

    def _refresh_exit_nodes(self, status):
        previous_value = self.exit_node_combo.currentData()
        if previous_value is not None:
            previous_value = str(previous_value)

        self.exit_node_combo.blockSignals(True)
        self.exit_node_combo.clear()
        self._exit_entries.clear()
        self._exit_alias_map.clear()

        for device in status.exit_nodes:
            command_value = self._preferred_exit_node_argument(device)
            if not command_value:
                continue
            command_value = str(command_value)
            label = self._format_exit_label(device, command_value)
            self.exit_node_combo.addItem(label, command_value)
            self._exit_entries[command_value] = label
            for alias in self._exit_aliases_for_device(device):
                self._exit_alias_map[alias] = command_value

        self._exit_has_nodes = self.exit_node_combo.count() > 0

        active_value = None
        if status.active_exit_node:
            for alias in self._exit_aliases_for_device(status.active_exit_node):
                mapped = self._exit_alias_map.get(alias)
                if mapped:
                    active_value = mapped
                    break
            if not active_value:
                preferred = self._preferred_exit_node_argument(status.active_exit_node)
                if preferred and preferred in self._exit_entries:
                    active_value = preferred

        target_value = active_value or previous_value
        if target_value and target_value in self._exit_entries:
            idx = self.exit_node_combo.findData(target_value)
            if idx >= 0:
                self.exit_node_combo.setCurrentIndex(idx)
        elif self._exit_has_nodes and self.exit_node_combo.currentIndex() == -1:
            self.exit_node_combo.setCurrentIndex(0)

        self.exit_node_combo.blockSignals(False)

        self._exit_active_value = active_value
        self.exit_enable_checkbox.blockSignals(True)
        self.exit_enable_checkbox.setChecked(active_value is not None)
        self.exit_enable_checkbox.blockSignals(False)

        self._sync_exit_controls_enabled()

    @staticmethod
    def _exit_aliases_for_device(device: Device) -> Set[str]:
        aliases: Set[str] = set()
        if not device:
            return aliases
        if device.name:
            aliases.add(str(device.name))
        if device.device_id:
            aliases.add(str(device.device_id))
        if device.tailnet_ips:
            aliases.update(str(ip) for ip in device.tailnet_ips if ip)
        hostinfo = device.hostinfo or {}
        for key in ("Hostname", "DNSName"):
            value = hostinfo.get(key)
            if value:
                aliases.add(str(value))
        return aliases

    @staticmethod
    def _format_exit_label(device: Device, command_value: str) -> str:
        name = str(device.name or command_value)
        ips = ", ".join(str(ip) for ip in (device.tailnet_ips or []) if ip)
        if ips and ips != name:
            return f"{name} – {ips}"
        return name

    @staticmethod
    def _preferred_exit_node_argument(device: Device) -> Optional[str]:
        hostinfo = device.hostinfo or {}
        for key in ("Hostname", "DNSName"):
            value = hostinfo.get(key)
            if value:
                return str(value)
        if device.name:
            return str(device.name)
        if device.tailnet_ips:
            for ip in device.tailnet_ips:
                if ip:
                    return str(ip)
        if device.device_id:
            return str(device.device_id)
        return None

    def _sync_exit_controls_enabled(self):
        if not hasattr(self, "exit_enable_checkbox"):
            return
        if not self.client:
            self.exit_enable_checkbox.setEnabled(False)
            self.exit_apply_btn.setEnabled(False)
            self.exit_node_combo.setEnabled(False)
            return
        if self._exit_busy:
            self.exit_enable_checkbox.setEnabled(False)
            self.exit_apply_btn.setEnabled(False)
            self.exit_node_combo.setEnabled(False)
            return

        checked = self.exit_enable_checkbox.isChecked()
        has_nodes = self._exit_has_nodes
        can_disable = self._exit_active_value is not None

        self.exit_enable_checkbox.setEnabled(has_nodes or can_disable or checked)

        self.exit_node_combo.setEnabled(checked and has_nodes)

        if checked:
            can_apply = has_nodes and self.exit_node_combo.currentData() is not None
        else:
            can_apply = can_disable
        self.exit_apply_btn.setEnabled(can_apply)

    @staticmethod
    def _wrap_with_copy(label: QLabel, button: QPushButton) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(label, 1)
        layout.addWidget(button)
        return container

    @staticmethod
    def _has_copyable_text(label: QLabel) -> bool:
        if not label:
            return False
        text = (label.text() or "").strip()
        return bool(text and text != "-")

    def _copy_label_text(self, label: QLabel, description: str):
        if not label:
            return
        text = (label.text() or "").strip()
        if not text or text == "-":
            self.statusBar().showMessage(f"Brak danych do skopiowania ({description})", 3000)
            return
        self._copy_to_clipboard(text, description)

    def _copy_ips_list(self, ips: List[str], description: str):
        cleaned = [ip.strip() for ip in ips if ip and ip.strip()]
        if not cleaned:
            self.statusBar().showMessage(f"Brak danych do skopiowania ({description})", 3000)
            return
        self._copy_to_clipboard("\n".join(cleaned), description)

    def _copy_to_clipboard(self, text: str, description: str):
        normalized = (text or "").strip()
        if not normalized:
            self.statusBar().showMessage(f"Brak danych do skopiowania ({description})", 3000)
            return
        QApplication.clipboard().setText(normalized)
        self.statusBar().showMessage(f"{description} skopiowane do schowka", 4000)

    def _sync_copy_buttons(self):
        if self.self_ips_copy_all_btn:
            self.self_ips_copy_all_btn.setEnabled(self._has_copyable_text(self.self_ips_label))
        if self.self_ipv4_copy_btn:
            self.self_ipv4_copy_btn.setEnabled(bool(self._self_ipv4_list))
        if self.self_ipv6_copy_btn:
            self.self_ipv6_copy_btn.setEnabled(bool(self._self_ipv6_list))
        if self.public_ip_copy_btn:
            self.public_ip_copy_btn.setEnabled(self._has_copyable_text(self.public_ip_label))

    def _on_exit_toggle_checkbox(self, checked: bool):
        if checked and self._exit_has_nodes and self.exit_node_combo.currentIndex() == -1:
            self.exit_node_combo.setCurrentIndex(0)
        self._sync_exit_controls_enabled()

    def _on_exit_selection_changed(self, index: int):
        self._sync_exit_controls_enabled()

    def _on_exit_apply(self):
        if not self.client or self._exit_busy:
            return

        want_enable = self.exit_enable_checkbox.isChecked()
        if want_enable:
            target = self.exit_node_combo.currentData()
            if not target:
                self._error("Wybierz exit node z listy.")
                return
            target = str(target)
            label = self.exit_node_combo.currentText()
            self._perform_exit_operation(
                lambda: self.client.set_exit_node(target),
                f"Exit node ustawiony: {label}"
            )
        else:
            if self._exit_active_value is None:
                self.statusBar().showMessage("Exit node jest już wyłączony", 3000)
                return
            self._perform_exit_operation(
                lambda: self.client.set_exit_node(None),
                "Exit node wyłączony"
            )

    def _perform_exit_operation(self, task: Callable[[], None], success_message: str):
        self._exit_busy = True
        self._sync_exit_controls_enabled()
        self.statusBar().showMessage("Aktualizowanie exit node…")
        self._submit_worker(
            task,
            lambda _: self._on_exit_operation_success(success_message),
            self._on_exit_operation_error
        )

    def _on_exit_operation_success(self, message: str):
        self._exit_busy = False
        self.statusBar().showMessage(message, 4000)
        self.refresh_status(force=True)
        self.fetch_public_ip(force=True)
        self._sync_exit_controls_enabled()

    def _on_exit_operation_error(self, msg: str):
        self._exit_busy = False
        if msg:
            self._error(msg)
        self.refresh_status(force=True)
        self.fetch_public_ip(force=True)
        self._sync_exit_controls_enabled()

    def _error(self, msg: str):
        self.statusBar().showMessage(msg, 10000)
        QMessageBox.warning(self, "Błąd", msg)

    # --- Odświeżanie ---
    def refresh_status(self, force: bool = False):
        if not self.client:
            self._exit_has_nodes = False
            self._exit_active_value = None
            self._update_self_ips(None)
            self._sync_exit_controls_enabled()
            self._update_tray_menu_status()
            return
        try:
            st = self.client.status()
        except TailscaleError as e:
            self.status_label.setText(f"błąd: {e}")
            self._exit_has_nodes = False
            self._exit_active_value = None
            self._sync_exit_controls_enabled()
            self._update_self_ips(None)
            return

        self._update_tray_menu_status(st)

        # Status tekstowy
        self.status_label.setText(f"{st.backend_state} | Połączony: {'tak' if st.connected else 'nie'}")

        # Aktualizacja stanów przycisków
        if not self._busy_toggle:
            style = self.style()
            self.toggle_button.setProperty("connected", st.connected)
            if st.connected:
                self.toggle_button.setText("Rozłącz")
                self.toggle_button.setIcon(style.standardIcon(QStyle.SP_MediaStop))
            else:
                self.toggle_button.setText("Połącz")
                self.toggle_button.setIcon(style.standardIcon(QStyle.SP_MediaPlay))

            self.toggle_button.style().unpolish(self.toggle_button)
            self.toggle_button.style().polish(self.toggle_button)
            self.toggle_button.setEnabled(True)

        # Aktualizacja listy urządzeń
        self._populate_devices(st)

        # Adresy własne
        self._update_self_ips(st.self_device)

        self._refresh_exit_nodes(st)

        # Znacznik czasu
        self._last_refresh_ts = time.time()
        self.last_refresh_label.setText(
            f"Odświeżono: {QDateTime.currentDateTime().toString('HH:mm:ss')}"
        )

    def _populate_devices(self, status):
        self.devices_tree.clear()
        for d in status.devices:
            flags = []
            if d.is_exit_node:
                flags.append("(aktywny exit)")
            if not d.online:
                flags.append("offline")
            status_text = "online" if d.online else "offline"
            exit_text = "tak" if d.is_exit_node else ("możliwy" if d.exit_node_option else "-")
            ipv4_list: List[str] = []
            ipv6_list: List[str] = []
            if d.tailnet_ips:
                for ip in d.tailnet_ips:
                    normalized = (ip or "").strip()
                    if not normalized:
                        continue
                    if ":" in normalized:
                        ipv6_list.append(normalized)
                    else:
                        ipv4_list.append(normalized)

            ips = ", ".join(ip for ip in (d.tailnet_ips or []) if ip) if (d.tailnet_ips) else "-"
            item = QTreeWidgetItem([
                d.name,
                ips,
                status_text,
                exit_text,
                d.os or "-"
            ])
            item.setData(1, self.DEVICE_IPV4_ROLE, ipv4_list)
            item.setData(1, self.DEVICE_IPV6_ROLE, ipv6_list)
            if not d.online:
                for col in range(self.devices_tree.columnCount()):
                    item.setForeground(col, QColor('#888'))
            if d.is_exit_node:
                item.setForeground(3, QColor('#ffd479'))
            self.devices_tree.addTopLevelItem(item)
            address_widget = self._create_device_addresses_widget(ips, ipv4_list, ipv6_list)
            self.devices_tree.setItemWidget(item, 1, address_widget)
        header = self.devices_tree.header()
        for i in range(self.devices_tree.columnCount()):
            if i == 1:
                continue
            self.devices_tree.resizeColumnToContents(i)

        # Zapewnij minimalną szerokość dla kolumny adresów, ale pozwól jej wypełniać resztę miejsca
        if header.sectionSize(1) < 420:
            header.resizeSection(1, 420)

    def _create_device_addresses_widget(self, addresses_text: str, ipv4_list: List[str], ipv6_list: List[str]) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        label = QLabel(addresses_text or "-")
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setWordWrap(True)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(label, 1)

        if ipv4_list:
            ipv4_btn = QToolButton(container)
            ipv4_btn.setText("IPv4")
            ipv4_btn.setObjectName("AddressCopyButton")
            ipv4_btn.setAutoRaise(True)
            ipv4_btn.setFocusPolicy(Qt.NoFocus)
            ipv4_btn.setCursor(Qt.PointingHandCursor)
            ipv4_btn.setToolTip("Skopiuj adresy IPv4")
            ipv4_btn.clicked.connect(
                lambda _=False, ips=list(ipv4_list): self._copy_ips_list(ips, "Adresy IPv4 urządzenia")
            )
            layout.addWidget(ipv4_btn)

        if ipv6_list:
            ipv6_btn = QToolButton(container)
            ipv6_btn.setText("IPv6")
            ipv6_btn.setObjectName("AddressCopyButton")
            ipv6_btn.setAutoRaise(True)
            ipv6_btn.setFocusPolicy(Qt.NoFocus)
            ipv6_btn.setCursor(Qt.PointingHandCursor)
            ipv6_btn.setToolTip("Skopiuj adresy IPv6")
            ipv6_btn.clicked.connect(
                lambda _=False, ips=list(ipv6_list): self._copy_ips_list(ips, "Adresy IPv6 urządzenia")
            )
            layout.addWidget(ipv6_btn)

        return container

    def _update_self_ips(self, device: Optional[Device]):
        self._self_ipv4_list = []
        self._self_ipv6_list = []

        if not device or not device.tailnet_ips:
            self.self_ips_label.setText("-")
            self._sync_copy_buttons()
            return

        for ip in device.tailnet_ips:
            normalized = (ip or "").strip()
            if not normalized:
                continue
            if ":" in normalized:
                self._self_ipv6_list.append(normalized)
            else:
                self._self_ipv4_list.append(normalized)

        segments = []
        if self._self_ipv4_list:
            segments.append(f"IPv4: {', '.join(self._self_ipv4_list)}")
        if self._self_ipv6_list:
            segments.append(f"IPv6: {', '.join(self._self_ipv6_list)}")

        if not segments:
            segments.append(", ".join(ip for ip in device.tailnet_ips if ip))

        self.self_ips_label.setText(" | ".join(segments) if segments else "-")
        self._sync_copy_buttons()

    def _on_device_context_menu(self, pos):
        item = self.devices_tree.itemAt(pos)
        if not item:
            return

        menu = QMenu(self.devices_tree)
        name = item.text(0).strip()
        addresses = item.text(1).strip()
        ipv4_list = item.data(1, self.DEVICE_IPV4_ROLE) or []
        ipv6_list = item.data(1, self.DEVICE_IPV6_ROLE) or []

        if name:
            menu.addAction("Kopiuj nazwę", lambda text=name: self._copy_to_clipboard(text, "Nazwa urządzenia"))
        if addresses and addresses != "-":
            menu.addAction(
                "Kopiuj adresy (wszystkie)",
                lambda text=addresses: self._copy_to_clipboard(text.replace(", ", "\n"), "Adresy urządzenia")
            )
        if ipv4_list:
            menu.addAction(
                "Kopiuj adresy IPv4",
                lambda ips=list(ipv4_list): self._copy_ips_list(ips, "Adresy IPv4 urządzenia")
            )
        if ipv6_list:
            menu.addAction(
                "Kopiuj adresy IPv6",
                lambda ips=list(ipv6_list): self._copy_ips_list(ips, "Adresy IPv6 urządzenia")
            )

        if menu.actions():
            global_pos = self.devices_tree.viewport().mapToGlobal(pos)
            menu.exec(global_pos)

    def _on_device_item_double_clicked(self, item, column):
        if column == 1:
            addresses = item.text(1).strip()
            if addresses and addresses != "-":
                self._copy_to_clipboard(addresses.replace(", ", "\n"), "Adresy urządzenia")
        elif column == 0:
            name = item.text(0).strip()
            if name:
                self._copy_to_clipboard(name, "Nazwa urządzenia")

    def fetch_public_ip(self, force: bool = False):
        if self._public_ip_pending:
            return

        self._public_ip_pending = True

        def task():
            return self.ip_fetcher.get_public_ip(force=force)

        def on_success(info):
            self._public_ip_pending = False
            self._on_public_ip(info)

        def on_error(msg: str):
            self._public_ip_pending = False
            if msg:
                self.statusBar().showMessage(f"Nie udało się pobrać publicznego IP: {msg}", 5000)
            self._on_public_ip(None)

        self._submit_worker(task, on_success, on_error)

    def eventFilter(self, obj, event):
        # Zdarzenia użytkownika wyzwalające przyspieszone odświeżenie
        if event.type() in (QEvent.MouseButtonPress, QEvent.KeyPress, QEvent.Wheel, QEvent.FocusIn):
            self._schedule_interaction_refresh()
        return super().eventFilter(obj, event)

    def _schedule_interaction_refresh(self):
        # Nie spamujemy – jeśli timer już odlicza, pozostawiamy
        if not self._interaction_timer.isActive():
            self._interaction_timer.start(self.INTERACTION_DEBOUNCE_MS)

    def _interaction_refresh(self):
        # Lekka ochrona przed zbyt częstym odpytywaniem – minimum 0.8s od ostatniego
        now = time.time()
        if self._last_refresh_ts and (now - self._last_refresh_ts) < 0.8:
            # Odłóż jeszcze raz minimalnie jeśli aktywność była bardzo gęsta
            self._interaction_timer.start(300)
            return
        self.refresh_status(force=True)
        self.fetch_public_ip()

    def _on_public_ip(self, info):
        if not info:
            self.public_ip_label.setText("Nie udało się pobrać")
            self.public_ip_details_label.setText("-")
            self._sync_copy_buttons()
            return
        self.public_ip_label.setText(info.ip)
        details_parts = []
        if info.org:
            details_parts.append(info.org)
        if info.asn:
            org_tokens = set(info.org.split()) if info.org else set()
            if info.asn not in org_tokens:
                details_parts.append(f"ASN {info.asn}")
        loc_parts = [p for p in [info.city, info.country] if p]
        if loc_parts:
            details_parts.append(", ".join(loc_parts))
        self.public_ip_details_label.setText(" | ".join(details_parts) or "-")
        self._sync_copy_buttons()


# --- Uruchomienie ---

def run():
    app = QApplication(sys.argv)
    app_icon = _load_app_icon()
    if app_icon:
        app.setWindowIcon(app_icon)
    win = MainWindow()
    if app_icon:
        win.setWindowIcon(app_icon)
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    run()
