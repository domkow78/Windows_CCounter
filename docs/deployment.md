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
10. [Access Point – przywracanie Wi-Fi](#10-access-point--przywracanie-wi-fi)

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
| Interfejs czujnika | Automation HAT Mini, wejście IN1 |

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

### 2.3 Konfiguracja uprawnień GPIO (jeśli używasz GPIO bezpośredniego)

```bash
# Dodaj użytkownika do grupy gpio
sudo usermod -a -G gpio $USER

# Wyloguj się i zaloguj ponownie (lub restart)
sudo reboot
```

> **Uwaga:** Jeśli używasz Automation HAT Mini z wejściem IN1, uprawnienia GPIO mogą nie być wymagane.

### 2.4 Weryfikacja uprawnień

```bash
# Po ponownym zalogowaniu (jeśli używasz GPIO)
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

# Biblioteki GPIO dla Raspberry Pi (jeśli używasz GPIO bezpośredniego)
pip install RPi.GPIO gpiozero

# === WARIANT A: Automation HAT Mini (ZALECANE) ===
# Instalacja biblioteki Automation HAT
pip install automationhat

# Lub ze źródła:
git clone https://github.com/pimoroni/automation-hat
cd automation-hat
./install.sh
cd ../Windows_CCounter

# === WARIANT B: GPIO bezpośrednie (ALTERNATYWA) ===
# W tym wypadku wystarczy pip install RPi.GPIO
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

### 4.2 Wybór backendu czujnika

W pliku `config.yaml` wybierz backend sprzętowy:

#### Wariant A: Automation HAT Mini (ZALECANE)
```yaml
sensor:
  # Użyj Automation HAT Mini z wejściem IN1
  hardware_backend: "automationhat"
  automation_hat_input: "one"    # "one", "two" lub "three"
  debounce_ms: 50
  active_low: true
```

#### Wariant B: GPIO bezpośrednie
```yaml
sensor:
  # Użyj bezpośredniego GPIO
  hardware_backend: "gpio"
  gpio_pin: 17                   # Numer pinu GPIO
  pull_up: true
  debounce_ms: 50
  active_low: true
```

### 4.2 Zalecane ustawienia produkcyjne

```yaml
sensor:
  hardware_backend: "automationhat"   # wariant docelowy
  automation_hat_input: "one"         # wejście IN1 na HAT
  gpio_pin: 17                        # używane tylko przy backendzie GPIO
  pull_up: true                       # używane tylko przy backendzie GPIO
  debounce_ms: 50
  active_low: true                    # Dla czujnika NPN
  simulation_mode: false

gui:
  enabled: true             # GUI włączone
  fullscreen: true          # Pełny ekran (produkcja)
  window_width: 800
  window_height: 480        # Rozdzielczość ekranu dotykowego

web:
  enabled: true             # Web UI dostępny w sieci lokalnej
  host: "0.0.0.0"
  port: 8080

api:
  host: "0.0.0.0"           # Dostęp z sieci LAN
  port: 8000

logging:
  level: "INFO"             # Lub "WARNING" w produkcji
```

### 4.3 Podłączenie czujnika

```
Czujnik E2S-H4N1 4 mm 5V -> Automation HAT Mini (zalecane):

┌──────────────────────┐        ┌──────────────────────┐
│     E2S-H4N1 5V      │        │  Automation HAT Mini │
│                      │        │                      │
│ VCC  ────────────────┼──────▶ │ zasilanie 5V         │
│ GND  ────────────────┼──────▶ │ GND                  │
│ OUT  ────────────────┼──────▶ │ IN1                  │
└──────────────────────┘        └──────────────────────┘
```

> ⚠️ Przed uruchomieniem potwierdź typ wyjścia konkretnej wersji czujnika
> **E2S-H4N1 4 mm 5V** w karcie katalogowej. Jeżeli wersja wyjścia wymaga innego sposobu
> polaryzacji lub pracy typu open collector, sprawdź to pomiarem przed podłączeniem produkcyjnym.

> ℹ️ Szczegółowy opis wariantu sprzętowego i uzasadnienie użycia nakładki znajduje się w pliku `pimoroni.md`.

### 4.4 Dlaczego IN1 zamiast bezpośredniego GPIO

W tym projekcie zalecane jest użycie **Automation HAT Mini** jako wejścia pośredniego między
czujnikiem a Raspberry Pi, ponieważ:

- upraszcza okablowanie i serwis,
- daje wygodne zaciski śrubowe,
- ogranicza ryzyko błędnego podania sygnału bezpośrednio na GPIO,
- ułatwia dalszą rozbudowę systemu o dodatkowe sygnały automatyki.

Bezpośrednie GPIO można traktować jako wariant uproszczony lub testowy.

W aktualnej konfiguracji wdrożeniowej wariant z **Automation HAT Mini / IN1** należy traktować jako podstawowy,
a bezpośrednie **GPIO** jako alternatywę dla prostszych lub testowych instalacji.

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
# Status aplikacji
curl http://localhost:8000/

# Szczegółowy status systemu
curl http://localhost:8000/api/status

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

> ⚠️ **Jeśli Pi działa w trybie Access Point** (uruchomiony `setup_ap.sh`), nie ma połączenia z Internetem.
> Przed aktualizacją przywróć tryb klienta Wi-Fi:
>
> ```bash
> sudo ./restore_wifi.sh
> ```
>
> Skrypt `redeploy.sh` wykrywa aktywny AP i sam pyta o przywrócenie Wi-Fi.

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

## 10. Access Point – przywracanie Wi-Fi

Kiedy Raspberry Pi działa jako punkt dostępowy (po uruchomieniu `setup_ap.sh`),
traci połączenie z Internetem. Aby wykonać `git pull` lub aktualizację systemu,
należy tymczasowo przywrócić tryb klienta Wi-Fi.

### Skrypt `restore_wifi.sh`

```bash
chmod +x restore_wifi.sh
sudo ./restore_wifi.sh
```

Co robi skrypt:

| Krok | Akcja |
|------|-------|
| 1 | Zatrzymuje i wyłącza `hostapd` oraz `dnsmasq` |
| 2 | Usuwa blok `# CCounter AP` ze statycznym IP z `/etc/dhcpcd.conf` |
| 3 | Przywraca oryginalny `/etc/dnsmasq.conf.orig` (jeśli istnieje) |
| 4 | Włącza i uruchamia `wpa_supplicant` |
| 5 | Restartuje `dhcpcd` / `NetworkManager` |
| 6 | Czeka na adres IP i informuje o rezultacie |

Po zakończeniu skrypt wyświetla przydzielony adres IP lub instrukcję ręcznej
konfiguracji sieci (jeśli `wpa_supplicant.conf` nie zawiera żadnej sieci).

### Typowy przepływ: AP → aktualizacja → AP

```bash
# 1. Przywróć Wi-Fi
sudo ./restore_wifi.sh

# 2. Zaktualizuj aplikację
./redeploy.sh

# 3. Włącz ponownie Access Point
sudo ./setup_ap.sh
```

> ℹ️ `redeploy.sh` automatycznie wykrywa aktywny AP i pyta o przywrócenie Wi-Fi
> przed wykonaniem `git pull`.

### Konfiguracja sieci domowej (jednorazowo)

Aby `restore_wifi.sh` mógł automatycznie połączyć się z siecią domową,
upewnij się, że sieć jest zdefiniowana w `wpa_supplicant.conf`:

```bash
sudo raspi-config
# System Options → Wireless LAN
```

Lub ręcznie:

```bash
sudo nano /etc/wpa_supplicant/wpa_supplicant.conf
```

```
country=PL
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="NazwaTwojejSieci"
    psk="HasloDoSieci"
}
```

---

## Podsumowanie

| Krok | Komenda |
|------|---------|
| Instalacja | `git clone`, `pip install -r requirements.txt` |
| Test | `python main.py` |
| Autostart | `sudo systemctl enable ccounter` |
| Logi | `journalctl -u ccounter -f` |
| Aktualizacja | `./redeploy.sh` |
| Konfiguracja AP | `sudo ./setup_ap.sh` |
| Przywrócenie Wi-Fi | `sudo ./restore_wifi.sh` |
| API Docs | `http://<IP>:8000/docs` |
