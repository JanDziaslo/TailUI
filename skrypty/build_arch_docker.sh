#!/bin/bash

# Skrypt do tworzenia pakietu .pkg.tar.zst dla TailUI na systemach nie-Arch (np. Ubuntu/Debian)
# Używa Dockera z obrazem Arch Linux do budowania pakietu

set -e

# Kolory dla outputu
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Tworzenie pakietu Arch Linux dla TailUI (Docker) ===${NC}"

# Sprawdź czy jesteśmy w katalogu projektu
if [ ! -f "main.py" ] || [ ! -f "requirements.txt" ]; then
    echo -e "${RED}Błąd: Uruchom skrypt w katalogu głównym projektu (gdzie znajduje się main.py)${NC}"
    exit 1
fi

# Sprawdź czy Docker jest dostępny
if ! command -v docker >/dev/null 2>&1; then
    echo -e "${RED}Błąd: Docker nie jest zainstalowany.${NC}"
    echo -e "${YELLOW}Zainstaluj Docker: sudo apt install docker.io${NC}"
    echo -e "${YELLOW}Dodaj użytkownika do grupy docker: sudo usermod -aG docker \$USER${NC}"
    exit 1
fi

# Sprawdź czy użytkownik ma uprawnienia do Dockera
if ! docker ps >/dev/null 2>&1; then
    echo -e "${RED}Błąd: Brak uprawnień do Dockera.${NC}"
    echo -e "${YELLOW}Uruchom: sudo usermod -aG docker \$USER${NC}"
    echo -e "${YELLOW}Następnie wyloguj się i zaloguj ponownie, lub użyj: sudo docker ...${NC}"
    echo ""
    read -p "Czy chcesz użyć sudo dla tego polecenia? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        DOCKER_CMD="sudo docker"
    else
        exit 1
    fi
else
    DOCKER_CMD="docker"
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

# Stwórz PKGBUILD
echo -e "${YELLOW}Tworzenie pliku PKGBUILD${NC}"
cat > "$BUILD_DIR/PKGBUILD" << 'PKGBUILD_EOF'
# Maintainer: Jan Dziasło i Ropucha
pkgname=tailui
pkgver=1.0.7
pkgrel=1
pkgdesc='Nieoficjalny interfejs graficzny dla Tailscale'
arch=('any')
url='https://github.com/JanDziaslo/tailui'
license=('MIT')
depends=(
    'python>=3.10'
    'python-pyside6'
    'python-requests'
    'tailscale'
)
install=tailui.install
source=(
    'main.py'
    'tailscale_client.py'
    'ip_info.py'
    'gui.py'
    'requirements.txt'
    'tailui.desktop'
    'config.py'
    'assets_icon_tailui.png'
    'assets_icon_tailui.svg'
    'README.md'
    'LICENSE'
)

md5sums=(
    'SKIP'
    'SKIP'
    'SKIP'
    'SKIP'
    'SKIP'
    'SKIP'
    'SKIP'
    'SKIP'
    'SKIP'
    'SKIP'
    'SKIP'
)

package() {
    # Utwórz katalogi
    install -dm755 "${pkgdir}/usr/share/${pkgname}"
    install -dm755 "${pkgdir}/usr/bin"
    install -dm755 "${pkgdir}/usr/share/applications"

    # Zainstaluj pliki aplikacji
    install -Dm644 main.py "${pkgdir}/usr/share/${pkgname}/main.py"
    install -Dm644 tailscale_client.py "${pkgdir}/usr/share/${pkgname}/tailscale_client.py"
    install -Dm644 ip_info.py "${pkgdir}/usr/share/${pkgname}/ip_info.py"
    install -Dm644 gui.py "${pkgdir}/usr/share/${pkgname}/gui.py"

    # Zainstaluj config.py jeśli istnieje
    if [ -f "config.py" ]; then
        install -Dm644 config.py "${pkgdir}/usr/share/${pkgname}/config.py"
    fi

    # Zainstaluj requirements.txt dla referencji
    if [ -f "requirements.txt" ]; then
        install -Dm644 requirements.txt "${pkgdir}/usr/share/${pkgname}/requirements.txt"
    fi

    # Zainstaluj ikony
    if [ -f "assets_icon_tailui.png" ]; then
        install -Dm644 assets_icon_tailui.png "${pkgdir}/usr/share/${pkgname}/assets_icon_tailui.png"
        install -Dm644 assets_icon_tailui.png "${pkgdir}/usr/share/icons/hicolor/48x48/apps/${pkgname}.png"
    fi

    if [ -f "assets_icon_tailui.svg" ]; then
        install -Dm644 assets_icon_tailui.svg "${pkgdir}/usr/share/${pkgname}/assets_icon_tailui.svg"
        install -Dm644 assets_icon_tailui.svg "${pkgdir}/usr/share/icons/hicolor/scalable/apps/${pkgname}.svg"
    fi

    # Zainstaluj plik .desktop
    install -Dm644 tailui.desktop "${pkgdir}/usr/share/applications/${pkgname}.desktop"

    # Zainstaluj dokumentację
    if [ -f "README.md" ]; then
        install -Dm644 README.md "${pkgdir}/usr/share/doc/${pkgname}/README.md"
    fi

    if [ -f "LICENSE" ]; then
        install -Dm644 LICENSE "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
    fi

    # Stwórz skrypt uruchamiający
    cat > "${pkgdir}/usr/bin/${pkgname}" << 'EOFSCRIPT'
#!/bin/bash
cd /usr/share/tailui
exec python3 main.py "$@"
EOFSCRIPT

    chmod 755 "${pkgdir}/usr/bin/${pkgname}"
}
PKGBUILD_EOF

