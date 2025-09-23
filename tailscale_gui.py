#!/usr/bin/env python3
"""
Tailscale GUI - Graficzny interfejs do zarządzania Tailscale
Autor: JanDziaslo
Data: 2025-09-23
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import json
import threading
import time
from typing import Dict, List, Optional

class TailscaleGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Tailscale GUI Manager")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # Zmienne stanu
        self.status_data = {}
        self.exit_nodes = []
        self.current_exit_node = None
        self.is_connected = False
        
        self.setup_ui()
        self.refresh_status()
        
    def setup_ui(self):
        """Konfiguracja interfejsu użytkownika"""
        # Główny kontener
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Konfiguracja grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Sekcja statusu
        self.create_status_section(main_frame, 0)
        
        # Sekcja kontroli połączenia
        self.create_connection_section(main_frame, 1)
        
        # Sekcja Exit Node
        self.create_exit_node_section(main_frame, 2)
        
        # Sekcja informacji
        self.create_info_section(main_frame, 3)
        
        # Przyciski akcji
        self.create_action_buttons(main_frame, 4)
        
    def create_status_section(self, parent, row):
        """Sekcja statusu połączenia"""
        status_frame = ttk.LabelFrame(parent, text="Status połączenia", padding="10")
        status_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        status_frame.columnconfigure(1, weight=1)
        
        # Status LED
        self.status_label = ttk.Label(status_frame, text="●", font=("Arial", 20))
        self.status_label.grid(row=0, column=0, padx=5)
        
        # Opis statusu
        self.status_text = ttk.Label(status_frame, text="Sprawdzanie statusu...", font=("Arial", 12))
        self.status_text.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        # Przycisk odświeżania
        refresh_btn = ttk.Button(status_frame, text="Odśwież", command=self.refresh_status)
        refresh_btn.grid(row=0, column=2, padx=5)
        
    def create_connection_section(self, parent, row):
        """Sekcja kontroli połączenia"""
        conn_frame = ttk.LabelFrame(parent, text="Kontrola połączenia", padding="10")
        conn_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Przyciski połączenia
        self.connect_btn = ttk.Button(conn_frame, text="Połącz", command=self.connect_tailscale)
        self.connect_btn.grid(row=0, column=0, padx=5)
        
        self.disconnect_btn = ttk.Button(conn_frame, text="Rozłącz", command=self.disconnect_tailscale)
        self.disconnect_btn.grid(row=0, column=1, padx=5)
        
    def create_exit_node_section(self, parent, row):
        """Sekcja Exit Node"""
        exit_frame = ttk.LabelFrame(parent, text="Exit Node", padding="10")
        exit_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        exit_frame.columnconfigure(1, weight=1)
        
        # Lista Exit Nodes
        ttk.Label(exit_frame, text="Dostępne Exit Nodes:").grid(row=0, column=0, sticky=tk.W, pady=2)
        
        self.exit_node_var = tk.StringVar()
        self.exit_node_combo = ttk.Combobox(exit_frame, textvariable=self.exit_node_var, state="readonly")
        self.exit_node_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=2)
        
        # Przyciski Exit Node
        btn_frame = ttk.Frame(exit_frame)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=5)
        
        self.set_exit_btn = ttk.Button(btn_frame, text="Ustaw Exit Node", command=self.set_exit_node)
        self.set_exit_btn.grid(row=0, column=0, padx=5)
        
        self.disable_exit_btn = ttk.Button(btn_frame, text="Wyłącz Exit Node", command=self.disable_exit_node)
        self.disable_exit_btn.grid(row=0, column=1, padx=5)
        
        # Status Exit Node
        self.exit_status_label = ttk.Label(exit_frame, text="Exit Node: Wyłączony")
        self.exit_status_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=2)
        
    def create_info_section(self, parent, row):
        """Sekcja informacji"""
        info_frame = ttk.LabelFrame(parent, text="Informacje o urządzeniu", padding="10")
        info_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        info_frame.columnconfigure(0, weight=1)
        info_frame.rowconfigure(0, weight=1)
        
        # Text widget z scrollbarem
        text_frame = ttk.Frame(info_frame)
        text_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        self.info_text = tk.Text(text_frame, height=10, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.info_text.yview)
        self.info_text.configure(yscrollcommand=scrollbar.set)
        
        self.info_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        parent.rowconfigure(row, weight=1)
        
    def create_action_buttons(self, parent, row):
        """Przyciski akcji"""
        action_frame = ttk.Frame(parent)
        action_frame.grid(row=row, column=0, columnspan=2, pady=10)
        
        ttk.Button(action_frame, text="Zaktualizuj informacje", command=self.update_device_info).grid(row=0, column=0, padx=5)
        ttk.Button(action_frame, text="Zamknij", command=self.root.quit).grid(row=0, column=1, padx=5)
        
    def run_tailscale_command(self, args: List[str]) -> Optional[str]:
        """Wykonanie komendy tailscale"""
        try:
            result = subprocess.run(['tailscale'] + args, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                messagebox.showerror("Błąd", f"Błąd komendy tailscale: {result.stderr}")
                return None
        except subprocess.TimeoutExpired:
            messagebox.showerror("Błąd", "Timeout podczas wykonywania komendy tailscale")
            return None
        except FileNotFoundError:
            messagebox.showerror("Błąd", "Tailscale nie jest zainstalowany lub nie znajduje się w PATH")
            return None
        except Exception as e:
            messagebox.showerror("Błąd", f"Nieoczekiwany błąd: {str(e)}")
            return None
            
    def refresh_status(self):
        """Odświeżenie statusu połączenia"""
        def update_status():
            # Pobierz status
            status_output = self.run_tailscale_command(['status', '--json'])
            if status_output:
                try:
                    self.status_data = json.loads(status_output)
                    self.is_connected = True
                    
                    # Aktualizuj GUI w głównym wątku
                    self.root.after(0, self.update_status_ui)
                    self.root.after(0, self.update_exit_nodes)
                    self.root.after(0, self.update_device_info)
                except json.JSONDecodeError:
                    self.is_connected = False
                    self.root.after(0, lambda: self.update_status_label("Błąd parsowania statusu", "red"))
            else:
                self.is_connected = False
                self.root.after(0, lambda: self.update_status_label("Tailscale niedostępny", "red"))
                
        # Uruchom w tle
        threading.Thread(target=update_status, daemon=True).start()
        
    def update_status_ui(self):
        """Aktualizacja interfejsu statusu"""
        if self.is_connected and self.status_data:
            backend_state = self.status_data.get('BackendState', 'Unknown')
            
            if backend_state == 'Running':
                self.update_status_label("Połączony", "green")
                self.connect_btn.config(state=tk.DISABLED)
                self.disconnect_btn.config(state=tk.NORMAL)
            elif backend_state == 'Stopped':
                self.update_status_label("Rozłączony", "orange")
                self.connect_btn.config(state=tk.NORMAL)
                self.disconnect_btn.config(state=tk.DISABLED)
            else:
                self.update_status_label(f"Status: {backend_state}", "orange")
                self.connect_btn.config(state=tk.NORMAL)
                self.disconnect_btn.config(state=tk.NORMAL)
        else:
            self.update_status_label("Brak połączenia", "red")
            self.connect_btn.config(state=tk.NORMAL)
            self.disconnect_btn.config(state=tk.DISABLED)
            
    def update_status_label(self, text: str, color: str):
        """Aktualizacja etykiety statusu"""
        self.status_label.config(foreground=color)
        self.status_text.config(text=text)
        
    def update_exit_nodes(self):
        """Aktualizacja listy Exit Nodes"""
        if not self.is_connected or not self.status_data:
            return
            
        self.exit_nodes = []
        peers = self.status_data.get('Peer', {})
        
        for peer_id, peer_info in peers.items():
            if peer_info.get('ExitNode', False):
                name = peer_info.get('DNSName', peer_info.get('HostName', peer_id))
                self.exit_nodes.append((name, peer_id))
                
        # Aktualizuj combobox
        exit_node_names = [name for name, _ in self.exit_nodes]
        self.exit_node_combo['values'] = exit_node_names
        
        # Sprawdź aktualny Exit Node
        current_exit = self.status_data.get('ExitNodeStatus')
        if current_exit and current_exit.get('ID'):
            for name, peer_id in self.exit_nodes:
                if peer_id == current_exit['ID']:
                    self.exit_node_var.set(name)
                    self.exit_status_label.config(text=f"Exit Node: {name}")
                    break
        else:
            self.exit_node_var.set("")
            self.exit_status_label.config(text="Exit Node: Wyłączony")
            
    def update_device_info(self):
        """Aktualizacja informacji o urządzeniu"""
        if not self.is_connected or not self.status_data:
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(tk.END, "Brak danych o urządzeniu")
            return
            
        # Przygotuj informacje
        info_lines = []
        
        # Informacje o urządzeniu
        self_info = self.status_data.get('Self', {})
        info_lines.append("=== INFORMACJE O URZĄDZENIU ===")
        info_lines.append(f"Nazwa: {self_info.get('HostName', 'N/A')}")
        info_lines.append(f"DNS Name: {self_info.get('DNSName', 'N/A')}")
        info_lines.append(f"IP Tailscale: {', '.join(self_info.get('TailscaleIPs', []))}")
        info_lines.append(f"OS: {self_info.get('OS', 'N/A')}")
        info_lines.append(f"Online: {'Tak' if self_info.get('Online') else 'Nie'}")
        info_lines.append("")
        
        # Status backendu
        info_lines.append("=== STATUS POŁĄCZENIA ===")
        info_lines.append(f"Stan backendu: {self.status_data.get('BackendState', 'N/A')}")
        info_lines.append(f"Wersja: {self.status_data.get('Version', 'N/A')}")
        info_lines.append("")
        
        # Exit Node
        exit_status = self.status_data.get('ExitNodeStatus')
        info_lines.append("=== EXIT NODE ===")
        if exit_status and exit_status.get('ID'):
            info_lines.append(f"Aktywny: Tak")
            info_lines.append(f"ID: {exit_status['ID']}")
            if 'Name' in exit_status:
                info_lines.append(f"Nazwa: {exit_status['Name']}")
        else:
            info_lines.append("Aktywny: Nie")
        info_lines.append("")
        
        # Peers
        peers = self.status_data.get('Peer', {})
        if peers:
            info_lines.append("=== DOSTĘPNE URZĄDZENIA ===")
            for peer_id, peer_info in peers.items():
                name = peer_info.get('HostName', peer_id[:8])
                online = "Online" if peer_info.get('Online') else "Offline"
                exit_node = " (Exit Node)" if peer_info.get('ExitNode') else ""
                info_lines.append(f"• {name} - {online}{exit_node}")
                
        # Wyświetl informacje
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, "\n".join(info_lines))
        
    def connect_tailscale(self):
        """Połączenie z Tailscale"""
        def connect():
            result = self.run_tailscale_command(['up'])
            if result is not None:
                self.root.after(0, lambda: messagebox.showinfo("Sukces", "Tailscale został uruchomiony"))
                self.root.after(1000, self.refresh_status)  # Odśwież po sekundzie
            
        threading.Thread(target=connect, daemon=True).start()
        
    def disconnect_tailscale(self):
        """Rozłączenie z Tailscale"""
        if messagebox.askyesno("Potwierdzenie", "Czy na pewno chcesz rozłączyć Tailscale?"):
            def disconnect():
                result = self.run_tailscale_command(['down'])
                if result is not None:
                    self.root.after(0, lambda: messagebox.showinfo("Sukces", "Tailscale został zatrzymany"))
                    self.root.after(1000, self.refresh_status)  # Odśwież po sekundzie
                
            threading.Thread(target=disconnect, daemon=True).start()
            
    def set_exit_node(self):
        """Ustawienie Exit Node"""
        selected_name = self.exit_node_var.get()
        if not selected_name:
            messagebox.showwarning("Błąd", "Wybierz Exit Node z listy")
            return
            
        # Znajdź ID wybranego Exit Node
        selected_id = None
        for name, peer_id in self.exit_nodes:
            if name == selected_name:
                selected_id = peer_id
                break
                
        if not selected_id:
            messagebox.showerror("Błąd", "Nie można znaleźć wybranego Exit Node")
            return
            
        def set_exit():
            result = self.run_tailscale_command(['set', '--exit-node', selected_id])
            if result is not None:
                self.root.after(0, lambda: messagebox.showinfo("Sukces", f"Exit Node ustawiony na: {selected_name}"))
                self.root.after(1000, self.refresh_status)
                
        threading.Thread(target=set_exit, daemon=True).start()
        
    def disable_exit_node(self):
        """Wyłączenie Exit Node"""
        def disable_exit():
            result = self.run_tailscale_command(['set', '--exit-node='])
            if result is not None:
                self.root.after(0, lambda: messagebox.showinfo("Sukces", "Exit Node został wyłączony"))
                self.root.after(1000, self.refresh_status)
                
        threading.Thread(target=disable_exit, daemon=True).start()

def main():
    """Funkcja główna"""
    root = tk.Tk()
    app = TailscaleGUI(root)
    
    # Ustawienia okna
    root.minsize(600, 500)
    
    # Ikona okna (jeśli dostępna)
    try:
        root.iconname("Tailscale GUI")
    except:
        pass
        
    # Uruchomienie aplikacji
    root.mainloop()

if __name__ == "__main__":
    main()