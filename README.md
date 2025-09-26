# Tailscale GUI (PySide6)

> 🇵🇱 Lekka aplikacja desktopowa dla Linuksa, oferująca pełne sterowanie Tailscale z poziomu graficznego interfejsu.
>
> 🇬🇧 Lightweight Linux desktop app that brings Tailscale controls into a friendly PySide6 GUI.

## 🇵🇱 Informacje po polsku

### Funkcje
- Włączanie i wyłączanie Tailscale (`tailscale up` / `tailscale down`) z bieżącym statusem backendu.
- Ręczny przycisk „Odśwież” oraz automatyczne odpytywanie co 5 s z dodatkowym przyspieszeniem po interakcji użytkownika.
- Zarządzanie exit node: lista węzłów, przełącznik aktywacji, przycisk „Zastosuj”, wykrywanie aliasów urządzeń oraz automatyczna próba z `sudo`, gdy wymaga tego system.
- Lista urządzeń Tailnet (nazwa, system operacyjny, status online, rola exit), kontekstowe menu i podwójne kliknięcie do szybkiego kopiowania adresów.
- Podgląd własnych adresów Tailnet (oddzielnie IPv4/IPv6) oraz przyciski kopiowania wybranych wartości.
- Pobieranie publicznego IP wraz z informacjami o organizacji, ASN i lokalizacji z kilku źródeł (ipinfo, ipapi, ifconfig) i cache’owaniem wyników.
- Ikona w zasobniku systemowym z akcjami (pokaż/ukryj okno, połącz, rozłącz, zakończ) i komunikatem o pracy w tle.
- Ciemny motyw, skalowanie interfejsu, dezaktywacja elementów podczas operacji oraz obsługa schowka dla wszystkich kopiowanych danych.
- Tryb tylko podgląd (gdy `tailscale` nie jest dostępny) – aplikacja nadal pokazuje informacje, ale blokuje operacje sterujące.

### Wymagania
- Python 3.10+ (testowane z 3.10/3.11).
- Zainstalowana binarka `tailscale` w `PATH` dla pełnego sterowania (opcjonalna dla trybu tylko podgląd).
- Biblioteki z `requirements.txt` (`PySide6`, `requests`, zależności testowe `pytest`).

### Instalacja i uruchomienie
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Jeśli `tailscale` nie znajduje się w `PATH`, interfejs przełączy się w tryb tylko podgląd (brak możliwości połączenia/rozłączenia czy zmiany exit node).

### Pakowanie
- **PyInstaller (pojedyncza binarka):**
	```bash
	pip install pyinstaller
	pyinstaller --name tailscale-gui --onefile main.py
	```
	Wynik znajduje się w katalogu `dist/`.
- **Pakiet .deb:** skorzystaj ze skryptu `build_deb.sh` (wymaga `fakeroot`, `dpkg-deb`, opcjonalnie `lintian`).
	```bash
	chmod +x build_deb.sh
	./build_deb.sh
	```
	Gotowy pakiet pojawi się jako `tailscale-gui_1.0.0_all.deb` w katalogu projektu.

### Testy
```bash
python -m pytest -q
```

### Struktura projektu
- `main.py` – punkt wejścia (uruchamia `gui.run()`).
- `gui.py` – główne okno PySide6, logika UI, zasobnik systemowy, zarządzanie danymi.
- `tailscale_client.py` – integracja z CLI `tailscale`, parsowanie JSON, obsługa exit node.
- `ip_info.py` – asynchroniczny fetcher publicznego IP z cache.
- `build_deb.sh` – skrypt budujący pakiet Debiana.
- `requirements.txt`, `VERSION`, `CHANGELOG.md`, `LICENSE`, testy jednostkowe (`test_*.py`).

