# Deployment – Windows CCounter na Raspberry Pi

Instrukcja wdrożenia systemu Windows CCounter na Raspberry Pi OS (Bookworm / Bullseye).
Aplikacja uruchamiana jest **natywnie** z pełnym wsparciem dla GUI.

---

## Spis treści

1. [Wymagania sprzętowe i systemowe](#1-wymagania-sprzętowe-i-systemowe)
2. [Przygotowanie systemu](#2-przygotowanie-systemu)
3. [Instalacja aplikacji](#3-instalacja-aplikacji)
4. [Konfiguracja](#4-konfiguracja)
5. [Uruchomienie testowe](#5-uruchomienie-testowe)
6. [Autostart (systemd)](#6-autostart-systemd)
7. [Aktualizacja aplikacji](#7-aktualizacja-aplikacji)
8. [Rozwiązywanie problemów](#8-rozwiązywanie-problemów)
9. [Docker (opcjonalnie)](#9-docker-opcjonalnie)

---

## 1. Wymagania sprzętowe i systemowe

| Element | Minimalne wymagania |
|---------|---------------------|
| Raspberry Pi | 3B / 3B+ / 4B / 5 |
| System | Raspberry Pi OS Desktop (64-bit zalecany) |
| Python | 3.10 lub nowszy |
| RAM | 512 MB (1 GB+ zalecane) |
| Pamięć | 4 GB karta SD |
| Monitor | Dowolny z HDMI (dotykowy zalecany) |
| GPIO | Pin 17 (domyślnie) dla czujnika indukcyjnego |

### Weryfikacja systemu

```bash
# Wersja systemu
cat /etc/os-release

# Wersja Pythona
python3 --version

# Sprawdź dostęp do GPIO
ls -la /dev/gpiomem
```

---

## 2. Przygotowanie systemu

### 2.1 Aktualizacja systemu

```bash
sudo apt update && sudo apt upgrade -y
```

### 2.2 Instalacja wymaganych pakietów

```bash
# Git i narzędzia deweloperskie
sudo apt install -y git python3-venv python3-pip

# Tkinter dla GUI
sudo apt install -y python3-tk

# Opcjonalnie: narzędzia do debugowania GPIO
sudo apt install -y python3-gpiozero
```

### 2.3 Konfiguracja uprawnień GPIO

```bash
# Dodaj użytkownika do grupy gpio
sudo usermod -a -G gpio $USER

# Wyloguj się i zaloguj ponownie (lub restart)
sudo reboot
```

### 2.4 Weryfikacja uprawnień

```bash
# Po ponownym zalogowaniu
groups $USER
# Powinno zawierać: gpio

# Test dostępu do GPIO
ls -la /dev/gpiomem
# Powinno pokazać: crw-rw---- ... root gpio ...
```

---

## 3. Instalacja aplikacji

### 3.1 Klonowanie repozytorium

```bash
cd ~
git clone <repo-url> Windows_CCounter
cd Windows_CCounter
```

### 3.2 Utworzenie środowiska wirtualnego

```bash
# Utwórz venv
python3 -m venv venv

# Aktywuj środowisko
source venv/bin/activate

# Zaktualizuj pip
pip install --upgrade pip
```

### 3.3 Instalacja zależności

```bash
# Zależności aplikacji
pip install -r requirements.txt

# Biblioteki GPIO dla Raspberry Pi
pip install RPi.GPIO gpiozero
```

### 3.4 Utworzenie katalogów

```bash
mkdir -p data data/backup logs
```

---

## 4. Konfiguracja

### 4.1 Plik konfiguracyjny

Edytuj `config.yaml` według potrzeb:

```bash
nano config.yaml
```

### 4.2 Zalecane ustawienia produkcyjne

```yaml
sensor:
  gpio_pin: 17              # Pin GPIO czujnika
  debounce_ms: 50
  pull_up: true
  active_low: true          # Dla czujnika NPN

gui:
  enabled: true             # GUI włączone
  fullscreen: true          # Pełny ekran (produkcja)
  window_width: 800
  window_height: 480        # Rozdzielczość ekranu dotykowego

api:
  host: "0.0.0.0"           # Dostęp z sieci LAN
  port: 8000

logging:
  level: "INFO"             # Lub "WARNING" w produkcji
```

### 4.3 Podłączenie czujnika

```
Czujnik indukcyjny NPN (PNP wymaga active_low: false):

┌─────────────────┐
│  Raspberry Pi   │
│                 │
│  GPIO 17 ◄──────┼──── Signal (niebieski/żółty)
│  3.3V    ───────┼──── VCC (brązowy) 
│  GND     ───────┼──── GND (czarny)
└─────────────────┘
         │
    ┌────┴────┐
    │ Czujnik │
    │ indukcyjny
    └─────────┘
```

> ⚠️ Większość czujników przemysłowych wymaga 12-24V. 
> Użyj transoptora lub konwertera poziomów logicznych!

---

## 5. Uruchomienie testowe

```bash
cd ~/Windows_CCounter
source venv/bin/activate
python main.py
```

### Oczekiwany wynik:

```
==================================================
Uruchamianie Windows CCounter...
==================================================
SessionManager zainicjalizowany, katalog: ./data
Czujnik zainicjalizowany
API Server uruchomiony na porcie 8000
Uruchamianie GUI...
```

### Sprawdzenie API:

```bash
# Health check
curl http://localhost:8000/health

# Dokumentacja API (w przeglądarce)
# http://<IP-raspberry>:8000/docs
```

Zatrzymanie: `Ctrl+C` lub zamknięcie okna GUI.

---

## 6. Autostart (systemd)

### 6.1 Instalacja pliku usługi

```bash
# Skopiuj plik usługi
sudo cp ccounter.service /etc/systemd/system/

# Edytuj i dostosuj ścieżki/użytkownika
sudo nano /etc/systemd/system/ccounter.service
```

Lub utwórz ręcznie:

```bash
sudo nano /etc/systemd/system/ccounter.service
```

Zawartość (dostosuj ścieżki i użytkownika):

```ini
[Unit]
Description=Windows CCounter - System zliczania cykli
After=graphical.target
Wants=graphical.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/Windows_CCounter
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/pi/.Xauthority
ExecStart=/home/pi/Windows_CCounter/venv/bin/python main.py
Restart=on-failure
RestartSec=10s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical.target
```

> ⚠️ Zamień `pi` na rzeczywistą nazwę użytkownika (`whoami`).

### 6.2 Włączenie usługi

```bash
# Przeładuj konfigurację systemd
sudo systemctl daemon-reload

# Włącz autostart
sudo systemctl enable ccounter.service

# Uruchom teraz
sudo systemctl start ccounter.service

# Sprawdź status
sudo systemctl status ccounter.service
```

### 6.3 Zarządzanie usługą

```bash
# Start
sudo systemctl start ccounter

# Stop
sudo systemctl stop ccounter

# Restart
sudo systemctl restart ccounter

# Wyłącz autostart
sudo systemctl disable ccounter

# Logi na żywo
journalctl -u ccounter -f

# Ostatnie 50 linii logów
journalctl -u ccounter -n 50
```

---

## 7. Aktualizacja aplikacji

### 7.1 Skrypt aktualizacji

Użyj gotowego skryptu:

```bash
chmod +x redeploy.sh
./redeploy.sh
```

### 7.2 Ręczna aktualizacja

```bash
cd ~/Windows_CCounter

# Zatrzymaj usługę
sudo systemctl stop ccounter

# Pobierz zmiany
git pull

# Aktywuj venv i zaktualizuj zależności (jeśli zmienione)
source venv/bin/activate
pip install -r requirements.txt

# Uruchom ponownie
sudo systemctl start ccounter
```

---

## 8. Rozwiązywanie problemów

### GUI nie uruchamia się (brak DISPLAY)

```bash
# Sprawdź zmienną DISPLAY
echo $DISPLAY
# Powinno pokazać: :0

# Jeśli puste, ustaw ręcznie
export DISPLAY=:0
```

### Brak dostępu do GPIO

```bash
# Sprawdź grupy użytkownika
groups $USER

# Dodaj do grupy gpio
sudo usermod -a -G gpio $USER

# Wyloguj i zaloguj ponownie
```

### Port 8000 zajęty

```bash
# Sprawdź co zajmuje port
sudo ss -tlnp | grep 8000

# Zabij proces (ostrożnie!)
sudo kill <PID>
```

### Czujnik nie reaguje

```bash
# Test GPIO w Pythonie
python3 << 'EOF'
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)
print(f"Stan pinu 17: {GPIO.input(17)}")
GPIO.cleanup()
EOF
```

### Usługa nie startuje

```bash
# Szczegółowe logi
journalctl -u ccounter -n 100 --no-pager

# Sprawdź składnię pliku usługi
sudo systemd-analyze verify /etc/systemd/system/ccounter.service
```

### Eksport na pendrive nie działa

```bash
# Sprawdź zamontowane urządzenia
lsblk

# Zamontuj pendrive ręcznie
sudo mkdir -p /media/usb
sudo mount /dev/sda1 /media/usb

# Sprawdź uprawnienia
ls -la /media/usb
```

---

## 9. Docker (opcjonalnie)

Dla środowisk **bez monitora** (headless) dostępna jest konfiguracja Docker.

> ⚠️ Docker **nie jest zalecany** dla Raspberry Pi z monitorem i GUI.

Pliki Docker znajdują się w repozytorium:
- `Dockerfile`
- `docker-compose.yml`
- `config.docker.yaml` (GUI wyłączone)

Szczegóły w sekcji komentarzy w tych plikach.

---

## Podsumowanie

| Krok | Komenda |
|------|---------|
| Instalacja | `git clone`, `pip install -r requirements.txt` |
| Test | `python main.py` |
| Autostart | `sudo systemctl enable ccounter` |
| Logi | `journalctl -u ccounter -f` |
| Aktualizacja | `./redeploy.sh` |
| API Docs | `http://<IP>:8000/docs` |
