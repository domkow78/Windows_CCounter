# Windows_CCounter

System pomiarowy do zliczania cykli otwarcia/zamknięcia okien suszarki dla P.K.

## 📋 Opis systemu

System oparty na **Raspberry Pi** służący do monitorowania i rejestrowania cykli pracy siłownika sterującego oknami suszarki. System automatycznie zlicza cykle otwarcia-zamknięcia oraz mierzy czas trwania każdego cyklu. Aplikacja udostępnia lokalne GUI **Tkinter**, interfejs webowy **NiceGUI** oraz REST API **FastAPI**.

## 🎯 Założenia funkcjonalne

### Pomiar cykli
- Zliczanie ilości cykli otwarcia-zamknięcia okien suszarki
- Pomiar czasu pomiędzy impulsami z czujnika indukcyjnego
- Wykrywanie pozycji siłownika za pomocą czujnika indukcyjnego

### Zasada działania
1. Czujnik indukcyjny wykrywa siłownik w pozycji początkowej (okno zamknięte)
2. Siłownik wykonuje cykl pracy - otwiera okno
3. Siłownik wraca do pozycji początkowej - zamyka okno
4. Czujnik indukcyjny ponownie wykrywa siłownik → cykl zakończony
5. System rejestruje czas trwania cyklu

### Sesje pomiarowe
System wykorzystuje **sesje pomiarowe** - dane są zapisywane tylko gdy sesja jest aktywna:

1. **START** - rozpoczyna nową sesję, tworzy nowy plik CSV z timestampem
2. **STOP** - kończy sesję, zamyka plik CSV
3. Cykle są rejestrowane **tylko podczas aktywnej sesji**

Każda sesja tworzy osobny plik CSV np. `session_20260401_143022.csv`

### Rejestracja danych
Dane zapisywane są do pliku **CSV** zawierającego:
| Pole | Opis |
|------|------|
| `timestamp` | Data i godzina zdarzenia |
| `cycle_number` | Numer cyklu w ramach sesji |
| `cycle_duration_ms` | Czas trwania cyklu w milisekundach |

## 🏗️ Architektura systemu

```
┌─────────────────────────────────────────────────────────────┐
│                      Raspberry Pi                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Czujnik    │───▶│   Moduł      │───▶│   Zapis      │  │
│  │  Indukcyjny  │    │   Pomiarowy  │    │   CSV        │  │
│  │   (GPIO)     │    │              │    │              │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                              │                              │
│                              ▼                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Ekran      │◀──▶│   GUI        │    │   FastAPI    │  │
│  │   Dotykowy   │    │  (Tkinter)   │    │   Server     │  │
│  │   LCD        │    └──────────────┘    │   (REST)     │  │
│  └──────────────┘                         └──────┬───────┘  │
│                                                  │          │
│                                           ┌──────▼───────┐  │
│                                           │   NiceGUI    │  │
│                                           │   Web UI     │  │
│                                           └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 💻 Komponenty software

### 1. Moduł czujnika indukcyjnego (wieloplatformowy)
- **Obsługa dwóch backendów sprzętowych:**
  - GPIO bezpośrednie (domyślnie) - `InductiveSensor`
  - Automation HAT Mini (zalecane) - `AutomationHATSensor` z wejściem IN1
- Nasłuchiwanie sygnałów z detektorem zmian stanu
- Pomiar czasu między impulsami (rising/falling edge)
- Obsługa debouncingu sygnału
- System callbacków dla powiadomień o cyklach
- **Factory pattern** - `create_sensor_from_config()` do wyboru implementacji

### 2. Moduł zapisu danych
- **SessionManager** - zarządzanie sesjami pomiarowymi
- Każda sesja = osobny plik CSV z timestampem
- Zapis tylko podczas aktywnej sesji
- Backup danych

### 3. FastAPI Server
- **GET** `/api/cycles` - pobranie listy cykli (z filtrowaniem po dacie)
- **GET** `/api/cycles/latest` - ostatni cykl
- **GET** `/api/stats` - statystyki (suma cykli, średni czas, itp.)
- **GET** `/api/export/csv` - pobranie pliku CSV
- **GET** `/api/export/session` - pobranie pliku aktualnej sesji
- **GET** `/api/status` - status systemu

### 4. Web UI (NiceGUI)
- Dashboard dostępny w przeglądarce na osobnym porcie
- START/STOP sesji z poziomu WWW
- Podgląd statusu sesji, czujnika, licznika i ostatniego cyklu
- Tabela ostatnich cykli i szybkie statystyki sesji
- Pobieranie bieżącej sesji CSV na dysk
- Panel historii zapisanych sesji i tryb symulacji na PC

### 5. GUI (ekran dotykowy)
- **Przycisk START** - rozpoczyna nową sesję pomiarową
- **Przycisk STOP** - kończy sesję z podsumowaniem
- Wyświetlanie aktualnej liczby cykli w sesji
- Wyświetlanie czasu ostatniego cyklu
- Status sesji (🔴 REC / ⏹ STOP)
- Tabela historii cykli
- Przycisk eksportu na pendrive
- Podgląd statystyk

## 🔌 Hardware

### Wymagane komponenty
- **Raspberry Pi** (3B+/4/5)
- **Czujnik indukcyjny** (NPN/PNP, 3-przewodowy)
- **Pimoroni Automation HAT Mini** - zalecana nakładka wejściowa dla czujnika
- **Wyświetlacz LCD** z obsługą dotyku (np. 3.5"/5"/7")
- Zasilacz 5V
- Karta microSD

### Podłączenie czujnika
```
Czujnik E2S-H4N1 5V         Automation HAT Mini
──────────────────         ───────────────────
  VCC  ──────────────▶  5V zasilania czujnika
  GND  ──────────────▶  GND
  OUT  ──────────────▶  IN1
