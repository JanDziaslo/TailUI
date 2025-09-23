#!/bin/bash

# Tailscale GUI Launcher - PyQt6 Version
# Sprawdza wymagania i uruchamia aplikację

echo "=== Tailscale GUI Launcher (PyQt6) ==="

# Sprawdź czy Python jest zainstalowany
if ! command -v python3 &> /dev/null; then
    echo "❌ Błąd: Python 3 nie jest zainstalowany"
    exit 1
fi

echo "✅ Python 3 znaleziony"

# Sprawdź czy Tailscale jest zainstalowany
if ! command -v tailscale &> /dev/null; then
    echo "❌ Błąd: Tailscale nie jest zainstalowany"
    echo "📥 Zainstaluj Tailscale z: https://tailscale.com/download"
    echo "  Ubuntu/Debian: sudo apt install tailscale"
    echo "  Fedora: sudo dnf install tailscale"
    echo "  macOS: brew install tailscale"
    exit 1
fi

echo "✅ Tailscale znaleziony"

# Sprawdź czy PyQt6 jest dostępny
python3 -c "import PyQt6.QtWidgets" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Błąd: PyQt6 nie jest zainstalowany"
    echo "📦 Zainstaluj PyQt6:"
    echo "  pip install PyQt6"
    echo "  Ubuntu/Debian: sudo apt install python3-pyqt6"
    echo "  Fedora: sudo dnf install python3-qt6"
    exit 1
fi

echo "✅ PyQt6 znaleziony"

# Sprawdź opcjonalnie starą wersję
if [ -f "tailscale_gui.py" ]; then
    echo "ℹ️  Znaleziono starą wersję (tkinter): tailscale_gui.py"
fi

echo "🚀 Uruchamianie nowoczesnej aplikacji PyQt6..."
python3 tailscale_gui_qt.py