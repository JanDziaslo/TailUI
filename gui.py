from __future__ import annotations

import sys
import time
from typing import Optional, Dict, Set, Callable
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QObject, QDateTime, QEvent, QRunnable, QThreadPool
from PySide6.QtGui import QIcon, QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout,
    QComboBox, QGroupBox, QFormLayout, QStatusBar, QMessageBox, QCheckBox,
    QTreeWidget, QTreeWidgetItem, QStyle, QSplitter, QSizePolicy
)

from tailscale_client import TailscaleClient, TailscaleError, tailscale_available, Device
from ip_info import PublicIPFetcher


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

        icon_path = Path(__file__).parent / 'assets_icon_tailscale.svg'
        if icon_path.exists():
            app_icon = QIcon(str(icon_path))
            self.setWindowIcon(app_icon)
            self.icon_label = QLabel()
            pm = QPixmap(str(icon_path))
            if not pm.isNull():
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
        self.devices_tree.setUniformRowHeights(True)
        devices_layout.addWidget(self.devices_tree)

        info_group = QGroupBox("Informacje o urządzeniu")
        info_form = QFormLayout(info_group)
        info_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.status_label = QLabel("-")
        self.self_ips_label = QLabel("-")
        self.public_ip_label = QLabel("-")
        self.public_ip_details_label = QLabel("-")
        self.public_ip_details_label.setWordWrap(True)
        info_form.addRow("Stan:", self.status_label)
        info_form.addRow("Adresy Tailnet:", self.self_ips_label)
        info_form.addRow("Publiczne IP:", self.public_ip_label)
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
                height: 30px;
                padding: 2px;
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

    # --- Pomocnicze busy ---
    def _set_busy(self, busy: bool):
        self._busy_toggle = busy
        self.toggle_button.setEnabled(not busy)

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
            self._sync_exit_controls_enabled()
            return
        try:
            st = self.client.status()
        except TailscaleError as e:
            self.status_label.setText(f"błąd: {e}")
            self._exit_has_nodes = False
            self._exit_active_value = None
            self._sync_exit_controls_enabled()
            return

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
        if st.self_device:
            self.self_ips_label.setText(", ".join(st.self_device.tailnet_ips) or "-")
        else:
            self.self_ips_label.setText("-")

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
            ips = ", ".join(d.tailnet_ips) if d.tailnet_ips else "-"
            item = QTreeWidgetItem([
                d.name,
                ips,
                status_text,
                exit_text,
                d.os or "-"
            ])
            if not d.online:
                for col in range(self.devices_tree.columnCount()):
                    item.setForeground(col, QColor('#888'))
            if d.is_exit_node:
                item.setForeground(3, QColor('#ffd479'))
            self.devices_tree.addTopLevelItem(item)
        for i in range(self.devices_tree.columnCount()):
            self.devices_tree.resizeColumnToContents(i)
        self.devices_tree.setColumnWidth(1, min(self.devices_tree.columnWidth(1), 360))

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


# --- Uruchomienie ---

def run():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    run()
