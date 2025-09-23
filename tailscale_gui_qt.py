#!/usr/bin/env python3
"""
Tailscale GUI - Nowoczesny graficzny interfejs do zarządzania Tailscale
Wersja PyQt6 z ciemnym motywem
Autor: JanDziaslo
Data: 2025-09-23
"""

import sys
import json
import subprocess
import threading
import time
from typing import Dict, List, Optional, Tuple
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QLabel, QPushButton, QComboBox, QTextEdit, 
    QGroupBox, QMessageBox, QProgressBar, QFrame, QSplitter,
    QScrollArea, QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import (
    QThread, pyqtSignal, QTimer, Qt, QSize, QPropertyAnimation, 
    QEasingCurve, QRect
)
from PyQt6.QtGui import (
    QFont, QPalette, QColor, QIcon, QPainter, QPixmap, 
    QLinearGradient, QBrush
)

class TailscaleWorker(QThread):
    """Worker thread dla operacji Tailscale"""
    status_updated = pyqtSignal(dict)
    operation_completed = pyqtSignal(str, bool, str)  # operation, success, message
    
    def __init__(self):
        super().__init__()
        self.operation = None
        self.args = []
        self.running = True
        
    def run_command(self, operation: str, args: List[str]):
        """Uruchom komendę Tailscale"""
        self.operation = operation
        self.args = args
        self.start()
        
    def refresh_status(self):
        """Odśwież status"""
        self.operation = "status"
        self.args = ["status", "--json"]
        self.start()
        
    def run(self):
        """Główna pętla worker thread"""
        if self.operation == "status":
            self._get_status()
        else:
            self._run_operation()
            
    def _get_status(self):
        """Pobierz status Tailscale"""
        try:
            result = subprocess.run(
                ['tailscale'] + self.args, 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            if result.returncode == 0:
                try:
                    status_data = json.loads(result.stdout.strip())
                    self.status_updated.emit(status_data)
                except json.JSONDecodeError:
                    self.status_updated.emit({})
            else:
                self.status_updated.emit({})
        except Exception:
            self.status_updated.emit({})
            
    def _run_operation(self):
        """Wykonaj operację Tailscale"""
        try:
            result = subprocess.run(
                ['tailscale'] + self.args,
                capture_output=True,
                text=True,
                timeout=30
            )
            success = result.returncode == 0
            message = result.stdout.strip() if success else result.stderr.strip()
            self.operation_completed.emit(self.operation, success, message)
        except subprocess.TimeoutExpired:
            self.operation_completed.emit(self.operation, False, "Timeout podczas wykonywania operacji")
        except Exception as e:
            self.operation_completed.emit(self.operation, False, f"Błąd: {str(e)}")

class StatusIndicator(QWidget):
    """Niestandardowy wskaźnik statusu z animacją"""
    
    def __init__(self):
        super().__init__()
        self.status = "unknown"  # unknown, connected, disconnected, error
        self.setFixedSize(24, 24)
        
        # Animacja
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
    def set_status(self, status: str):
        """Ustaw status wskaźnika"""
        if self.status != status:
            self.status = status
            self.update()
            
    def paintEvent(self, event):
        """Rysuj wskaźnik"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Kolory w zależności od statusu
        colors = {
            "connected": QColor(76, 175, 80),      # Zielony
            "disconnected": QColor(255, 152, 0),   # Pomarańczowy
            "error": QColor(244, 67, 54),          # Czerwony
            "unknown": QColor(158, 158, 158)       # Szary
        }
        
        color = colors.get(self.status, colors["unknown"])
        
        # Użyj solidnego koloru zamiast gradientu
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, self.width()-4, self.height()-4)
        
        # Dodaj subtelny efekt świecenia przez namalowanie mniejszego koła
        inner_color = color.lighter(150)
        painter.setBrush(QBrush(inner_color))
        painter.drawEllipse(6, 6, self.width()-12, self.height()-12)

class ModernButton(QPushButton):
    """Nowoczesny przycisk z efektami hover"""
    
    def __init__(self, text: str, button_type: str = "primary"):
        super().__init__(text)
        self.button_type = button_type
        self.setup_style()
        
    def setup_style(self):
        """Konfiguruj style przycisku"""
        base_style = """
            QPushButton {
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 13px;
                min-height: 24px;
            }
            QPushButton:disabled {
                opacity: 0.5;
            }
        """
        
        if self.button_type == "primary":
            style = base_style + """
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: 1px solid #45a049;
                }
                QPushButton:hover {
                    background-color: #5CBF60;
                    border-color: #55b059;
                }
                QPushButton:pressed {
                    background-color: #3C9F40;
                    border-color: #359039;
                }
            """
        elif self.button_type == "danger":
            style = base_style + """
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: 1px solid #d32f2f;
                }
                QPushButton:hover {
                    background-color: #f66356;
                    border-color: #e34f4f;
                }
                QPushButton:pressed {
                    background-color: #d32f2f;
                    border-color: #b71c1c;
                }
            """
        else:  # secondary
            style = base_style + """
                QPushButton {
                    background-color: #424242;
                    color: #E0E0E0;
                    border: 1px solid #555;
                }
                QPushButton:hover {
                    background-color: #525252;
                    border-color: #666;
                }
                QPushButton:pressed {
                    background-color: #303030;
                    border-color: #444;
                }
            """
            
        self.setStyleSheet(style)

class TailscaleGUI(QMainWindow):
    """Główna klasa aplikacji Tailscale GUI"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tailscale GUI Manager")
        self.setMinimumSize(900, 700)
        self.resize(1000, 800)
        
        # Dane stanu
        self.status_data = {}
        self.exit_nodes = []
        self.is_connected = False
        
        # Worker thread
        self.worker = TailscaleWorker()
        self.worker.status_updated.connect(self.on_status_updated)
        self.worker.operation_completed.connect(self.on_operation_completed)
        
        # Timer dla auto-refresh
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_status)
        self.refresh_timer.start(30000)  # 30 sekund
        
        self.setup_ui()
        self.apply_dark_theme()
        self.refresh_status()
        
    def setup_ui(self):
        """Konfiguracja interfejsu użytkownika"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Główny layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Header z logo i statusem
        self.create_header(main_layout)
        
        # Splitter dla głównej zawartości
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Lewa strona - kontrole
        left_widget = self.create_controls_panel()
        splitter.addWidget(left_widget)
        
        # Prawa strona - informacje
        right_widget = self.create_info_panel()
        splitter.addWidget(right_widget)
        
        # Ustaw proporcje splittera
        splitter.setSizes([400, 600])
        
        # Footer
        self.create_footer(main_layout)
        
    def create_header(self, parent_layout):
        """Stwórz header aplikacji"""
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #2A2A2A;
                border: 1px solid #404040;
                border-radius: 12px;
                padding: 10px;
            }
        """)
        
        header_layout = QHBoxLayout(header_frame)
        
        # Logo i tytuł
        title_layout = QVBoxLayout()
        title_label = QLabel("Tailscale Manager")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #4CAF50;")
        subtitle_label = QLabel("Nowoczesny interfejs zarządzania VPN")
        subtitle_label.setStyleSheet("font-size: 12px; color: #888; margin-top: -5px;")
        
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)
        header_layout.addLayout(title_layout)
        
        header_layout.addStretch()
        
        # Status indicator
        status_layout = QHBoxLayout()
        self.status_indicator = StatusIndicator()
        self.status_text = QLabel("Sprawdzanie statusu...")
        self.status_text.setStyleSheet("font-size: 14px; color: #E0E0E0;")
        
        status_layout.addWidget(self.status_indicator)
        status_layout.addWidget(self.status_text)
        header_layout.addLayout(status_layout)
        
        # Refresh button
        self.refresh_btn = ModernButton("⟳ Odśwież", "secondary")
        self.refresh_btn.clicked.connect(self.refresh_status)
        header_layout.addWidget(self.refresh_btn)
        
        parent_layout.addWidget(header_frame)
        
    def create_controls_panel(self):
        """Stwórz panel kontroli"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        
        # Kontrola połączenia
        conn_group = QGroupBox("Kontrola połączenia")
        conn_group.setStyleSheet(self.get_groupbox_style())
        conn_layout = QVBoxLayout(conn_group)
        
        buttons_layout = QHBoxLayout()
        self.connect_btn = ModernButton("🔗 Połącz", "primary")
        self.disconnect_btn = ModernButton("🔌 Rozłącz", "danger")
        
        self.connect_btn.clicked.connect(self.connect_tailscale)
        self.disconnect_btn.clicked.connect(self.disconnect_tailscale)
        
        buttons_layout.addWidget(self.connect_btn)
        buttons_layout.addWidget(self.disconnect_btn)
        conn_layout.addLayout(buttons_layout)
        
        layout.addWidget(conn_group)
        
        # Exit Node
        exit_group = QGroupBox("Exit Node")
        exit_group.setStyleSheet(self.get_groupbox_style())
        exit_layout = QVBoxLayout(exit_group)
        
        # Combo box dla Exit Nodes
        self.exit_node_combo = QComboBox()
        self.exit_node_combo.setStyleSheet(self.get_combo_style())
        exit_layout.addWidget(QLabel("Dostępne Exit Nodes:"))
        exit_layout.addWidget(self.exit_node_combo)
        
        # Przyciski Exit Node
        exit_buttons_layout = QHBoxLayout()
        self.set_exit_btn = ModernButton("✓ Ustaw", "primary")
        self.disable_exit_btn = ModernButton("✗ Wyłącz", "secondary")
        
        self.set_exit_btn.clicked.connect(self.set_exit_node)
        self.disable_exit_btn.clicked.connect(self.disable_exit_node)
        
        exit_buttons_layout.addWidget(self.set_exit_btn)
        exit_buttons_layout.addWidget(self.disable_exit_btn)
        exit_layout.addLayout(exit_buttons_layout)
        
        # Status Exit Node
        self.exit_status_label = QLabel("Exit Node: Wyłączony")
        self.exit_status_label.setStyleSheet("color: #BBB; margin-top: 10px;")
        exit_layout.addWidget(self.exit_status_label)
        
        layout.addWidget(exit_group)
        
        # Progress bar dla operacji
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #555;
                border-radius: 8px;
                text-align: center;
                background-color: #2E2E2E;
                color: #E0E0E0;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        layout.addStretch()
        return widget
        
    def create_info_panel(self):
        """Stwórz panel informacji"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Informacje o urządzeniu
        info_group = QGroupBox("Informacje o urządzeniu")
        info_group.setStyleSheet(self.get_groupbox_style())
        info_layout = QVBoxLayout(info_group)
        
        # Text widget z informacjami
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setStyleSheet("""
            QTextEdit {
                background: #1E1E1E;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 10px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                color: #E0E0E0;
                line-height: 1.4;
            }
        """)
        info_layout.addWidget(self.info_text)
        
        layout.addWidget(info_group)
        return widget
        
    def create_footer(self, parent_layout):
        """Stwórz footer aplikacji"""
        footer_layout = QHBoxLayout()
        
        # Informacje o wersji
        version_label = QLabel("Tailscale GUI v2.0 | PyQt6")
        version_label.setStyleSheet("color: #666; font-size: 11px;")
        footer_layout.addWidget(version_label)
        
        footer_layout.addStretch()
        
        # Przyciski akcji
        update_btn = ModernButton("📊 Aktualizuj", "secondary")
        update_btn.clicked.connect(self.refresh_status)
        
        quit_btn = ModernButton("🚪 Zamknij", "secondary")
        quit_btn.clicked.connect(self.close)
        
        footer_layout.addWidget(update_btn)
        footer_layout.addWidget(quit_btn)
        
        parent_layout.addLayout(footer_layout)
        
    def get_groupbox_style(self):
        """Zwróć style dla QGroupBox"""
        return """
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #444;
                border-radius: 12px;
                margin-top: 8px;
                padding-top: 10px;
                background-color: #252525;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #4CAF50;
                background-color: transparent;
            }
        """
        
    def get_combo_style(self):
        """Zwróć style dla QComboBox"""
        return """
            QComboBox {
                border: 2px solid #444;
                border-radius: 8px;
                padding: 6px 12px;
                background: #2E2E2E;
                color: #E0E0E0;
                font-size: 13px;
                min-height: 20px;
            }
            QComboBox:hover {
                border-color: #4CAF50;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #888;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background: #2E2E2E;
                border: 1px solid #444;
                selection-background-color: #4CAF50;
                color: #E0E0E0;
            }
        """
        
    def apply_dark_theme(self):
        """Zastosuj ciemny motyw"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1E1E1E;
                color: #E0E0E0;
            }
            QWidget {
                background-color: transparent;
                color: #E0E0E0;
            }
            QLabel {
                color: #E0E0E0;
                background-color: transparent;
            }
            QMessageBox {
                background-color: #2E2E2E;
                color: #E0E0E0;
            }
            QMessageBox QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QSplitter::handle {
                background-color: #404040;
            }
            QSplitter::handle:horizontal {
                width: 3px;
            }
            QSplitter::handle:vertical {
                height: 3px;
            }
        """)
        
    def refresh_status(self):
        """Odśwież status Tailscale"""
        self.worker.refresh_status()
        
    def on_status_updated(self, status_data: dict):
        """Callback dla aktualizacji statusu"""
        self.status_data = status_data
        self.update_ui_from_status()
        
    def update_ui_from_status(self):
        """Aktualizuj UI na podstawie statusu"""
        if not self.status_data:
            self.status_indicator.set_status("error")
            self.status_text.setText("Tailscale niedostępny")
            self.is_connected = False
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
            return
            
        backend_state = self.status_data.get('BackendState', 'Unknown')
        
        if backend_state == 'Running':
            self.status_indicator.set_status("connected")
            self.status_text.setText("✅ Połączony")
            self.is_connected = True
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
        elif backend_state == 'Stopped':
            self.status_indicator.set_status("disconnected")
            self.status_text.setText("⏸️ Rozłączony")
            self.is_connected = False
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
        else:
            self.status_indicator.set_status("unknown")
            self.status_text.setText(f"🔄 Status: {backend_state}")
            self.is_connected = False
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(True)
            
        self.update_exit_nodes()
        self.update_device_info()
        
    def update_exit_nodes(self):
        """Aktualizuj listę Exit Nodes"""
        self.exit_nodes.clear()
        self.exit_node_combo.clear()
        
        if not self.status_data:
            return
            
        peers = self.status_data.get('Peer', {})
        
        for peer_id, peer_info in peers.items():
            if peer_info.get('ExitNode', False):
                name = peer_info.get('DNSName', peer_info.get('HostName', peer_id))
                self.exit_nodes.append((name, peer_id))
                self.exit_node_combo.addItem(f"🌐 {name}", peer_id)
                
        # Sprawdź aktualny Exit Node
        current_exit = self.status_data.get('ExitNodeStatus')
        if current_exit and current_exit.get('ID'):
            for i, (name, peer_id) in enumerate(self.exit_nodes):
                if peer_id == current_exit['ID']:
                    self.exit_node_combo.setCurrentIndex(i)
                    self.exit_status_label.setText(f"✅ Exit Node: {name}")
                    break
        else:
            self.exit_status_label.setText("❌ Exit Node: Wyłączony")
            
    def update_device_info(self):
        """Aktualizuj informacje o urządzeniu"""
        if not self.status_data:
            self.info_text.setHtml("""
                <div style='color: #888; text-align: center; padding: 20px;'>
                    <h3>❌ Brak danych o urządzeniu</h3>
                    <p>Tailscale nie jest dostępny lub nie jest połączony</p>
                </div>
            """)
            return
            
        # Przygotuj HTML z informacjami
        html_content = self.generate_device_info_html()
        self.info_text.setHtml(html_content)
        
    def generate_device_info_html(self):
        """Generuj HTML z informacjami o urządzeniu"""
        self_info = self.status_data.get('Self', {})
        
        html = """
        <div style='font-family: "Segoe UI", Arial, sans-serif; line-height: 1.6;'>
        """
        
        # Informacje o urządzeniu
        html += """
        <div style='background: #2A2A2A; border-radius: 8px; padding: 15px; margin-bottom: 15px; border-left: 4px solid #4CAF50;'>
            <h3 style='color: #4CAF50; margin-top: 0;'>🖥️ Informacje o urządzeniu</h3>
        """
        
        device_info = [
            ("📝 Nazwa", self_info.get('HostName', 'N/A')),
            ("🌐 DNS Name", self_info.get('DNSName', 'N/A')),
            ("🔗 IP Tailscale", ', '.join(self_info.get('TailscaleIPs', []))),
            ("💻 System", self_info.get('OS', 'N/A')),
            ("🟢 Online", '✅ Tak' if self_info.get('Online') else '❌ Nie'),
        ]
        
        for label, value in device_info:
            html += f"<p><strong>{label}:</strong> <span style='color: #E0E0E0;'>{value}</span></p>"
            
        html += "</div>"
        
        # Status połączenia
        html += """
        <div style='background: #2A2A2A; border-radius: 8px; padding: 15px; margin-bottom: 15px; border-left: 4px solid #2196F3;'>
            <h3 style='color: #2196F3; margin-top: 0;'>📡 Status połączenia</h3>
        """
        
        connection_info = [
            ("🔧 Stan backendu", self.status_data.get('BackendState', 'N/A')),
            ("📦 Wersja", self.status_data.get('Version', 'N/A')),
        ]
        
        for label, value in connection_info:
            html += f"<p><strong>{label}:</strong> <span style='color: #E0E0E0;'>{value}</span></p>"
            
        html += "</div>"
        
        # Exit Node info
        exit_status = self.status_data.get('ExitNodeStatus')
        html += """
        <div style='background: #2A2A2A; border-radius: 8px; padding: 15px; margin-bottom: 15px; border-left: 4px solid #FF9800;'>
            <h3 style='color: #FF9800; margin-top: 0;'>🚪 Exit Node</h3>
        """
        
        if exit_status and exit_status.get('ID'):
            html += f"<p><strong>✅ Aktywny:</strong> <span style='color: #4CAF50;'>Tak</span></p>"
            html += f"<p><strong>🆔 ID:</strong> <span style='color: #E0E0E0;'>{exit_status['ID']}</span></p>"
            if 'Name' in exit_status:
                html += f"<p><strong>📝 Nazwa:</strong> <span style='color: #E0E0E0;'>{exit_status['Name']}</span></p>"
        else:
            html += "<p><strong>❌ Aktywny:</strong> <span style='color: #888;'>Nie</span></p>"
            
        html += "</div>"
        
        # Lista urządzeń
        peers = self.status_data.get('Peer', {})
        if peers:
            html += """
            <div style='background: #2A2A2A; border-radius: 8px; padding: 15px; margin-bottom: 15px; border-left: 4px solid #9C27B0;'>
                <h3 style='color: #9C27B0; margin-top: 0;'>🌐 Dostępne urządzenia</h3>
            """
            
            for peer_id, peer_info in peers.items():
                name = peer_info.get('HostName', peer_id[:8])
                online_status = "🟢 Online" if peer_info.get('Online') else "🔴 Offline"
                exit_node_badge = " <span style='background: #4CAF50; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px;'>EXIT NODE</span>" if peer_info.get('ExitNode') else ""
                
                html += f"<p>• <strong>{name}</strong> - {online_status}{exit_node_badge}</p>"
                
            html += "</div>"
            
        html += "</div>"
        return html
        
    def show_progress(self, message: str):
        """Pokaż progress bar z wiadomością"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.status_text.setText(message)
        
    def hide_progress(self):
        """Ukryj progress bar"""
        self.progress_bar.setVisible(False)
        
    def connect_tailscale(self):
        """Połącz z Tailscale"""
        self.show_progress("🔗 Łączenie z Tailscale...")
        self.worker.run_command("connect", ["up"])
        
    def disconnect_tailscale(self):
        """Rozłącz z Tailscale"""
        reply = QMessageBox.question(
            self, 
            "Potwierdzenie", 
            "Czy na pewno chcesz rozłączyć Tailscale?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.show_progress("🔌 Rozłączanie Tailscale...")
            self.worker.run_command("disconnect", ["down"])
            
    def set_exit_node(self):
        """Ustaw Exit Node"""
        current_index = self.exit_node_combo.currentIndex()
        if current_index < 0:
            QMessageBox.warning(self, "Błąd", "Wybierz Exit Node z listy")
            return
            
        selected_peer_id = self.exit_node_combo.currentData()
        selected_name = self.exit_node_combo.currentText()
        
        self.show_progress(f"🌐 Ustawianie Exit Node: {selected_name}")
        self.worker.run_command("set_exit", ["set", f"--exit-node={selected_peer_id}"])
        
    def disable_exit_node(self):
        """Wyłącz Exit Node"""
        self.show_progress("❌ Wyłączanie Exit Node...")
        self.worker.run_command("disable_exit", ["set", "--exit-node="])
        
    def on_operation_completed(self, operation: str, success: bool, message: str):
        """Callback dla zakończenia operacji"""
        self.hide_progress()
        
        if success:
            if operation == "connect":
                QMessageBox.information(self, "Sukces", "✅ Tailscale został uruchomiony")
            elif operation == "disconnect":
                QMessageBox.information(self, "Sukces", "✅ Tailscale został zatrzymany")
            elif operation == "set_exit":
                QMessageBox.information(self, "Sukces", "✅ Exit Node został ustawiony")
            elif operation == "disable_exit":
                QMessageBox.information(self, "Sukces", "✅ Exit Node został wyłączony")
                
            # Odśwież status po sekundzie
            QTimer.singleShot(1000, self.refresh_status)
        else:
            QMessageBox.critical(self, "Błąd", f"❌ Operacja nieudana:\n{message}")

def main():
    """Funkcja główna"""
    app = QApplication(sys.argv)
    
    # Ustaw informacje o aplikacji
    app.setApplicationName("Tailscale GUI")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("JanDziaslo")
    
    # Stwórz i pokaż główne okno
    window = TailscaleGUI()
    window.show()
    
    # Uruchom aplikację
    sys.exit(app.exec())

if __name__ == "__main__":
    main()