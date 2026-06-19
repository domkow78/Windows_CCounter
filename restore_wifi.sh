#!/bin/bash
# =============================================================================
# restore_wifi.sh – Windows CCounter – przywracanie trybu Wi-Fi (klient)
#
# Skrypt cofa konfigurację Access Point (setup_ap.sh) i przywraca
# normalny tryb klienta Wi-Fi, aby umożliwić dostęp do Internetu –
# np. przed wykonaniem `git pull` lub aktualizacją systemu.
#
# Użycie:
#   chmod +x restore_wifi.sh
#   sudo ./restore_wifi.sh
#
# Po przywróceniu Wi-Fi:
#   - Uruchom: ./redeploy.sh          (aktualizacja aplikacji)
#   - Lub:     sudo ./setup_ap.sh     (ponowna konfiguracja AP)
# =============================================================================

set -euo pipefail

WIFI_IFACE="${WIFI_IFACE:-wlan0}"

# ---------------------------------------------------------------------------
# Pomocnicze kolory
# ---------------------------------------------------------------------------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERR] ${NC}  $*"; }

# ---------------------------------------------------------------------------
# Wymagane sudo
# ---------------------------------------------------------------------------
if [ "${EUID}" -ne 0 ]; then
    error "Uruchom skrypt przez sudo: sudo ./restore_wifi.sh"
    exit 1
fi

echo
echo "============================================================"
echo "  Windows CCounter – Przywracanie Wi-Fi (tryb klient)"
echo "============================================================"
echo

# ---------------------------------------------------------------------------
# 1. Zatrzymaj i zablokuj usługi AP
# ---------------------------------------------------------------------------
info "[1/6] Zatrzymywanie hostapd i dnsmasq..."
for svc in hostapd dnsmasq; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        systemctl stop "$svc"
        info "      $svc zatrzymany."
    else
        warn "      $svc nie był uruchomiony."
    fi
    systemctl disable "$svc" 2>/dev/null || true
done

# ---------------------------------------------------------------------------
# 2. Usuń blok CCounter AP z /etc/dhcpcd.conf
# ---------------------------------------------------------------------------
info "[2/6] Przywracam /etc/dhcpcd.conf (usuwam blok AP)..."
if grep -q "# CCounter AP START" /etc/dhcpcd.conf 2>/dev/null; then
    # Usuń blok między markerami (włącznie z pustą linią przed)
    sed -i '/^$/N;/^\n# CCounter AP START/,/# CCounter AP END/d' /etc/dhcpcd.conf || true
    # Próba alternatywna (jedna pusta linia przed blokiem)
    sed -i '/# CCounter AP START/,/# CCounter AP END/d' /etc/dhcpcd.conf || true
    info "      Blok AP usunięty z dhcpcd.conf."
else
    warn "      Blok AP nie znaleziony w dhcpcd.conf – pomijam."
fi

# ---------------------------------------------------------------------------
# 3. Przywróć dnsmasq.conf (jeśli istnieje oryginał)
# ---------------------------------------------------------------------------
info "[3/6] Sprawdzam kopię zapasową dnsmasq.conf..."
if [ -f /etc/dnsmasq.conf.orig ]; then
    mv /etc/dnsmasq.conf.orig /etc/dnsmasq.conf
    info "      /etc/dnsmasq.conf.orig przywrócony."
else
    warn "      Brak /etc/dnsmasq.conf.orig – pomijam."
fi

# ---------------------------------------------------------------------------
# 4. Upewnij się, że wpa_supplicant jest aktywny
# ---------------------------------------------------------------------------
info "[4/6] Włączam wpa_supplicant..."
systemctl enable wpa_supplicant 2>/dev/null || true
systemctl start  wpa_supplicant 2>/dev/null || true
# Wariant z interfejsem (Bookworm+)
WPA_SVC="wpa_supplicant@${WIFI_IFACE}"
if systemctl list-unit-files "${WPA_SVC}.service" --no-legend 2>/dev/null | grep -q "${WPA_SVC}"; then
    systemctl enable  "${WPA_SVC}" 2>/dev/null || true
    systemctl restart "${WPA_SVC}" 2>/dev/null || true
    info "      ${WPA_SVC} włączony."
fi

# ---------------------------------------------------------------------------
# 5. Zresetuj interfejs i uruchom dhcpcd ponownie
# ---------------------------------------------------------------------------
info "[5/6] Restartuję interfejs ${WIFI_IFACE} i dhcpcd..."
ip link set "${WIFI_IFACE}" down  2>/dev/null || true
ip addr flush dev "${WIFI_IFACE}" 2>/dev/null || true
ip link set "${WIFI_IFACE}" up    2>/dev/null || true

if systemctl is-enabled --quiet dhcpcd 2>/dev/null; then
    systemctl restart dhcpcd
    info "      dhcpcd zrestartowany."
elif systemctl is-enabled --quiet NetworkManager 2>/dev/null; then
    systemctl restart NetworkManager
    info "      NetworkManager zrestartowany."
else
    warn "      Nie znaleziono dhcpcd ani NetworkManager – uruchom sieć ręcznie."
fi

# ---------------------------------------------------------------------------
# 6. Odczekaj i sprawdź połączenie
# ---------------------------------------------------------------------------
info "[6/6] Oczekiwanie na adres IP (max 20 s)..."
TIMEOUT=20
WAITED=0
while [ "$WAITED" -lt "$TIMEOUT" ]; do
    IP=$(ip -4 addr show "${WIFI_IFACE}" 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1 || true)
    if [ -n "$IP" ] && [ "$IP" != "192.168.4.1" ]; then
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
done

echo
if [ -n "${IP:-}" ] && [ "$IP" != "192.168.4.1" ]; then
    echo "============================================================"
    echo -e "  ${GREEN}✅ Wi-Fi przywrócone!${NC}"
    echo "     Interfejs : ${WIFI_IFACE}"
    echo "     Adres IP  : ${IP}"
    echo
    echo "  Możesz teraz:"
    echo "    ./redeploy.sh          – aktualizacja aplikacji"
    echo "    sudo ./setup_ap.sh     – ponowna konfiguracja AP"
    echo "============================================================"
else
    echo "============================================================"
    echo -e "  ${YELLOW}⚠️  Nie udało się automatycznie uzyskać adresu IP.${NC}"
    echo
    echo "  Możliwe przyczyny:"
    echo "    - Brak skonfigurowanej sieci w wpa_supplicant.conf"
    echo "    - Sieć poza zasięgiem"
    echo
    echo "  Skonfiguruj sieć ręcznie:"
    echo "    sudo raspi-config          (opcja: Wireless LAN)"
    echo "    # lub:"
    echo "    sudo nano /etc/wpa_supplicant/wpa_supplicant.conf"
    echo
    echo "  Wymagana treść pliku (przykład):"
    echo "    country=PL"
    echo "    ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev"
    echo "    update_config=1"
    echo "    network={"
    echo "        ssid=\"NazwaTwojejSieci\""
    echo "        psk=\"HasloDoSieci\""
    echo "    }"
    echo "============================================================"
fi
echo
