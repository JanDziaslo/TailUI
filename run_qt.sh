#!/bin/bash

# Quick launcher dla PyQt6 version
# Bezpośredni start nowoczesnej aplikacji

echo "🚀 Tailscale GUI (PyQt6) - Quick Start"

# Sprawdź podstawowe wymagania
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 nie jest zainstalowany"
    exit 1
fi

if ! python3 -c "import PyQt6.QtWidgets" 2>/dev/null; then
    echo "❌ PyQt6 nie jest zainstalowany"
    echo "💿 Zainstaluj: pip install PyQt6"
    exit 1
fi

if ! command -v tailscale &> /dev/null; then
    echo "❌ Tailscale nie jest zainstalowany"
    echo "📥 Pobierz z: https://tailscale.com/download"
    exit 1
fi

# Uruchom aplikację
echo "✨ Uruchamianie nowoczesnego interfejsu..."
python3 tailscale_gui_qt.py