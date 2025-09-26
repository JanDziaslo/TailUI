#!/bin/bash

# Skrypt do tworzenia pakietu .deb dla Tailscale GUI
# Autor: Automatycznie wygenerowany skrypt

set -e

# Kolory dla outputu
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Tworzenie pakietu .deb dla Tailscale GUI ===${NC}"

# Sprawdź czy jesteśmy w katalogu projektu
if [ ! -f "main.py" ] || [ ! -f "requirements.txt" ]; then
    echo -e "${RED}Błąd: Uruchom skrypt w katalogu głównym projektu (gdzie znajduje się main.py)${NC}"
    exit 1
fi

# Pobranie wersji z pliku lub ustawienie domyślnej
VERSION="1.0.0"
PACKAGE_NAME="tailscale-gui"
MAINTAINER="Jan Dziasło <jan@example.com>"

echo -e "${YELLOW}Wersja pakietu: $VERSION${NC}"

# Stworzenie tymczasowego katalogu dla pakietu
BUILD_DIR="${PACKAGE_NAME}_${VERSION}_all"
echo -e "${YELLOW}Tworzenie struktury katalogów w $BUILD_DIR${NC}"

# Usuń stary katalog jeśli istnieje
rm -rf "$BUILD_DIR"

# Stwórz strukturę katalogów
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/bin"
mkdir -p "$BUILD_DIR/usr/share/applications"
mkdir -p "$BUILD_DIR/usr/share/icons/hicolor/48x48/apps"
mkdir -p "$BUILD_DIR/usr/share/icons/hicolor/scalable/apps"
mkdir -p "$BUILD_DIR/usr/share/$PACKAGE_NAME"

# Stwórz plik control
echo -e "${YELLOW}Tworzenie pliku control${NC}"
cat > "$BUILD_DIR/DEBIAN/control" << EOF
Package: $PACKAGE_NAME
Version: $VERSION
Section: net
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-pyside6.qtcore, python3-pyside6.qtwidgets, python3-pyside6.qtgui, python3-requests, tailscale, python3-pkg-resources
Recommends: python3-pyside6.qtnetwork
Maintainer: $MAINTAINER
Description: Graficzny interfejs użytkownika dla Tailscale
 Lekka aplikacja desktopowa (Linux) zapewniająca podstawowe sterowanie
 Tailscale z następującymi funkcjami:
  * Włączanie/wyłączanie połączenia Tailscale
  * Zarządzanie exit nodes z przełącznikiem
  * Lista urządzeń z statusem online
  * Podgląd lokalnych i publicznych adresów IP
  * Automatyczne odświeżanie co 5 sekund
  * Ikona w zasobniku systemowym
  * Kopiowanie adresów IP do schowka
  * Ciemny motyw interfejsu
Homepage: https://github.com/JanDziaslo/tailscale-GUI
EOF

# Stwórz plik copyright
echo -e "${YELLOW}Tworzenie pliku copyright${NC}"
mkdir -p "$BUILD_DIR/usr/share/doc/$PACKAGE_NAME"
cat > "$BUILD_DIR/usr/share/doc/$PACKAGE_NAME/copyright" << EOF
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Source: https://github.com/JanDziaslo/tailscale-GUI

Files: *
Copyright: 2025 Jan Dziasło
License: MIT
 Permission is hereby granted, free of charge, to any person obtaining a
 copy of this software and associated documentation files (the "Software"),
 to deal in the Software without restriction, including without limitation
 the rights to use, copy, modify, merge, publish, distribute, sublicense,
 and/or sell copies of the Software, and to permit persons to whom the
 Software is furnished to do so, subject to the following conditions:
 .
 The above copyright notice and this permission notice shall be included
 in all copies or substantial portions of the Software.
 .
 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
 OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
 THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
 DEALINGS IN THE SOFTWARE.
EOF

# Stwórz skrypt postinst
echo -e "${YELLOW}Tworzenie skryptu postinst${NC}"
cat > "$BUILD_DIR/DEBIAN/postinst" << 'EOF'
#!/bin/bash
set -e

# Nadanie uprawnień do wykonania
chmod +x /usr/bin/tailscale-gui

# Aktualizacja bazy danych aplikacji desktop
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications || true
fi