```

> ⚠️ **Uwaga:** W docelowej instalacji zalecane jest użycie nakładki **Automation HAT Mini**
> jako interfejsu dla czujnika **E2S-H4N1 4 mm 5V**. Pozwala to uniknąć bezpośredniego
> podawania sygnału na GPIO Raspberry Pi i upraszcza okablowanie.

> ℹ️ Szczegóły wariantu z nakładką opisano w pliku `pimoroni.md`.

## 📁 Struktura projektu

```
Windows_CCounter/
├── .gitignore              # Ignorowane pliki Git
├── README.md               # Dokumentacja projektu
├── pimoroni.md             # Opis użycia Automation HAT Mini z czujnikiem E2S-H4N1
├── requirements.txt        # Zależności Python
├── config.yaml             # Konfiguracja systemu
├── main.py                 # Główny punkt wejścia
├── src/
│   ├── __init__.py
│   ├── sensor/
│   │   ├── __init__.py
│   │   ├── inductive_sensor.py      # Obsługa czujnika GPIO bezpośrednie
│   │   ├── automation_hat_sensor.py # Obsługa Automation HAT Mini (IN1)
│   │   └── sensor_factory.py        # Factory do wyboru implementacji
│   ├── data/
│   │   ├── __init__.py
│   │   ├── csv_handler.py        # Zapis/odczyt danych CSV
│   │   └── session_manager.py    # Zarządzanie sesjami pomiarowymi
│   ├── api/
│   │   ├── __init__.py
│   │   └── fastapi_server.py     # REST API (FastAPI + Uvicorn)
│   ├── web/
│   │   ├── __init__.py
│   │   └── nicegui_app.py        # Interfejs webowy NiceGUI
│   └── gui/
│       ├── __init__.py
│       └── touchscreen_gui.py    # Interfejs Tkinter dla ekranu dotykowego
├── data/
│   └── session_*.csv       # Pliki sesji pomiarowych
├── logs/
│   └── system.log          # Logi systemowe
├── docs/
│   ├── architecture.md     # Dokumentacja architektury
│   └── deployment.md       # Instrukcje deployment na Raspberry Pi
└── venv/                   # Środowisko wirtualne Python
```

## 🚀 Instalacja i uruchomienie

### Windows (PowerShell)
```powershell
# Klonowanie repozytorium
git clone https://github.com/user/Windows_CCounter.git
cd Windows_CCounter

# Utworzenie środowiska wirtualnego
python -m venv venv

# Aktywacja środowiska
.\venv\Scripts\Activate.ps1

# Instalacja zależności
pip install -r requirements.txt

# Uruchomienie
python main.py

# Dostęp po uruchomieniu
# Web UI:  http://localhost:8080
# REST API: http://localhost:8000
```

### Linux / Raspberry Pi
```bash
# Klonowanie repozytorium
git clone https://github.com/user/Windows_CCounter.git
cd Windows_CCounter

# Utworzenie środowiska wirtualnego
python3 -m venv venv

# Aktywacja środowiska
source venv/bin/activate

# Instalacja zależności podstawowych
pip install -r requirements.txt

# Instalacja GPIO (tylko na Raspberry Pi)
pip install RPi.GPIO

# Instalacja Automation HAT Mini (jeśli używasz HAT zamiast GPIO)
# Opcja 1: Z repozytorium pimoroni
sudo apt install python3-automationhat
# lub
pip install automationhat

# Opcja 2: Instalacja ze źródła
git clone https://github.com/pimoroni/automation-hat.git
cd automation-hat
./install.sh
cd ../Windows_CCounter

# Uruchomienie
python main.py

