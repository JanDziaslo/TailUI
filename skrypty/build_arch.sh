#!/bin/bash

# Skrypt do tworzenia pakietu .pkg.tar.zst dla TailUI (nieoficjalny interfejs Tailscale)
# Dla Arch Linux i pochodnych (Manjaro, EndeavourOS, etc.)

set -e

# Kolory dla outputu
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Tworzenie pakietu Arch Linux dla TailUI ===${NC}"

# Sprawdź czy jesteśmy w katalogu projektu
if [ ! -f "main.py" ] || [ ! -f "requirements.txt" ]; then
    echo -e "${RED}Błąd: Uruchom skrypt w katalogu głównym projektu (gdzie znajduje się main.py)${NC}"
    exit 1
fi

# Sprawdź czy mamy dostępne narzędzia do budowania pakietów Arch
if ! command -v makepkg >/dev/null 2>&1; then
    echo -e "${RED}Błąd: makepkg nie jest dostępny. Ten skrypt działa tylko na Arch Linux lub pochodnych.${NC}"
    echo ""
    echo -e "${YELLOW}Jeśli używasz Debiana/Ubuntu/Kubuntu:${NC}"
    echo -e "  - Dla pakietów .deb: użyj ${GREEN}./skrypty/build_deb.sh${NC}"
    echo -e "  - Dla pakietów Arch (przez Docker): użyj ${GREEN}./skrypty/build_arch_docker.sh${NC}"
    echo ""
    exit 1
fi

# Pobranie wersji z pliku lub ustawienie domyślnej
VERSION="1.0.8"
PACKAGE_NAME="tailui"
MAINTAINER="Jan Dziasło i Ropucha"
PKGREL="1"

echo -e "${YELLOW}Wersja pakietu: $VERSION-$PKGREL${NC}"

# Stworzenie tymczasowego katalogu dla pakietu
BUILD_DIR="build_arch"
echo -e "${YELLOW}Tworzenie struktury katalogów w $BUILD_DIR${NC}"

# Usuń stary katalog jeśli istnieje
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Skopiuj pliki źródłowe do katalogu budowania
echo -e "${YELLOW}Przygotowywanie plików źródłowych${NC}"
cp main.py "$BUILD_DIR/"
cp tailscale_client.py "$BUILD_DIR/"
cp ip_info.py "$BUILD_DIR/"
cp gui.py "$BUILD_DIR/"
cp requirements.txt "$BUILD_DIR/"

# Skopiuj config.py jeśli istnieje
if [ -f "config.py" ]; then
    cp config.py "$BUILD_DIR/"
fi

# Skopiuj ikony jeśli istnieją
if [ -f "assets_icon_tailui.png" ]; then
    cp assets_icon_tailui.png "$BUILD_DIR/"
    echo -e "${GREEN}Skopiowano ikonę PNG${NC}"
fi

if [ -f "assets_icon_tailui.svg" ]; then
    cp assets_icon_tailui.svg "$BUILD_DIR/"
    echo -e "${GREEN}Skopiowano ikonę SVG${NC}"
fi

# Skopiuj README i LICENSE jeśli istnieją
if [ -f "README.md" ]; then
    cp README.md "$BUILD_DIR/"
fi

if [ -f "LICENSE" ]; then
    cp LICENSE "$BUILD_DIR/"
fi

# Stwórz plik .desktop
echo -e "${YELLOW}Tworzenie pliku .desktop${NC}"
cat > "$BUILD_DIR/tailui.desktop" << EOF
[Desktop Entry]
Type=Application
Name=TailUI
Comment=Nieoficjalny interfejs Tailscale
Comment[en]=Unofficial TailUI interface for Tailscale
GenericName=Network Management
GenericName[pl]=Zarządzanie siecią
Exec=tailui
Icon=tailui
Terminal=false
Categories=Network;System;
StartupNotify=true
Keywords=tailscale;vpn;network;mesh;
Keywords[pl]=tailscale;vpn;sieć;
EOF

# Oblicz sumy kontrolne plików
cd "$BUILD_DIR"
echo -e "${YELLOW}Obliczanie sum kontrolnych plików${NC}"

# Generuj tablicę sum MD5
MD5_SUMS=""
for file in *.py *.txt *.desktop *.png *.svg *.md LICENSE 2>/dev/null; do
    if [ -f "$file" ]; then
        SUM=$(md5sum "$file" | cut -d' ' -f1)
        MD5_SUMS="${MD5_SUMS}'${SUM}'\n            "
    fi
done
MD5_SUMS=$(echo -e "$MD5_SUMS" | sed '$ s/\\n *$//')

cd ..