# Aktualizacja cache ikon
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q /usr/share/icons/hicolor || true
fi

echo "Tailscale GUI został zainstalowany."
echo "Możesz uruchomić aplikację przez menu aplikacji lub poleceniem: tailscale-gui"

exit 0
EOF

# Stwórz skrypt prerm
echo -e "${YELLOW}Tworzenie skryptu prerm${NC}"
cat > "$BUILD_DIR/DEBIAN/prerm" << 'EOF'
#!/bin/bash
set -e

echo "Usuwanie Tailscale GUI..."

exit 0
EOF

# Stwórz skrypt postrm
echo -e "${YELLOW}Tworzenie skryptu postrm${NC}"
cat > "$BUILD_DIR/DEBIAN/postrm" << 'EOF'
#!/bin/bash
set -e

# Aktualizacja bazy danych aplikacji desktop
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications || true
fi

# Aktualizacja cache ikon
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q /usr/share/icons/hicolor || true
fi

exit 0
EOF

# Nadanie uprawnień skryptom
chmod 755 "$BUILD_DIR/DEBIAN/postinst"
chmod 755 "$BUILD_DIR/DEBIAN/prerm" 
chmod 755 "$BUILD_DIR/DEBIAN/postrm"

# Stwórz skrypt uruchamiający
echo -e "${YELLOW}Tworzenie skryptu uruchamiającego${NC}"
cat > "$BUILD_DIR/usr/bin/tailscale-gui" << EOF
#!/bin/bash
# Skrypt uruchamiający dla Tailscale GUI

# Przejdź do katalogu z aplikacją
cd /usr/share/$PACKAGE_NAME

# Uruchom aplikację
exec python3 main.py "\$@"
EOF

# Nadanie uprawnień do wykonania
chmod 755 "$BUILD_DIR/usr/bin/tailscale-gui"

# Stwórz plik .desktop
echo -e "${YELLOW}Tworzenie pliku .desktop${NC}"
cat > "$BUILD_DIR/usr/share/applications/$PACKAGE_NAME.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Tailscale GUI
Comment=Graficzny interfejs użytkownika dla Tailscale
Comment[en]=Graphical user interface for Tailscale
GenericName=Network Management
GenericName[pl]=Zarządzanie siecią
Exec=tailscale-gui
Icon=tailscale-gui
Terminal=false
Categories=Network;System;
StartupNotify=true
Keywords=tailscale;vpn;network;mesh;
Keywords[pl]=tailscale;vpn;sieć;
EOF

# Obsługa ikon - PNG dla menu systemowego i SVG dla aplikacji
echo -e "${YELLOW}Sprawdzanie ikon aplikacji${NC}"

# 1. Obsługa ikony PNG dla menu systemowego
PNG_ICON_FOUND=false
if [ -f "assets_icon_tailscale.png" ]; then
    echo -e "${GREEN}Znaleziono ikonę PNG: assets_icon_tailscale.png${NC}"
    PNG_ICON_FOUND=true

    # Skopiuj ikonę do właściwego katalogu systemowego
    cp "assets_icon_tailscale.png" "$BUILD_DIR/usr/share/icons/hicolor/48x48/apps/$PACKAGE_NAME.png"

    # Sprawdź czy ikona wymaga zmiany rozmiaru
    if command -v identify >/dev/null 2>&1; then
        SIZE=$(identify -format "%wx%h" "assets_icon_tailscale.png" 2>/dev/null || echo "unknown")
        if [ "$SIZE" != "48x48" ] && [ "$SIZE" != "unknown" ]; then
            echo -e "${YELLOW}Ikona PNG ma rozmiar $SIZE, przeskalowuję do 48x48${NC}"
            if command -v convert >/dev/null 2>&1; then
                convert "assets_icon_tailscale.png" -resize 48x48 "$BUILD_DIR/usr/share/icons/hicolor/48x48/apps/$PACKAGE_NAME.png"
            else
                echo -e "${YELLOW}ImageMagick nie jest dostępny - używam ikony w oryginalnym rozmiarze${NC}"
            fi
        else
            echo -e "${GREEN}Ikona PNG ma właściwy rozmiar (48x48)${NC}"
        fi
    fi
