from __future__ import annotations

import sys
import threading
import time
from typing import Optional
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QObject, QDateTime, QEvent
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

        self.connect_btn = QPushButton("Połącz")
        self.connect_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.connect_btn.clicked.connect(self.start_connection)
        self.connect_btn.setObjectName("ConnectButton")
        top_bar.addWidget(self.connect_btn)

        self.disconnect_btn = QPushButton("Rozłącz")
        self.disconnect_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.disconnect_btn.clicked.connect(self.stop_connection)
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.setObjectName("DisconnectButton")
        top_bar.addWidget(self.disconnect_btn)

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
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(False)
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
            QPushButton#ConnectButton {
                background-color: #50fa7b;
                color: #282a36;
            }
            QPushButton#ConnectButton:hover {
                background-color: #69ff8c;
            }
            QPushButton#DisconnectButton {
                background-color: #ff5555;
                 color: #282a36;
            }
            QPushButton#DisconnectButton:hover {
                background-color: #ff7070;
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
        if busy:
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(False)
        else:
            # Stany zostaną ustawione przez refresh_status
            pass

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
        self._poll_timer.start(300)  # delikatnie szybciej

    def _poll_iteration(self):
        if not self.client:
            self._finish_transition(error_msg="Brak klienta")
            return
        elapsed = time.time() - self._poll_started_at
        # Dobierz właściwy timeout (krótszy przy rozłączaniu)
        timeout_limit = self._disconnect_timeout_sec if self._poll_target is False else self._poll_timeout_sec
        if elapsed > timeout_limit:
            self._finish_transition(error_msg="Przekroczono czas oczekiwania na zmianę stanu")
            return
        try:
            st = self.client.status()
            if st.connected == self._poll_target:
                self._finish_transition()
                return
            # Szybka ścieżka: rozłączanie – jeśli minęło >= grace i backend nie jest 'running'
            if self._poll_target is False and (time.time() - self._down_started_at) >= self._disconnect_grace_sec:
                if st.backend_state.lower() != 'running':
                    self._finish_transition()
                    return
        except TailscaleError:
            # Jeśli oczekujemy rozłączenia i status rzuca błąd – traktuj jako sukces
            if self._poll_target is False:
                self._finish_transition()
                return
        # kontynuujemy polling

    def _finish_transition(self, error_msg: Optional[str] = None, connected: Optional[bool] = None):
        if self._poll_timer:
            self._poll_timer.stop()
            self._poll_timer.deleteLater()
            self._poll_timer = None
        self._poll_target = None
        self._set_busy(False)
        self.connect_btn.setText("Połącz")
        self.disconnect_btn.setText("Rozłącz")
        self.refresh_status(force=True)
        self.fetch_public_ip()
        if error_msg:
            self._error(error_msg)
        else:
            if connected is True:
                self.statusBar().showMessage("Połączono", 4000)
            elif connected is False:
                self.statusBar().showMessage("Rozłączono", 4000)

    def start_connection(self):
        if not self.client or self._busy_toggle:
            return
        self._set_busy(True)
        self.connect_btn.setText("Łączenie…")
        self.statusBar().showMessage("Łączenie…", 4000)

        def run_up():
            err = None
            try:
                self.client.up([])
            except TailscaleError as e:
                err = str(e)
            except Exception as e:
                err = f"Nieoczekiwany błąd: {e}"

            def after():
                self._finish_transition(error_msg=err, connected=not err)

            QTimer.singleShot(0, after)

        threading.Thread(target=run_up, daemon=True).start()

    def stop_connection(self):
        if not self.client or self._busy_toggle:
            return
        self._set_busy(True)
        self.disconnect_btn.setText("Rozłączanie…")
        self.statusBar().showMessage("Rozłączanie…", 4000)

        def run_down():
            err = None
            try:
                self.client.down()
            except TailscaleError as e:
                err = str(e)
            except Exception as e:
                err = f"Nieoczekiwany błąd: {e}"

            def after():
                self._finish_transition(error_msg=err, connected=False if not err else None)

            QTimer.singleShot(0, after)

        threading.Thread(target=run_down, daemon=True).start()

    def _manual_refresh(self):
        self.refresh_status(force=True)
        self.fetch_public_ip()

    def _exit_use_changed(self, state: int):
        if not self.client:
            return

        node_to_set = self.exit_node_combo.currentData() if state == Qt.Checked else None

        try:
            self.client.set_exit_node(node_to_set)
        except TailscaleError as e:
            self._error(str(e))
        finally:
            self.refresh_status(force=True)
            self.fetch_public_ip()

    def _exit_node_changed(self, index: int):
        if not self.client or not self.exit_use_checkbox.isChecked():
            return
        self._apply_exit_node_selection()

    def _apply_exit_node_selection(self):
        if not self.client:
            return

        node_name = self.exit_node_combo.currentData()

        try:
            self.client.set_exit_node(node_name)
        except TailscaleError as e:
            self._error(str(e))
        finally:
            self.refresh_status(force=True)
            self.fetch_public_ip()

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
        if not self._busy_toggle and self._poll_timer is None:
            self.connect_btn.setEnabled(not st.connected)
            self.disconnect_btn.setEnabled(st.connected)

        # Aktualizacja listy urządzeń
        self._populate_devices(st)

        # Adresy własne
        if st.self_device:
            self.self_ips_label.setText(", ".join(st.self_device.tailnet_ips) or "-")
        else:
            self.self_ips_label.setText("-")

        # Exit nodes combo
        current_data = self.exit_node_combo.currentData()
        self.exit_node_combo.blockSignals(True)
        self.exit_node_combo.clear()
        for d in st.exit_nodes:
            self.exit_node_combo.addItem(d.name, d.name)
        if current_data:
            idx = self.exit_node_combo.findData(current_data)
            if idx >= 0:
                self.exit_node_combo.setCurrentIndex(idx)
        self.exit_node_combo.blockSignals(False)

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
