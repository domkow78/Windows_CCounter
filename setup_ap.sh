#!/bin/bash
# =============================================================================
# setup_ap.sh – Windows CCounter – konfiguracja Raspberry Pi jako Access Point
#
# Skrypt konfiguruje Raspberry Pi OS jako punkt dostępowy Wi-Fi, aby można było
# połączyć się bezpośrednio z urządzeniem i wejść do NiceGUI / FastAPI bez
# dodatkowej sieci LAN.
#
# Wymagania:
#   - uruchomienie na Raspberry Pi OS
#   - dostęp do sudo
#   - interfejs Wi-Fi na Raspberry Pi (zwykle wlan0)
#
# Użycie:
#   chmod +x setup_ap.sh
#   sudo ./setup_ap.sh
#
# Po instalacji:
#   - SSID: CCounter-AP
#   - Hasło: CCounter2026!
#   - Adres Pi: 192.168.4.1
#   - NiceGUI: http://192.168.4.1:8080
#   - FastAPI: http://192.168.4.1:8000
# =============================================================================

set -euo pipefail

SSID="${SSID:-CCounter-AP}"
PASS="${PASS:-CCounter2026!}"
AP_IP="${AP_IP:-192.168.4.1}"
AP_CIDR="${AP_CIDR:-24}"
WIFI_IFACE="${WIFI_IFACE:-wlan0}"
DHCP_START="${DHCP_START:-192.168.4.50}"
DHCP_END="${DHCP_END:-192.168.4.150}"
COUNTRY="${COUNTRY:-PL}"

if [ "${EUID}" -ne 0 ]; then
    echo "Uruchom skrypt przez sudo: sudo ./setup_ap.sh"
    exit 1
fi

if ! command -v hostapd >/dev/null 2>&1 || ! command -v dnsmasq >/dev/null 2>&1; then
    echo "Instaluję hostapd i dnsmasq..."
    apt-get update -qq
    apt-get install -y --no-install-recommends hostapd dnsmasq rfkill
fi

systemctl unmask hostapd >/dev/null 2>&1 || true
systemctl disable --now hostapd >/dev/null 2>&1 || true
systemctl disable --now dnsmasq >/dev/null 2>&1 || true

echo "Tworzę kopie zapasowe konfiguracji..."
mkdir -p /etc/ccounter-ap-backup
for file in /etc/dnsmasq.conf /etc/hostapd/hostapd.conf /etc/default/hostapd /etc/dhcpcd.conf; do
    if [ -f "$file" ]; then
        cp "$file" "/etc/ccounter-ap-backup/$(basename "$file").$(date +%Y%m%d_%H%M%S)" || true
    fi
done

echo "Konfiguruję statyczny adres IP dla ${WIFI_IFACE}..."
if ! grep -q "# CCounter AP START" /etc/dhcpcd.conf 2>/dev/null; then
    cat <<EOF >> /etc/dhcpcd.conf

# CCounter AP START
interface ${WIFI_IFACE}
    static ip_address=${AP_IP}/${AP_CIDR}
    nohook wpa_supplicant
# CCounter AP END
EOF
fi

echo "Konfiguruję hostapd..."
install -d /etc/hostapd
cat > /etc/hostapd/hostapd.conf <<EOF
country_code=${COUNTRY}
interface=${WIFI_IFACE}
ssid=${SSID}
hw_mode=g
channel=6
wmm_enabled=1
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=${PASS}
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
EOF

if grep -q '^#\?DAEMON_CONF=' /etc/default/hostapd 2>/dev/null; then
    sed -i 's|^#\?DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd
else
    echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' >> /etc/default/hostapd
fi

echo "Konfiguruję dnsmasq..."
mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig 2>/dev/null || true
cat > /etc/dnsmasq.conf <<EOF
interface=${WIFI_IFACE}
dhcp-range=${DHCP_START},${DHCP_END},255.255.255.0,24h
domain-needed
bogus-priv
EOF

echo "Włączam interfejs AP..."
rfkill unblock wifi || true
ip link set "${WIFI_IFACE}" down || true
ip addr flush dev "${WIFI_IFACE}" || true
ip link set "${WIFI_IFACE}" up || true
ip addr add "${AP_IP}/${AP_CIDR}" dev "${WIFI_IFACE}" || true

systemctl enable hostapd
systemctl enable dnsmasq
systemctl restart dnsmasq
systemctl restart hostapd

echo
echo "Gotowe. Punkt dostępowy powinien być aktywny."
echo "SSID: ${SSID}"
echo "Hasło: ${PASS}"
echo "Adres Pi: ${AP_IP}"
echo "NiceGUI: http://${AP_IP}:8080"
echo "FastAPI: http://${AP_IP}:8000"
echo
echo "Jeśli używasz Wi-Fi jako klient, ta konfiguracja je przejmie."
echo "Aby wrócić do poprzedniego stanu, przywróć pliki z /etc/ccounter-ap-backup oraz /etc/dnsmasq.conf.orig."
