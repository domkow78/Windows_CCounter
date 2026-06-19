#!/bin/bash
# =============================================================================
# redeploy.sh – Windows CCounter
# Pobiera zmiany z repo i restartuje usługę.
#
# Użycie:
#   chmod +x redeploy.sh        # jednorazowo, nadanie uprawnień
#   ./redeploy.sh
# =============================================================================

set -e  # Zatrzymaj skrypt przy pierwszym błędzie

SERVICE_NAME="ccounter"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "============================================================"
echo "  Windows CCounter – Aktualizacja"
echo "============================================================"

# Przejdź do katalogu aplikacji
cd "$APP_DIR"

# 1. Zatrzymaj usługę (jeśli działa)
echo ""
echo "[1/5] Zatrzymywanie usługi..."
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    sudo systemctl stop "$SERVICE_NAME"
    echo "      Usługa zatrzymana."
else
    echo "      Usługa nie była uruchomiona."
fi

# 2. Pobierz zmiany z repozytorium
echo ""
echo "[2/5] Pobieranie zmian (git pull)..."
git pull

# 3. Utwórz katalogi (jeśli nie istnieją)
echo ""
echo "[3/5] Sprawdzanie katalogów..."
mkdir -p data data/backup logs

# 4. Aktualizacja zależności (opcjonalnie)
echo ""
echo "[4/5] Aktualizacja zależności..."
source venv/bin/activate
pip install -q -r requirements.txt

# 5. Uruchom usługę
echo ""
echo "[5/5] Uruchamianie usługi..."
sudo systemctl start "$SERVICE_NAME"

# Sprawdź status
sleep 2
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo ""
    echo "============================================================"
    echo "  ✅ Gotowe! Usługa '$SERVICE_NAME' uruchomiona."
    echo ""
    echo "  Status:     sudo systemctl status $SERVICE_NAME"
    echo "  Logi:       journalctl -u $SERVICE_NAME -f"
    echo "  Health:     curl http://localhost:8000/health"
    echo "  API Docs:   http://localhost:8000/docs"
    echo "============================================================"
else
    echo ""
    echo "============================================================"
    echo "  ❌ Błąd! Usługa nie uruchomiła się."
    echo ""
    echo "  Sprawdź logi: journalctl -u $SERVICE_NAME -n 50"
    echo "============================================================"
    exit 1
fi
echo ""
