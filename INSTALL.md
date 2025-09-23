# Instalacja i konfiguracja systemowa

## Automatyczne uruchamianie przy starcie systemu

### systemd (Linux)

1. Utwórz plik usługi:
```bash
sudo nano /etc/systemd/user/tailscale-gui.service
```

2. Dodaj zawartość:
```ini
[Unit]
Description=Tailscale GUI Manager
After=graphical-session.target
Wants=graphical-session.target

[Service]
Type=simple
Environment=DISPLAY=:0
ExecStart=/usr/bin/python3 /path/to/tailscale-GUI/tailscale_gui.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

3. Włącz usługę:
```bash
systemctl --user enable tailscale-gui.service
systemctl --user start tailscale-gui.service
```

### Desktop Entry (Linux)

1. Utwórz plik .desktop:
```bash
nano ~/.local/share/applications/tailscale-gui.desktop
```

2. Dodaj zawartość:
```ini
[Desktop Entry]
Version=1.0
Type=Application
Name=Tailscale GUI
Comment=Graficzny interfejs do zarządzania Tailscale
Exec=/path/to/tailscale-GUI/run.sh
Icon=network-vpn
Terminal=false
Categories=Network;System;
```

3. Zaktualizuj bazę aplikacji:
```bash
update-desktop-database ~/.local/share/applications/
```

## Ustawienia uprawnień

### Dodanie użytkownika do grupy tailscale
```bash
sudo usermod -a -G tailscale $USER
```

### Konfiguracja sudo dla Tailscale (opcjonalnie)
```bash
sudo visudo
```

Dodaj linię:
```
%tailscale ALL=(ALL) NOPASSWD: /usr/bin/tailscale
```

## Instalacja globalna

### Kopiowanie do /usr/local/bin
```bash
sudo cp tailscale_gui.py /usr/local/bin/
sudo chmod +x /usr/local/bin/tailscale_gui.py
```

### Tworzenie symlinka
```bash
sudo ln -s /path/to/tailscale-GUI/tailscale_gui.py /usr/local/bin/tailscale-gui
```

## Konfiguracja środowiska wirtualnego

```bash
# Utwórz venv
python3 -m venv tailscale-gui-env

# Aktywuj
source tailscale-gui-env/bin/activate

# Uruchom aplikację
python tailscale_gui.py
```

## Konfiguracja dla różnych dystrybucji

### Ubuntu/Debian
```bash
sudo apt update
sudo apt install python3-tk tailscale
```

### Fedora
```bash
sudo dnf install python3-tkinter tailscale
```

### Arch Linux
```bash
sudo pacman -S tk tailscale
```

### macOS
```bash
brew install python-tk tailscale
```

## Rozwiązywanie problemów uprawnień

### SELinux (RedHat/Fedora)
```bash
# Sprawdź status SELinux
sestatus

# Jeśli włączony, możesz potrzebować:
sudo setsebool -P allow_user_exec_content on
```

### AppArmor (Ubuntu)
Sprawdź profil Tailscale:
```bash
sudo aa-status | grep tailscale
```

## Konfiguracja dla serwerów (headless)

### X11 Forwarding
```bash
ssh -X user@server
```

### VNC
```bash
# Zainstaluj VNC server na zdalnej maszynie
sudo apt install tightvncserver

# Uruchom VNC
vncserver :1

# Połącz się z klienta VNC
```

## Backup konfiguracji

### Eksport ustawień Tailscale
```bash
# Backup klucza autoryzacji
sudo tailscale file get /var/lib/tailscale/

# Lista urządzeń
tailscale status --json > tailscale_status_backup.json
```

### Przywracanie
```bash
# Po ponownej instalacji użyj tego samego klucza autoryzacji
tailscale up --authkey=tskey-auth-...
```