# Stwórz PKGBUILD
echo -e "${YELLOW}Tworzenie pliku PKGBUILD${NC}"
cat > "$BUILD_DIR/PKGBUILD" << EOF
# Maintainer: $MAINTAINER
pkgname=$PACKAGE_NAME
pkgver=$VERSION
pkgrel=$PKGREL
pkgdesc='Nieoficjalny interfejs graficzny dla Tailscale'
arch=('any')
url='https://github.com/JanDziaslo/tailui'
license=('MIT')
depends=(
    'python>=3.10'
    'pyside6'
    'python-requests'
    'tailscale'
)
optdepends=()
source=(
    'main.py'
    'tailscale_client.py'
    'ip_info.py'
    'gui.py'
    'requirements.txt'
    'tailui.desktop'
    'config.py'
)

# Dodaj ikony do source jeśli istnieją
if [ -f "assets_icon_tailui.png" ]; then
    source+=('assets_icon_tailui.png')
fi

if [ -f "assets_icon_tailui.svg" ]; then
    source+=('assets_icon_tailui.svg')
fi

if [ -f "README.md" ]; then
    source+=('README.md')
fi

if [ -f "LICENSE" ]; then
    source+=('LICENSE')
fi

md5sums=(
    SKIP
    SKIP
    SKIP
    SKIP
    SKIP
    SKIP
    SKIP
)

# Dodaj SKIP dla ikon jeśli istnieją
if [ -f "assets_icon_tailui.png" ]; then
    md5sums+=('SKIP')
fi

if [ -f "assets_icon_tailui.svg" ]; then
    md5sums+=('SKIP')
fi

if [ -f "README.md" ]; then
    md5sums+=('SKIP')
fi

if [ -f "LICENSE" ]; then
    md5sums+=('SKIP')
fi

package() {
    # Utwórz katalogi
    install -dm755 "\${pkgdir}/usr/share/\${pkgname}"
    install -dm755 "\${pkgdir}/usr/bin"
    install -dm755 "\${pkgdir}/usr/share/applications"

    # Zainstaluj pliki aplikacji
    install -Dm644 main.py "\${pkgdir}/usr/share/\${pkgname}/main.py"
    install -Dm644 tailscale_client.py "\${pkgdir}/usr/share/\${pkgname}/tailscale_client.py"
    install -Dm644 ip_info.py "\${pkgdir}/usr/share/\${pkgname}/ip_info.py"
    install -Dm644 gui.py "\${pkgdir}/usr/share/\${pkgname}/gui.py"

    # Zainstaluj config.py jeśli istnieje
    if [ -f "config.py" ]; then
        install -Dm644 config.py "\${pkgdir}/usr/share/\${pkgname}/config.py"
    fi

    # Zainstaluj requirements.txt dla referencji
    if [ -f "requirements.txt" ]; then
        install -Dm644 requirements.txt "\${pkgdir}/usr/share/\${pkgname}/requirements.txt"
    fi

    # Zainstaluj ikony
    if [ -f "assets_icon_tailui.png" ]; then
        install -Dm644 assets_icon_tailui.png "\${pkgdir}/usr/share/\${pkgname}/assets_icon_tailui.png"
        install -Dm644 assets_icon_tailui.png "\${pkgdir}/usr/share/icons/hicolor/48x48/apps/\${pkgname}.png"
    fi

    if [ -f "assets_icon_tailui.svg" ]; then
        install -Dm644 assets_icon_tailui.svg "\${pkgdir}/usr/share/\${pkgname}/assets_icon_tailui.svg"
        install -Dm644 assets_icon_tailui.svg "\${pkgdir}/usr/share/icons/hicolor/scalable/apps/\${pkgname}.svg"
    fi

    # Zainstaluj plik .desktop
    install -Dm644 tailui.desktop "\${pkgdir}/usr/share/applications/\${pkgname}.desktop"

    # Zainstaluj dokumentację
    if [ -f "README.md" ]; then
        install -Dm644 README.md "\${pkgdir}/usr/share/doc/\${pkgname}/README.md"
    fi

    if [ -f "LICENSE" ]; then
        install -Dm644 LICENSE "\${pkgdir}/usr/share/licenses/\${pkgname}/LICENSE"
    fi

    # Stwórz skrypt uruchamiający
    cat > "\${pkgdir}/usr/bin/\${pkgname}" << 'EOFSCRIPT'
#!/bin/bash
cd /usr/share/tailui
exec python3 main.py "\$@"
EOFSCRIPT

    chmod 755 "\${pkgdir}/usr/bin/\${pkgname}"
}

post_install() {
    echo ""
    echo "TailUI został zainstalowany."
    echo "Możesz uruchomić aplikację przez menu aplikacji lub poleceniem: tailui"
    echo ""
    echo "Aktualizuję cache ikon..."
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor 2>/dev/null || true
    update-desktop-database -q 2>/dev/null || true
}

