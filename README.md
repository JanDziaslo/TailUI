# Tailscale GUI (PySide6)

Lekka aplikacja desktopowa (Linux) zapewniająca podstawowe sterowanie Tailscale:

Funkcje:
- Włączanie / wyłączanie połączenia (`tailscale up` / `tailscale down`)
- Sekcja exit node z przełącznikiem i przyciskiem „Zastosuj” do włączania/wyłączania wybranego węzła
- Lista urządzeń (nazwa, adresy Tailnet, status online, oznaczenie exit node)
- Podgląd lokalnych adresów Tailscale urządzenia
- Pobranie publicznego IP + podstawowe dane (org/ASN/miasto/kraj)
- Automatyczne okresowe odświeżanie (co 5s) + ciemny motyw
- Asynchroniczne pobieranie publicznego IP (bez blokowania interfejsu)

## Wymagania
- Python 3.10+ (testowane z 3.10/3.11)
- Zainstalowany klient `tailscale` w PATH (dla pełnej funkcjonalności)
- Biblioteki z `requirements.txt`

## Instalacja z pakietu DEB

Najnowsze pakiety DEB są dostępne w [Releases](https://github.com/JanDziaslo/tailscale-GUI/releases).

```bash
# Pobierz najnowszy pakiet DEB z releases
wget https://github.com/JanDziaslo/tailscale-GUI/releases/latest/download/tailscale-gui_*.deb

# Zainstaluj pakiet
sudo dpkg -i tailscale-gui_*.deb

# Jeśli wystąpią problemy z zależnościami, napraw je:
sudo apt-get install -f

# Uruchom aplikację
tailscale-gui
```

Po instalacji aplikacja będzie dostępna w menu aplikacji jako "Tailscale GUI".

## Instalacja z kodu źródłowego
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Jeżeli `tailscale` nie jest w PATH, aplikacja uruchomi się w trybie tylko-podgląd (bez możliwości sterowania).

## Pakowanie (PyInstaller – opcjonalnie)
```bash
pip install pyinstaller
pyinstaller --name tailscale-gui --onefile main.py
```
Binarka pojawi się w `dist/`.

## .desktop (skrót aplikacji – przykład)
Utwórz plik `~/.local/share/applications/tailscale-gui.desktop`:
```
[Desktop Entry]
Type=Application
Name=Tailscale GUI
Exec=/absolute/path/to/.venv/bin/python /absolute/path/to/main.py
Icon=utilities-terminal
Terminal=false
Categories=Network;
```
Następnie:
```bash
update-desktop-database ~/.local/share/applications || true
```

## Testy
```bash
python -m pytest -q
```

## Struktura
- `tailscale_client.py` – interakcja z CLI tailscale
- `ip_info.py` – pobieranie publicznego IP z kilku źródeł + cache
- `gui.py` – logika i interfejs PySide6
- `main.py` – punkt wejścia

## Uwagi dot. bezpieczeństwa
Aplikacja wywołuje polecenia systemowe `tailscale` poprzez `subprocess`. Nie interpoluje wejścia użytkownika w poleceniach (poza nazwą exit node pobraną z listy zwracanej przez tailscale), co minimalizuje ryzyko injection.

## Rozszerzenia (pomysły na przyszłość)
- Ikona w zasobniku systemowym (System Tray)
- Ręczne odświeżanie + wskaźnik czasu ostatniego odświeżenia
- Filtrowanie / wyszukiwanie urządzeń
- Kopiowanie adresów IP do schowka
- Tryb kompaktowy (mini-window)
- Wsparcie dla Windows / macOS

## Licencja
MIT License - zobacz plik [LICENSE](LICENSE) dla pełnych szczegółów.

