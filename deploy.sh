#!/bin/bash
# =============================================================================
# deploy.sh – Windows CCounter – Pierwsze uruchomienie na Raspberry Pi
#
# Skrypt wykonuje pełną instalację od zera:
#   - instaluje zależności systemowe
#   - tworzy środowisko Python
#   - instaluje pakiety
#   - konfiguruje i włącza usługę systemd
#
# Użycie:
#   chmod +x deploy.sh
#   ./deploy.sh
#
# Po zakończeniu aplikacja startuje automatycznie przy każdym uruchomieniu RPi.
# Kolejne aktualizacje wykonuj przez: ./redeploy.sh
# =============================================================================

set -e  # Zatrzymaj przy błędzie

SERVICE_NAME="ccounter"
SERVICE_FILE="ccounter.service"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
CURRENT_USER="$(whoami)"
VENV_DIR="$APP_DIR/venv"
PYTHON_BIN="$VENV_DIR/bin/python"
SYSTEMD_DIR="/etc/systemd/system"

echo ""
echo "============================================================"
echo "  Windows CCounter – Pierwsza instalacja"
echo "============================================================"
echo "  Katalog aplikacji : $APP_DIR"
echo "  Użytkownik        : $CURRENT_USER"
echo "============================================================"

# ---------------------------------------------------------------------------
# [1] Zależności systemowe
# ---------------------------------------------------------------------------
echo ""
echo "[1/7] Instalacja zależności systemowych..."

sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    python3-venv \
    python3-pip \
    python3-tk \
    git \
    i2c-tools

echo "      OK"

# ---------------------------------------------------------------------------
# [2] Sprawdzenie i włączenie I2C (dla Automation HAT Mini)
# ---------------------------------------------------------------------------
echo ""
echo "[2/7] Sprawdzanie I2C (Automation HAT Mini)..."

if ! grep -q "^dtparam=i2c_arm=on" /boot/firmware/config.txt 2>/dev/null \
   && ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt 2>/dev/null; then
    echo "      Włączanie I2C w /boot/firmware/config.txt..."
    if [ -f /boot/firmware/config.txt ]; then
        echo "dtparam=i2c_arm=on" | sudo tee -a /boot/firmware/config.txt > /dev/null
    else
        echo "dtparam=i2c_arm=on" | sudo tee -a /boot/config.txt > /dev/null
    fi
    echo "      ⚠️  I2C włączone – wymagany restart po instalacji!"
    I2C_ENABLED_NOW=true
else
    echo "      I2C już włączone. OK"
fi

# Dodaj użytkownika do grup gpio i i2c
sudo usermod -aG gpio,i2c "$CURRENT_USER" 2>/dev/null || true

# ---------------------------------------------------------------------------
# [3] Środowisko wirtualne Python
# ---------------------------------------------------------------------------
echo ""
echo "[3/7] Tworzenie środowiska wirtualnego..."

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "      Środowisko utworzone: $VENV_DIR"
else
    echo "      Środowisko już istnieje: $VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip -q

# ---------------------------------------------------------------------------
# [4] Zależności Python
# ---------------------------------------------------------------------------
echo ""
echo "[4/7] Instalacja zależności Python..."

pip install -q -r "$APP_DIR/requirements.txt"

# Automation HAT Mini
echo ""
echo "      Instalacja automationhat (Pimoroni Automation HAT Mini)..."
pip install -q automationhat

echo "      OK"

# ---------------------------------------------------------------------------
# [5] Katalogi danych
# ---------------------------------------------------------------------------
echo ""
echo "[5/7] Tworzenie katalogów..."

mkdir -p "$APP_DIR/data" "$APP_DIR/data/backup" "$APP_DIR/logs"
echo "      data/, data/backup/, logs/ – OK"

# ---------------------------------------------------------------------------
# [6] Konfiguracja pliku usługi systemd
# ---------------------------------------------------------------------------
echo ""
echo "[6/7] Instalacja usługi systemd..."

SERVICE_SRC="$APP_DIR/$SERVICE_FILE"
SERVICE_DST="$SYSTEMD_DIR/$SERVICE_FILE"

if [ ! -f "$SERVICE_SRC" ]; then
    echo "      ❌ Błąd: nie znaleziono pliku $SERVICE_SRC"
    exit 1
fi

# Podmień zmienne w pliku usługi i zainstaluj
sed \
    -e "s|User=pi|User=$CURRENT_USER|g" \
    -e "s|Group=pi|Group=$CURRENT_USER|g" \
    -e "s|/home/pi/Windows_CCounter|$APP_DIR|g" \
    -e "s|/home/pi/\.Xauthority|/home/$CURRENT_USER/.Xauthority|g" \
    "$SERVICE_SRC" | sudo tee "$SERVICE_DST" > /dev/null

echo "      Zainstalowano: $SERVICE_DST"
echo "      Użytkownik: $CURRENT_USER"
echo "      Katalog: $APP_DIR"

# ---------------------------------------------------------------------------
# [7] Uruchomienie usługi
# ---------------------------------------------------------------------------
echo ""
echo "[7/7] Włączanie i uruchamianie usługi..."

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"

sleep 3

# ---------------------------------------------------------------------------
# Podsumowanie
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"

if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "  ✅ Instalacja zakończona pomyślnie!"
    echo ""
    echo "  Usługa     : $SERVICE_NAME (aktywna, autostart włączony)"
    echo "  Web UI     : http://$(hostname -I | awk '{print $1}'):8080"
    echo "  REST API   : http://$(hostname -I | awk '{print $1}'):8000"
    echo ""
    echo "  Logi       : journalctl -u $SERVICE_NAME -f"
    echo "  Status     : sudo systemctl status $SERVICE_NAME"
    echo "  Aktualizacja: ./redeploy.sh"
else
    echo "  ❌ Usługa nie uruchomiła się!"
    echo ""
    echo "  Sprawdź logi: journalctl -u $SERVICE_NAME -n 50"
    echo "============================================================"
    exit 1
fi

if [ "${I2C_ENABLED_NOW}" = true ]; then
    echo ""
    echo "  ⚠️  UWAGA: I2C zostało właśnie włączone."
    echo "     Wymagany restart: sudo reboot"
    echo "     Po restarcie usługa wystartuje automatycznie."
fi

echo "============================================================"
echo ""
