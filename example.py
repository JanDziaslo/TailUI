#!/usr/bin/env python3
"""
Przykład użycia modułu Tailscale GUI
Demonstracja jak używać komponentów programowo
"""

from tailscale_gui import TailscaleGUI
import tkinter as tk

def example_usage():
    """Przykład programowego użycia"""
    root = tk.Tk()
    app = TailscaleGUI(root)
    
    # Przykład: Automatyczne odświeżanie co 30 sekund
    def auto_refresh():
        app.refresh_status()
        root.after(30000, auto_refresh)  # 30 sekund
    
    # Uruchom auto-odświeżanie
    auto_refresh()
    
    # Przykład: Dodanie własnego menu
    menubar = tk.Menu(root)
    root.config(menu=menubar)
    
    # Menu Plik
    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Plik", menu=file_menu)
    file_menu.add_command(label="Odśwież", command=app.refresh_status)
    file_menu.add_separator()
    file_menu.add_command(label="Zakończ", command=root.quit)
    
    # Menu Pomoc
    help_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Pomoc", menu=help_menu)
    help_menu.add_command(label="O programie", command=show_about)
    
    def show_about():
        about_window = tk.Toplevel(root)
        about_window.title("O programie")
        about_window.geometry("400x300")
        about_window.resizable(False, False)
        
        tk.Label(about_window, text="Tailscale GUI Manager", 
                font=("Arial", 16, "bold")).pack(pady=10)
        tk.Label(about_window, text="Wersja 1.0").pack()
        tk.Label(about_window, text="Autor: JanDziaslo").pack()
        tk.Label(about_window, text="GitHub: github.com/JanDziaslo/tailscale-GUI").pack()
        
        tk.Button(about_window, text="Zamknij", 
                 command=about_window.destroy).pack(pady=20)
    
    return app, root

if __name__ == "__main__":
    app, root = example_usage()
    root.mainloop()