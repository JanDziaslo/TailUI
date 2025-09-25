from __future__ import annotations

import sys
import threading
import time
from typing import Optional, Tuple, Dict
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QObject, QDateTime, QEvent, QRunnable, QThreadPool
from PySide6.QtGui import QIcon, QPalette, QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout,
    QComboBox, QGroupBox, QFormLayout, QStatusBar, QMessageBox, QCheckBox,
    QTreeWidget, QTreeWidgetItem, QStyle, QSplitter, QSizePolicy
)

from tailscale_client import TailscaleClient, TailscaleError, tailscale_available
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
        self._exit_action_in_progress = False
        self._exit_action_expected: Optional[Tuple[bool, Optional[str]]] = None
        self._last_exit_node_choice: Optional[str] = None
        self._exit_node_alias_map: Dict[str, str] = {}
        self._exit_node_display: Dict[str, str] = {}

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
        self.fetch_public_ip()

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

        exit_group = QGroupBox("Exit Node")
        exit_layout = QHBoxLayout(exit_group)
        self.exit_use_checkbox = QCheckBox("Używaj exit node")
        self.exit_use_checkbox.stateChanged.connect(self._exit_use_changed)
        self.exit_node_combo = QComboBox()
        self.exit_node_combo.currentIndexChanged.connect(self._exit_node_changed)
        exit_layout.addWidget(self.exit_use_checkbox)
        exit_layout.addWidget(self.exit_node_combo, 1)

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
            self.exit_use_checkbox.setEnabled(False)
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
        self.fetch_public_ip()

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
        if self.exit_use_checkbox.isChecked():
            desired_exit_node = self.exit_node_combo.currentData()
            if desired_exit_node is None and self.exit_node_combo.count() > 0:
                self.exit_node_combo.blockSignals(True)
                self.exit_node_combo.setCurrentIndex(0)
                self.exit_node_combo.blockSignals(False)
                desired_exit_node = self.exit_node_combo.currentData()
            if desired_exit_node:
                desired_exit_node = str(desired_exit_node)
                self._begin_exit_operation(True, desired_exit_node)

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
            self._end_exit_operation(True)
        self._start_poll(True)

    def _handle_connection_error(self, msg: str, exit_node_requested: bool):
        if exit_node_requested:
            self._end_exit_operation(False)
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
        self.fetch_public_ip()

    def _run_exit_node_command(self, fn, *, pending_state: Optional[Tuple[bool, Optional[str]]] = None,
                               on_success=None, on_error=None):
        was_busy = self._busy_toggle
        if not was_busy:
            self._set_busy(True)

        self.exit_use_checkbox.setEnabled(False)
        self.exit_node_combo.setEnabled(False)

        status_message = "Ustawianie exit node…"
        if pending_state is not None:
            self._begin_exit_operation(*pending_state)
            enable_flag, target_value = pending_state
            if enable_flag:
                status_message = f"Ustawianie exit node: {self._exit_node_label(target_value)}"
            else:
                status_message = "Wyłączanie exit node…"
        self.statusBar().showMessage(status_message)

        def _finalize():
            if not was_busy:
                self._set_busy(False)
            self.exit_use_checkbox.setEnabled(True)
            self.exit_node_combo.setEnabled(True)
            self.refresh_status(force=True)
            self.fetch_public_ip()

        def _success_wrapper():
            if on_success:
                on_success()
            message = "Exit node ustawiony"
            if pending_state is not None:
                enable_flag, target_value = pending_state
                if enable_flag:
                    message = f"Exit node ustawiony: {self._exit_node_label(target_value)}"
                else:
                    message = "Exit node wyłączony"
                self._end_exit_operation(True)
            self.statusBar().showMessage(message, 3000)
            _finalize()

        def _error_wrapper(msg: str):
            if pending_state is not None:
                self._end_exit_operation(False)
            if on_error:
                on_error()
            self._error(msg)
            _finalize()

        self._submit_worker(fn, lambda _: _success_wrapper(), _error_wrapper)

    def _set_exit_checkbox_checked(self, checked: bool):
        self.exit_use_checkbox.blockSignals(True)
        self.exit_use_checkbox.setChecked(checked)
        self.exit_use_checkbox.blockSignals(False)

    def _begin_exit_operation(self, enabled: bool, node_name: Optional[str]):
        self._exit_action_in_progress = True
        self._exit_action_expected = (enabled, node_name)
        if enabled and node_name:
            self._last_exit_node_choice = node_name

    def _end_exit_operation(self, success: bool):
        self._exit_action_in_progress = False
        if not success:
            self._exit_action_expected = None

    def _exit_node_label(self, target: Optional[str]) -> str:
        if not target:
            return "brak"
        return self._exit_node_display.get(target, str(target))

    def _exit_use_changed(self, state: int):
        if not self.client:
            return

        if state == Qt.Checked:
            if self.exit_node_combo.count() == 0:
                self.statusBar().showMessage("Brak dostępnych exit node", 4000)
                self._set_exit_checkbox_checked(False)
                return

            node_to_set = self.exit_node_combo.currentData()
            
            # If no node is currently selected, try to find a good selection
            if node_to_set is None:
                # First try to use the last exit node choice if it's in the current list
                if self._last_exit_node_choice:
                    for i in range(self.exit_node_combo.count()):
                        if self.exit_node_combo.itemData(i) == self._last_exit_node_choice:
                            self.exit_node_combo.blockSignals(True)
                            self.exit_node_combo.setCurrentIndex(i)
                            self.exit_node_combo.blockSignals(False)
                            node_to_set = self.exit_node_combo.currentData()
                            break
                
                # If still no node, just use the first one if available
                if not node_to_set and self.exit_node_combo.count() > 0:
                    self.exit_node_combo.blockSignals(True)
                    self.exit_node_combo.setCurrentIndex(0)
                    self.exit_node_combo.blockSignals(False)
                    node_to_set = self.exit_node_combo.currentData()

            # If we still don't have a node, something is wrong
            if not node_to_set:
                self.statusBar().showMessage("Nie można wybrać exit node z listy", 4000)
                self._set_exit_checkbox_checked(False)
                return

            node_to_set = str(node_to_set)
            self._last_exit_node_choice = node_to_set
            self._run_exit_node_command(
                lambda: self.client.set_exit_node(node_to_set),
                pending_state=(True, node_to_set)
            )
        else:
            self._run_exit_node_command(
                lambda: self.client.set_exit_node(None),
                pending_state=(False, None)
            )

    def _exit_node_changed(self, index: int):
        if not self.client or not self.exit_use_checkbox.isChecked():
            return
        if self.exit_node_combo.currentData() is None:
            return
        self._apply_exit_node_selection()

    def _apply_exit_node_selection(self):
        if not self.client:
            return

        node_target = self.exit_node_combo.currentData()
        if not node_target:
            self.statusBar().showMessage("Wybierz exit node z listy", 4000)
            return

        node_target = str(node_target)
        self._last_exit_node_choice = node_target
        self._run_exit_node_command(
            lambda: self.client.set_exit_node(node_target),
            pending_state=(True, node_target)
        )

    def _error(self, msg: str):
        self.statusBar().showMessage(msg, 10000)
        QMessageBox.warning(self, "Błąd", msg)

    # --- Odświeżanie ---
    def refresh_status(self, force: bool = False):
        if not self.client:
            return
        try:
            st = self.client.status()
        except TailscaleError as e:
            self.status_label.setText(f"błąd: {e}")
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

        # Exit nodes combo
        active_exit_device = st.active_exit_node
        active_aliases = set()
        if active_exit_device:
            if active_exit_device.name:
                active_aliases.add(str(active_exit_device.name))
            ips = [str(ip) for ip in (active_exit_device.tailnet_ips or []) if ip]
            active_aliases.update(ips)
            hostinfo = active_exit_device.hostinfo or {}
            for key in ("Hostname", "DNSName"):
                val = hostinfo.get(key)
                if val:
                    active_aliases.add(str(val))
            if active_exit_device.device_id:
                active_aliases.add(str(active_exit_device.device_id))

        previous_selection = self.exit_node_combo.currentData()
        if previous_selection is not None:
            previous_selection = str(previous_selection)
        self.exit_node_combo.blockSignals(True)
        self.exit_node_combo.clear()
        self._exit_node_alias_map.clear()
        self._exit_node_display.clear()
        for d in st.exit_nodes:
            command_source = d.device_id or next((ip for ip in (d.tailnet_ips or []) if ip), None) or d.name
            if not command_source:
                continue
            command_value = str(command_source)
            display_name = str(d.name or command_value)
            self.exit_node_combo.addItem(display_name, command_value)
            self._exit_node_display[command_value] = display_name
            aliases = {command_value}
            if d.name:
                aliases.add(str(d.name))
            if d.device_id:
                aliases.add(str(d.device_id))
            if d.tailnet_ips:
                aliases.update(str(ip) for ip in d.tailnet_ips if ip)
            hostinfo = d.hostinfo or {}
            for key in ("Hostname", "DNSName"):
                val = hostinfo.get(key)
                if val:
                    aliases.add(str(val))
            for alias in aliases:
                if alias:
                    self._exit_node_alias_map[alias] = command_value

        available_targets = set(self._exit_node_display.keys())
        if previous_selection not in available_targets:
            previous_selection = None

        active_command_value = None
        if active_exit_device:
            for alias in active_aliases:
                mapped = self._exit_node_alias_map.get(alias)
                if mapped:
                    active_command_value = mapped
                    break
            if not active_command_value and active_exit_device.device_id:
                active_command_value = str(active_exit_device.device_id)
        if active_command_value:
            active_aliases.add(active_command_value)
            self._last_exit_node_choice = active_command_value

        expected_enabled: Optional[bool] = None
        expected_target: Optional[str] = None
        expectation_matches = False
        if self._exit_action_expected:
            expected_enabled, expected_target = self._exit_action_expected
            if expected_target is not None and not isinstance(expected_target, str):
                expected_target = str(expected_target)
                self._exit_action_expected = (expected_enabled, expected_target)
            actual_enabled = active_exit_device is not None
            if expected_enabled:
                if actual_enabled:
                    if expected_target:
                        expectation_matches = (
                            expected_target == active_command_value
                            or expected_target in active_aliases
                        )
                    else:
                        expectation_matches = True
            else:
                expectation_matches = not actual_enabled

        if self._exit_action_expected and not self._exit_action_in_progress and expectation_matches:
            self._exit_action_expected = None

        if self._exit_action_in_progress or (self._exit_action_expected and not expectation_matches):
            checkbox_checked = bool(expected_enabled)
        else:
            checkbox_checked = active_exit_device is not None

        self.exit_use_checkbox.blockSignals(True)
        self.exit_use_checkbox.setChecked(checkbox_checked)
        self.exit_use_checkbox.setEnabled(bool(st.exit_nodes))
        self.exit_use_checkbox.blockSignals(False)

        preferred = None
        if self._exit_action_in_progress or (self._exit_action_expected and not expectation_matches):
            if expected_enabled and expected_target:
                preferred = expected_target
            else:
                preferred = expected_target or previous_selection or active_command_value or self._last_exit_node_choice
        else:
            preferred = active_command_value or previous_selection or self._last_exit_node_choice

        if preferred and preferred in available_targets:
            idx = self.exit_node_combo.findData(preferred)
            if idx >= 0:
                self.exit_node_combo.setCurrentIndex(idx)
        elif active_exit_device:
            for alias in active_aliases:
                translated = self._exit_node_alias_map.get(alias)
                if translated and translated in available_targets:
                    idx = self.exit_node_combo.findData(translated)
                    if idx >= 0:
                        self.exit_node_combo.setCurrentIndex(idx)
                        break
        
        # If no selection was made and combo has items, select the first one
        if self.exit_node_combo.count() > 0 and self.exit_node_combo.currentIndex() == -1:
            self.exit_node_combo.setCurrentIndex(0)
            
        self.exit_node_combo.blockSignals(False)
        self.exit_node_combo.setEnabled(bool(st.exit_nodes))

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

    def fetch_public_ip(self):
        def task():
            info = self.ip_fetcher.get_public_ip(force=True)
            self._on_public_ip(info)
        threading.Thread(target=task, daemon=True).start()

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
