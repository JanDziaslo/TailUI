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
- Ikona w zasobniku systemowym z szybkim menu (pokaż/ukryj, połącz, rozłącz, zakończ)
- Kopiowanie adresów IP do schowka (lokalne IPv4/IPv6 osobno, publiczne, urządzenia z listy – wszystkie/IPv4/IPv6)

## Wymagania
- Python 3.10+ (testowane z 3.10/3.11)
- Zainstalowany klient `tailscale` w PATH (dla pełnej funkcjonalności)
- Biblioteki z `requirements.txt`

## Instalacja
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
- Ręczne odświeżanie + wskaźnik czasu ostatniego odświeżenia
- Filtrowanie / wyszukiwanie urządzeń
- Tryb kompaktowy (mini-window)
- Wsparcie dla Windows / macOS

## Licencja
Możesz swobodnie używać i modyfikować (dodaj własną licencję jeśli potrzebujesz formalizacji).