else
    echo -e "${YELLOW}Brak ikony PNG: assets_icon_tailscale.png${NC}"
fi

# 2. Obsługa ikony SVG dla aplikacji i systemu
SVG_ICON_FOUND=false
if [ -f "assets_icon_tailscale.svg" ]; then
    echo -e "${GREEN}Znaleziono ikonę SVG: assets_icon_tailscale.svg${NC}"
    SVG_ICON_FOUND=true

    # Skopiuj ikonę SVG do katalogu aplikacji (dla użycia przez program)
    cp "assets_icon_tailscale.svg" "$BUILD_DIR/usr/share/$PACKAGE_NAME/"
    echo -e "${GREEN}Ikona SVG skopiowana do katalogu aplikacji${NC}"

    # Skopiuj ikonę SVG również do katalogu systemowego ikon
    cp "assets_icon_tailscale.svg" "$BUILD_DIR/usr/share/icons/hicolor/scalable/apps/$PACKAGE_NAME.svg"
    echo -e "${GREEN}Ikona SVG skopiowana do katalogu systemowego${NC}"
else
    echo -e "${YELLOW}Brak ikony SVG: assets_icon_tailscale.svg${NC}"
fi

# 3. Fallback - stwórz podstawową ikonę jeśli nie ma żadnej
if [ "$PNG_ICON_FOUND" = false ] && [ "$SVG_ICON_FOUND" = false ]; then
    echo -e "${YELLOW}Brak ikon - tworzenie podstawowej ikony PNG${NC}"
    if command -v convert >/dev/null 2>&1; then
        convert -size 48x48 xc:transparent -fill "#4285f4" -draw "roundrectangle 8,8 40,40 8,8" -pointsize 20 -fill white -gravity center -annotate +0+0 "T" "$BUILD_DIR/usr/share/icons/hicolor/48x48/apps/$PACKAGE_NAME.png"
        echo -e "${GREEN}Utworzono podstawową ikonę PNG${NC}"
    else
        echo -e "${YELLOW}ImageMagick nie jest zainstalowany - pomijam tworzenie ikony${NC}"
        # Usuń referencję do ikony z .desktop
        sed -i '/^Icon=/d' "$BUILD_DIR/usr/share/applications/$PACKAGE_NAME.desktop"
    fi
elif [ "$PNG_ICON_FOUND" = false ] && [ "$SVG_ICON_FOUND" = true ]; then
    echo -e "${YELLOW}Brak ikony PNG - tworzenie PNG z SVG${NC}"
    if command -v convert >/dev/null 2>&1; then
        convert -size 48x48 "assets_icon_tailscale.svg" "$BUILD_DIR/usr/share/icons/hicolor/48x48/apps/$PACKAGE_NAME.png"
        echo -e "${GREEN}Utworzono ikonę PNG z SVG${NC}"
    else
        echo -e "${YELLOW}ImageMagick nie jest dostępny - PNG pozostanie brakujące${NC}"
    fi
fi

# Skopiuj pliki aplikacji
echo -e "${YELLOW}Kopiowanie plików aplikacji${NC}"
cp main.py "$BUILD_DIR/usr/share/$PACKAGE_NAME/"
cp tailscale_client.py "$BUILD_DIR/usr/share/$PACKAGE_NAME/"
cp ip_info.py "$BUILD_DIR/usr/share/$PACKAGE_NAME/"
cp gui.py "$BUILD_DIR/usr/share/$PACKAGE_NAME/"

# Skopiuj requirements.txt dla referencji
if [ -f "requirements.txt" ]; then
    cp requirements.txt "$BUILD_DIR/usr/share/$PACKAGE_NAME/"
    echo -e "${GREEN}Skopiowano requirements.txt${NC}"
fi

# Skopiuj README jeśli istnieje
if [ -f "README.md" ]; then
    cp README.md "$BUILD_DIR/usr/share/doc/$PACKAGE_NAME/"
    echo -e "${GREEN}Skopiowano README.md${NC}"
fi

# Sprawdź czy są inne pliki zasobów które mogą być potrzebne
echo -e "${YELLOW}Sprawdzanie dodatkowych plików zasobów${NC}"
for resource_file in *.css *.qss *.json *.txt *.conf; do
    if [ -f "$resource_file" ] && [ "$resource_file" != "requirements.txt" ]; then
        cp "$resource_file" "$BUILD_DIR/usr/share/$PACKAGE_NAME/"
        echo -e "${GREEN}Skopiowano zasób: $resource_file${NC}"
    fi