# Dostęp po uruchomieniu
# Web UI:  http://<IP_RPI>:8080
# REST API: http://<IP_RPI>:8000
```

## ⚙️ Konfiguracja

### Wybór backendu czujnika

Edytuj plik `config.yaml`:

```yaml
sensor:
  # Wybór backendu: "gpio" lub "automationhat"
  hardware_backend: "gpio"
  
  # Dla GPIO bezpośredniego:
  gpio_pin: 17              # Numer pinu GPIO
  pull_up: true
  
  # Dla Automation HAT Mini:
  automation_hat_input: "one"  # "one", "two" lub "three"
  
  # Wspólne ustawienia:
  debounce_ms: 50           # Czas debouncingu
  active_low: true          # Aktywny stan niski (NPN)
```

### Uruchomienie z Automation HAT Mini

```bash
# Zmień w config.yaml
sensor:
  hardware_backend: "automationhat"
  automation_hat_input: "one"

# Uruchom aplikację
python main.py
```

### Tryb symulacji (Windows / testy)

Na Windows system automatycznie startuje w trybie symulacji.
Można testować wszystkie funkcje bez fizycznego GPIO.

Aby wymusić tryb symulacji na Raspberry Pi, dodaj do `config.yaml`:
```yaml
sensor:
  simulation_mode: true
```

## ⚡ Szybki start

Po uruchomieniu `python main.py` aplikacja standardowo startuje w trzech warstwach:

- **FastAPI** na porcie `8000`
- **NiceGUI Web UI** na porcie `8080`
- **Tkinter GUI** lokalnie, jeśli dostępny jest ekran i `gui.enabled=true`

Na Windows system zwykle działa w **trybie symulacji**, więc można testować działanie bez GPIO.

Na Raspberry Pi zalecany wariant produkcyjny zakłada podłączenie czujnika
**E2S-H4N1 4 mm 5V** do wejścia **IN1** nakładki **Automation HAT Mini**.

Obecna implementacja repozytorium nadal wykorzystuje bezpośrednią obsługę GPIO jako ścieżkę bazową.
Wariant z **Automation HAT Mini / IN1** jest opisanym i zalecanym kierunkiem integracji sprzętowej.

## 📦 Zależności

Plik `requirements.txt`:
```
# Core
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-dateutil>=2.8.2
aiofiles>=23.2.1
PyYAML>=6.0.1
nicegui>=1.4.0
python-multipart>=0.0.6

# Raspberry Pi GPIO (zainstaluj ręcznie na Raspberry Pi)
# RPi.GPIO>=0.7.1

# Opcjonalnie: biblioteka nakładki Automation HAT Mini
# automationhat

# GUI - tkinter jest wbudowany w Python
```

## 🔧 Konfiguracja

Plik `config.yaml`:
```yaml
sensor:
  gpio_pin: 17              # Numer pinu GPIO dla czujnika indukcyjnego
  debounce_ms: 50           # Czas debouncingu w milisekundach
  pull_up: true             # Włącz wewnętrzny pull-up rezystor
  active_low: true          # Czujnik aktywny stanem niskim (NPN)

data:
  data_dir: "./data"        # Katalog na pliki sesji (session_*.csv)
  backup_enabled: true
  backup_path: "./data/backup/"
  max_records_in_memory: 1000

api:
  host: "0.0.0.0"
  port: 8000
  enable_cors: true

gui:
  enabled: true
  fullscreen: false         # Ustaw na true dla produkcji
  window_width: 800
  window_height: 600        # Wysokość okna
  refresh_interval_ms: 500

web:
  enabled: true             # Interfejs webowy NiceGUI
  host: "0.0.0.0"
  port: 8080

usb:
  mount_path: "/media/usb"  # Ścieżka montowania pendrive
  auto_detect: true

logging:
  level: "INFO"
  file: "./logs/system.log"