# Stwórz plik .install dla hooków post-instalacyjnych
echo -e "${YELLOW}Tworzenie pliku .install${NC}"
cat > "$BUILD_DIR/tailui.install" << 'INSTALL_EOF'
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
INSTALL_EOF

# Stwórz skrypt budujący dla Dockera
echo -e "${YELLOW}Tworzenie skryptu budującego dla kontenera${NC}"
cat > "$BUILD_DIR/build_in_container.sh" << 'CONTAINER_EOF'
#!/bin/bash
set -e

echo "=== Budowanie pakietu w kontenerze Arch Linux ==="

# Aktualizuj system
echo "Aktualizacja systemu..."
pacman -Sy --noconfirm

# Zainstaluj narzędzia budujące
echo "Instalacja narzędzi budujących..."
pacman -S --noconfirm --needed base-devel fakeroot

# Stwórz użytkownika builder (makepkg nie może działać jako root)
useradd -m -G wheel builder || true
echo "builder ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Kopiuj pliki do katalogu buildera
mkdir -p /home/builder/build
cp -r /build/* /home/builder/build/
chown -R builder:builder /home/builder/build

# Buduj jako builder (bez sprawdzania zależności - to tylko budowanie pakietu)
cd /home/builder/build
su - builder -c "cd /home/builder/build && makepkg -f --skipinteg --nodeps --noconfirm"

# Skopiuj wynik z powrotem
cp /home/builder/build/*.pkg.tar.zst /output/ 2>/dev/null || \
cp /home/builder/build/*.pkg.tar.xz /output/ 2>/dev/null || \
echo "Nie znaleziono pakietu!"

echo "=== Budowanie zakończone ==="
CONTAINER_EOF

chmod +x "$BUILD_DIR/build_in_container.sh"

# Pobierz obraz Arch Linux jeśli go nie ma
echo -e "${YELLOW}Sprawdzanie obrazu Arch Linux...${NC}"
if ! $DOCKER_CMD images | grep -q "^archlinux"; then
    echo -e "${YELLOW}Pobieranie obrazu Arch Linux...${NC}"
    $DOCKER_CMD pull archlinux:latest
else
    echo -e "${GREEN}Obraz Arch Linux już istnieje${NC}"
fi

# Utwórz katalog wyjściowy
mkdir -p "$BUILD_DIR/output"

# Uruchom budowanie w kontenerze Docker
echo -e "${YELLOW}Uruchamianie budowania w kontenerze Docker...${NC}"
echo -e "${BLUE}To może potrwać kilka minut przy pierwszym uruchomieniu...${NC}"

$DOCKER_CMD run --rm \
    -v "$(pwd)/$BUILD_DIR:/build:ro" \
    -v "$(pwd)/$BUILD_DIR/output:/output" \
    -v "$(pwd)/$BUILD_DIR/build_in_container.sh:/build_in_container.sh:ro" \
    archlinux:latest \
    /bin/bash /build_in_container.sh

# Sprawdź czy pakiet został utworzony
PACKAGE_FILE=$(find "$BUILD_DIR/output" -name "*.pkg.tar.zst" -o -name "*.pkg.tar.xz" | head -n 1)

if [ -z "$PACKAGE_FILE" ]; then
    echo -e "${RED}Błąd: Nie znaleziono utworzonego pakietu${NC}"
    exit 1
fi

# Przenieś pakiet do głównego katalogu
PACKAGE_NAME=$(basename "$PACKAGE_FILE")
mv "$PACKAGE_FILE" "./"

echo -e "${GREEN}=== Pakiet został utworzony pomyślnie ===${NC}"
echo -e "${GREEN}Plik: $PACKAGE_NAME${NC}"
echo ""
echo -e "${BLUE}Aby zainstalować pakiet na systemie Arch Linux:${NC}"
echo "  sudo pacman -U $PACKAGE_NAME"
echo ""
echo -e "${BLUE}Lub użyj yay/paru jeśli używasz AUR:${NC}"
echo "  yay -U $PACKAGE_NAME"
echo ""
echo -e "${BLUE}Aby sprawdzić zawartość pakietu:${NC}"
echo "  tar -tzf $PACKAGE_NAME | less"
echo ""
echo -e "${BLUE}Aby uzyskać informacje o pakiecie:${NC}"
echo "  tar -xOf $PACKAGE_NAME .PKGINFO | less"
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

echo ""
echo -e "${GREEN}✅ Gotowe! Pakiet Arch Linux został zbudowany na Ubuntu/Kubuntu${NC}"