done

# Sprawdź zależności (poprawiona wersja)
echo -e "${YELLOW}Sprawdzanie dostępności zależności w systemie${NC}"
MISSING_DEPS=""

for dep in python3-pyside6.qtcore python3-pyside6.qtwidgets python3-pyside6.qtgui python3-requests tailscale; do
    if [ "$dep" = "tailscale" ]; then
        if ! command -v tailscale >/dev/null 2>&1; then
            MISSING_DEPS="$MISSING_DEPS $dep"
        fi
    else
        # Użyj dpkg -s zamiast dpkg -l | grep dla większej niezawodności
        if ! dpkg -s "$dep" >/dev/null 2>&1; then
            MISSING_DEPS="$MISSING_DEPS $dep"
        fi
    fi
done

if [ ! -z "$MISSING_DEPS" ]; then
    echo -e "${YELLOW}Uwaga: Następujące zależności nie są zainstalowane w systemie:${NC}"
    echo -e "${YELLOW}$MISSING_DEPS${NC}"
    echo -e "${YELLOW}Pakiet zostanie zbudowany, ale może wymagać instalacji tych zależności przez apt install -f${NC}"
fi

# Oblicz rozmiar pakietu
INSTALLED_SIZE=$(du -sk "$BUILD_DIR" | cut -f1)
echo "Installed-Size: $INSTALLED_SIZE" >> "$BUILD_DIR/DEBIAN/control"

# Zbuduj pakiet z fakeroot dla poprawnych uprawnień
echo -e "${YELLOW}Budowanie pakietu .deb${NC}"
if command -v fakeroot >/dev/null 2>&1; then
    echo -e "${GREEN}Używam fakeroot dla poprawnych uprawnień plików${NC}"
    fakeroot dpkg-deb --build "$BUILD_DIR"
else
    echo -e "${YELLOW}fakeroot nie jest dostępny - budowanie bez niego${NC}"
    dpkg-deb --build "$BUILD_DIR"
fi

# Sprawdź pakiet
echo -e "${YELLOW}Sprawdzanie pakietu${NC}"
if command -v lintian >/dev/null 2>&1; then
    lintian "${BUILD_DIR}.deb" || echo -e "${YELLOW}Lintian znalazł pewne ostrzeżenia (to normalne)${NC}"
fi

echo -e "${GREEN}=== Pakiet został utworzony pomyślnie ===${NC}"
echo -e "${GREEN}Plik: ${BUILD_DIR}.deb${NC}"
echo ""
echo -e "${BLUE}Zawartość pakietu - ikony:${NC}"
if [ "$PNG_ICON_FOUND" = true ]; then
    echo -e "  ✅ PNG: /usr/share/icons/hicolor/48x48/apps/$PACKAGE_NAME.png"
fi
if [ "$SVG_ICON_FOUND" = true ]; then
    echo -e "  ✅ SVG (aplikacja): /usr/share/$PACKAGE_NAME/assets_icon_tailscale.svg"
    echo -e "  ✅ SVG (system): /usr/share/icons/hicolor/scalable/apps/$PACKAGE_NAME.svg"
fi
echo ""
echo -e "${BLUE}Aby zainstalować pakiet:${NC}"
echo "  sudo dpkg -i ${BUILD_DIR}.deb"
echo "  sudo apt install -f  # Zainstaluj brakujące zależności"
echo ""
echo -e "${BLUE}Aby sprawdzić zawartość pakietu:${NC}"
echo "  dpkg -c ${BUILD_DIR}.deb"
echo ""
echo -e "${BLUE}Aby uzyskać informacje o pakiecie:${NC}"
echo "  dpkg -I ${BUILD_DIR}.deb"
echo ""

# Opcjonalnie usuń katalog tymczasowy
read -p "Czy chcesz usunąć tymczasowy katalog budowania? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$BUILD_DIR"
    echo -e "${GREEN}Katalog tymczasowy został usunięty.${NC}"
fi

echo -e "${GREEN}Gotowe!${NC}"