```

## 📊 Format pliku CSV

Każda sesja tworzy osobny plik np. `session_20260401_143022.csv`:

```csv
timestamp,cycle_number,cycle_duration_ms
2026-04-01 14:30:22,1,2340
2026-04-01 14:32:45,2,2280
2026-04-01 14:35:10,3,2310
```

> **Uwaga:** `cycle_number` jest numerem cyklu w ramach sesji (zaczyna od 1 w każdej nowej sesji)

## 🌐 API Endpoints

| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET | `/` | Strona główna API (status) |
| GET | `/api/cycles` | Lista wszystkich cykli |
| GET | `/api/cycles?from=2026-04-01&to=2026-04-02` | Cykle z zakresu dat |
| GET | `/api/cycles?limit=100` | Ostatnie N cykli |
| GET | `/api/cycles/latest` | Ostatni zarejestrowany cykl |
| GET | `/api/cycles/last/{n}` | Ostatnie N cykli |
| GET | `/api/stats` | Statystyki systemu |
| GET | `/api/status` | Status systemu (czujnik, uptime) |
| GET | `/api/export/csv` | Pobierz plik CSV (download) |
| GET | `/api/export/session` | Pobierz plik bieżącej sesji |
| GET | `/api/export/csv/content` | Zawartość CSV jako tekst |
| POST | `/api/usb/export` | Eksport na pendrive |
| GET | `/api/usb/status` | Status pendrive (zamontowany?) |
| POST | `/api/backup` | Utwórz backup danych |
| **Sesje** | | |
| POST | `/api/session/start` | Rozpocznij nową sesję pomiarową |
| POST | `/api/session/stop` | Zakończ aktywną sesję |
| GET | `/api/session/status` | Status bieżącej sesji |
| GET | `/api/session/list` | Lista wszystkich plików sesji |
| **Symulacja** | | |
| POST | `/api/simulate/cycle` | Symuluj pojedynczy cykl |
| POST | `/api/simulate/cycles/{n}` | Symuluj N cykli |

### Przykłady odpowiedzi API

**GET /api/status**
```json
{
  "status": "running",
  "sensor_active": true,
  "cycle_in_progress": false,
  "current_cycle_count": 1523,
  "uptime_seconds": 3600.5,
  "last_cycle_time": "2026-04-01 12:30:45"
}
```

**GET /api/stats**
```json
{
  "total_cycles": 1523,
  "avg_duration_ms": 2310.5,
  "min_duration_ms": 1850.0,
  "max_duration_ms": 3200.0,
  "first_cycle_time": "2026-03-01 08:00:00",
  "last_cycle_time": "2026-04-01 12:30:45"
}
```

## 🌐 Funkcje Web UI

Interfejs NiceGUI dostępny w przeglądarce:

### Dashboard
- Status sesji `🔴 REC` / `⏹ STOP`
- Osobny panel przycisków **START** / **STOP**
- Aktualna liczba cykli w sesji
- Status czujnika i podgląd ostatniego cyklu
- Tabela ostatnich cykli i szybkie statystyki
- Przycisk **Pobierz sesję** zapisujący CSV na dysk użytkownika

### Historia i eksport
- Lista zapisanych plików `session_*.csv`
- Pobieranie wybranych plików CSV
- Eksport aktualnej sesji bezpośrednio z dashboardu

### Tryb symulacji
- Przyciski do symulacji pojedynczych i wielokrotnych cykli
- Przydatne do testów na Windows bez fizycznego GPIO

## 📱 Funkcje GUI

Interfejs Tkinter dla ekranu dotykowego LCD:

### Panel główny
- Duży licznik cykli (widoczny z daleka)
- Czas ostatniego cyklu w milisekundach
- Status czujnika (aktywny/nieaktywny) z kolorowym wskaźnikiem
- **Status sesji** - `🔴 REC` lub `⏹ STOP`

### Przyciski sterowania
| Przycisk | Funkcja |
|----------|--------|
| **▶ START** | Rozpoczyna nową sesję, tworzy plik CSV, resetuje licznik do 0 |
| **⏹ STOP** | Kończy sesję, pokazuje podsumowanie, licznik zatrzymuje się na ostatniej wartości |
| **💾 Eksport USB** | Zapisuje dane na pendrive |
| **📊 Statystyki** | Wyświetla statystyki sesji |

> **Uwaga:** Cykle są zliczane i zapisywane **tylko podczas aktywnej sesji** (po START, przed STOP). Po STOP licznik pokazuje ostatnią wartość z zakończonej sesji.

### Tabela historii
- Ostatnie 10 cykli z bieżącej sesji
- Automatyczne odświeżanie co 500ms

### Tryb symulacji

Na komputerze bez GPIO (Windows/Mac) system działa w trybie symulacji - czujnik nie jest podłączony, ale można testować GUI i API.

**Symulacja cykli przez API:**
```powershell
# Pojedynczy cykl (2 sekundy)
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/simulate/cycle?duration_ms=2000"

# 5 cykli po 1 sekundzie
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/simulate/cycles/5?duration_ms=1000"
```

## 🖥️ Tryby uruchomienia

| Tryb | Tkinter GUI | Web UI | API | Użycie |
|------|-------------|--------|-----|--------|
| Pełny | ✅ | ✅ | ✅ | Produkcja na Raspberry Pi |
| Bez GUI lokalnego | ❌ | ✅ | ✅ | Serwer headless z WWW |
| Symulacja | ✅ | ✅ | ✅ | Testy na PC bez GPIO |

Konfiguracja w `config.yaml`:
```yaml
gui:
  enabled: true   # false = tryb bez GUI

web:
  enabled: true   # false = wyłącza interfejs NiceGUI
```

## � Dokumentacja

- [README.md](README.md) - Główna dokumentacja projektu
- [docs/architecture.md](docs/architecture.md) - Szczegółowa architektura systemu

## �📄 Licencja

MIT License

## 👥 Autorzy

P.K.