post_upgrade() {
    post_install
}

post_remove() {
    echo "TailUI został usunięty."
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor 2>/dev/null || true
    update-desktop-database -q 2>/dev/null || true
}
EOF

# Stwórz plik .install dla hooków post-instalacyjnych
echo -e "${YELLOW}Tworzenie pliku .install${NC}"
cat > "$BUILD_DIR/tailui.install" << 'EOF'
post_install() {
    echo ""
    echo "TailUI został zainstalowany."
    echo "Możesz uruchomić aplikację przez menu aplikacji lub poleceniem: tailui"
    echo ""
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor 2>/dev/null || true
    update-desktop-database -q 2>/dev/null || true
}

post_upgrade() {
    post_install
}

post_remove() {
    echo "TailUI został usunięty."
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor 2>/dev/null || true
    update-desktop-database -q 2>/dev/null || true
}
EOF

# Dodaj install do PKGBUILD
sed -i "/^optdepends=/a install=tailui.install" "$BUILD_DIR/PKGBUILD"

# Sprawdź dostępność zależności
echo -e "${YELLOW}Sprawdzanie dostępności zależności w systemie${NC}"
MISSING_DEPS=""

for dep in python pyside6 python-requests tailscale; do
    if [ "$dep" = "tailscale" ]; then
        if ! command -v tailscale >/dev/null 2>&1; then
            MISSING_DEPS="$MISSING_DEPS $dep"
        fi
    else
        if ! pacman -Q "$dep" >/dev/null 2>&1; then
            MISSING_DEPS="$MISSING_DEPS $dep"
        fi
    fi
done

if [ ! -z "$MISSING_DEPS" ]; then
    echo -e "${YELLOW}Uwaga: Następujące zależności nie są zainstalowane w systemie:${NC}"
    echo -e "${YELLOW}$MISSING_DEPS${NC}"
    echo -e "${YELLOW}Możesz je zainstalować przez: sudo pacman -S$MISSING_DEPS${NC}"
fi

# Zbuduj pakiet
echo -e "${YELLOW}Budowanie pakietu Arch${NC}"
cd "$BUILD_DIR"

# Sprawdź czy użytkownik chce użyć makepkg z fakeroot
if makepkg --help | grep -q "\-\-asdeps"; then
    echo -e "${GREEN}Używam makepkg do budowania pakietu${NC}"
    makepkg -f --skipinteg
else
    echo -e "${YELLOW}Uruchamiam makepkg${NC}"
    makepkg -f --skipinteg
fi

cd ..

# Znajdź utworzony pakiet
PACKAGE_FILE=$(find "$BUILD_DIR" -name "*.pkg.tar.zst" -o -name "*.pkg.tar.xz" | head -n 1)

if [ -z "$PACKAGE_FILE" ]; then
    echo -e "${RED}Błąd: Nie znaleziono utworzonego pakietu${NC}"
    exit 1
fi

# Przenieś pakiet do głównego katalogu i zmień nazwę
PACKAGE_BASENAME=$(basename "$PACKAGE_FILE")
FINAL_PACKAGE_NAME="${PACKAGE_NAME}_${VERSION}.pkg.tar.zst"

mv "$PACKAGE_FILE" "./$FINAL_PACKAGE_NAME"

echo -e "${GREEN}=== Pakiet został utworzony pomyślnie ===${NC}"
echo -e "${GREEN}Plik: $FINAL_PACKAGE_NAME${NC}"
echo ""
echo -e "${BLUE}Aby zainstalować pakiet:${NC}"
echo "  sudo pacman -U $FINAL_PACKAGE_NAME"
echo ""
echo -e "${BLUE}Lub użyj yay/paru jeśli używasz AUR:${NC}"
echo "  yay -U $FINAL_PACKAGE_NAME"
echo ""
echo -e "${BLUE}Aby sprawdzić zawartość pakietu:${NC}"
echo "  tar --use-compress-program=unzstd -tf $FINAL_PACKAGE_NAME | less"
echo ""
echo -e "${BLUE}Aby uzyskać informacje o pakiecie:${NC}"
echo "  pacman -Qip $FINAL_PACKAGE_NAME"
echo ""

# Opcjonalnie usuń katalog tymczasowy
read -p "Czy chcesz usunąć tymczasowy katalog budowania? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$BUILD_DIR"
    echo -e "${GREEN}Katalog tymczasowy został usunięty.${NC}"
else
    echo -e "${YELLOW}Katalog tymczasowy pozostawiony w: $BUILD_DIR${NC}"
    echo -e "${YELLOW}Możesz go użyć do debugowania lub ponownej kompilacji${NC}"
fi