### Uwagi dotyczące bezpieczeństwa
- Operacje wykonywane są przez `subprocess.run` na poleceniach `tailscale`; dane wejściowe pochodzą z zaufanych źródeł (`tailscale status`).
- Przy zmianie exit node aplikacja próbuje ponownie z `sudo` tylko wtedy, gdy wykryje błąd uprawnień.
- Aplikacja nie przechowuje poświadczeń – korzysta wyłącznie z przypisanego do użytkownika CLI.

### Pomysły na przyszłość
- Filtrowanie i wyszukiwarka urządzeń w widoku listy.
- Tryb kompaktowy (mini okno lub widżet zasobnika).
- Obsługa powiadomień systemowych o zmianie stanu połączenia.
- Port na Windows i macOS (aktualnie wsparcie testowane tylko na Linuksie).

### Licencja
Projekt jest objęty licencją MIT – szczegóły w pliku `LICENSE`.

---

## 🇬🇧 Information in English

### Features
- Toggle Tailscale on/off via `tailscale up` / `tailscale down` and display the backend state in real time.
- Manual **Refresh** button plus automatic polling every 5 seconds, with extra refreshes when the user interacts with the window.
- Exit node management: device list, enable/disable switch, **Apply** button, alias detection, and an optional `sudo` retry when permissions are required.
- Tailnet device overview (name, OS, online state, exit status) with context menu actions and double-click shortcuts for copying addresses.
- Local Tailnet addresses grouped by IPv4/IPv6 with dedicated copy buttons and clear status bar feedback.
- Public IP lookup (organization, ASN, location) via multiple providers (ipinfo, ipapi, ifconfig) with caching to avoid rate limits.
- System tray icon with quick actions (show/hide window, connect, disconnect, quit) and a notification that the app keeps running in the background.
- Dark theme, responsive widgets, disabled controls while operations are in flight, and clipboard integration for every copy action.
- Read-only mode kicks in automatically when the `tailscale` binary is missing, letting you inspect data without mutating state.

### Requirements
- Python 3.10 or newer (validated with 3.10/3.11).
- `tailscale` binary available in `PATH` for full control (optional for read-only mode).
- Dependencies from `requirements.txt` (`PySide6`, `requests`, optional dev/test extras like `pytest`).

### Installation & Run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

When `tailscale` is not detected, the GUI disables all mutating actions and behaves as an observer only.

### Packaging
- **PyInstaller (single executable):**
	```bash
	pip install pyinstaller
	pyinstaller --name tailscale-gui --onefile main.py
	```
	The binary will land in `dist/`.
- **Debian package:** use the `build_deb.sh` helper (requires `fakeroot`, `dpkg-deb`, optionally `lintian`).
	```bash
	chmod +x build_deb.sh
	./build_deb.sh
	```
	The resulting artifact is `tailscale-gui_1.0.0_all.deb` in the project root.

### Tests
```bash
python -m pytest -q
```

### Project layout
- `main.py` – entry point (boots `gui.run()`).
- `gui.py` – PySide6 window, tray icon, copy helpers, status polling, exit node logic.
- `tailscale_client.py` – wrapper around the `tailscale` CLI, JSON parsing, exit node helpers with optional sudo retry.
- `ip_info.py` – public IP fetcher with multi-endpoint fallback and TTL cache.
- `build_deb.sh` – Debian packaging script.
- Ancillary files: `requirements.txt`, `VERSION`, `CHANGELOG.md`, `LICENSE`, and pytest suites (`test_*.py`).

### Security notes
- Interactions with `tailscale` happen via `subprocess.run`; user input is not interpolated into shell strings.
- Exit node changes only retry with `sudo` when the CLI reports a permission error.
- Secrets are not stored; the app relies on your existing Tailscale authentication.

### Future ideas
- Device search/filtering within the tree view.
- Compact / mini window layout for quick status checks.
- Native desktop notifications on status changes.
- Cross-platform support (Windows/macOS) once UI and packaging are adapted.

### License
Distributed under the MIT License – see `LICENSE` for details.

