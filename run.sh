#!/bin/bash

# Tailscale GUI Launcher
# Sprawdza wymagania i uruchamia aplikację

echo "=== Tailscale GUI Launcher ==="

# Sprawdź czy Python jest zainstalowany
if ! command -v python3 &> /dev/null; then
    echo "Błąd: Python 3 nie jest zainstalowany"
    exit 1
fi

# Sprawdź czy Tailscale jest zainstalowany
if ! command -v tailscale &> /dev/null; then
    echo "Błąd: Tailscale nie jest zainstalowany"
    echo "Zainstaluj Tailscale z: https://tailscale.com/download"
    echo "Ubuntu/Debian: sudo apt install tailscale"
    echo "macOS: brew install tailscale"
    exit 1
fi

# Sprawdź czy tkinter jest dostępny
python3 -c "import tkinter" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Błąd: tkinter nie jest dostępny"
    echo "Ubuntu/Debian: sudo apt install python3-tk"
    echo "Fedora: sudo dnf install tkinter"
    exit 1
fi

echo "Wszystkie wymagania spełnione. Uruchamianie aplikacji..."
python3 tailscale_gui.py