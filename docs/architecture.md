# Architektura systemu Windows_CCounter

## 📐 Przegląd

System Windows_CCounter to modułowa aplikacja Python do monitorowania cykli pracy siłownika. Składa się z czterech głównych warstw:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         WARSTWA PREZENTACJI                         │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐  │
│  │      GUI (Tkinter)          │  │      REST API (FastAPI)     │  │
│  │   touchscreen_gui.py        │  │    fastapi_server.py        │  │
│  └─────────────────────────────┘  └─────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                         WARSTWA LOGIKI                              │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐  │
│  │    Session Manager          │  │     Cycle Counter           │  │
│  │   session_manager.py        │  │    (w main.py)              │  │
│  └─────────────────────────────┘  └─────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                         WARSTWA DANYCH                              │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐  │
│  │     CSV Handler             │  │     Config (YAML)           │  │
│  │    csv_handler.py           │  │    config.yaml              │  │
│  └─────────────────────────────┘  └─────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                         WARSTWA HARDWARE                            │
│  ┌─────────────────────────────┐                                    │
│  │    Inductive Sensor         │                                    │
│  │   inductive_sensor.py       │                                    │
│  │      (GPIO / Symulacja)     │                                    │
│  └─────────────────────────────┘                                    │
└─────────────────────────────────────────────────────────────────────┘
```

## 🧩 Komponenty

### 1. InductiveSensor (`src/sensor/inductive_sensor.py`)

**Odpowiedzialność:** Obsługa czujnika indukcyjnego podłączonego do GPIO Raspberry Pi.

```
                    ┌─────────────────┐
                    │ InductiveSensor │
                    ├─────────────────┤
   GPIO Pin ──────▶ │ - gpio_pin      │
                    │ - debounce_ms   │
                    │ - simulation    │
                    ├─────────────────┤
                    │ + start()       │
                    │ + stop()        │──────▶ CycleEvent
                    │ + register_cb() │
                    └─────────────────┘
```

**Kluczowe cechy:**
- Wykrywanie zbocza sygnału (rising/falling edge)
- Debouncing programowy
- Tryb symulacji dla testów (bez GPIO)
- System callbacków dla powiadomień o cyklach

**Stany czujnika:**
```
    Siłownik widoczny          Siłownik niewidoczny
    (pozycja początkowa)       (cykl w trakcie)
          │                           │
          ▼                           ▼
    ┌───────────┐               ┌───────────┐
    │  ACTIVE   │──── START ───▶│ INACTIVE  │
    │           │◀──── END ─────│           │
    └───────────┘               └───────────┘
          │                           │
          └─── Cykl zakończony ───────┘
                      │
                      ▼
               CycleEvent {
                 cycle_number,
                 start_time,
                 end_time,
                 duration_ms
               }
```

### 2. SessionManager (`src/data/session_manager.py`)

**Odpowiedzialność:** Zarządzanie sesjami pomiarowymi (START/STOP).

```
┌─────────────────────────────────────────────────────────┐
│                    SessionManager                        │
├─────────────────────────────────────────────────────────┤
│  Stan: STOPPED                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Brak aktywnej sesji                            │   │
│  │  Cykle NIE są zapisywane                        │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                    START_SESSION()                      │
│                         │                               │
│                         ▼                               │
│  Stan: RECORDING                                        │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Sesja aktywna: session_20260401_143022.csv     │   │
│  │  Cykle SĄ zapisywane do pliku                   │   │
│  │  cycle_number resetowany do 1                   │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                    STOP_SESSION()                       │
│                         │                               │
│                         ▼                               │
│  Stan: STOPPED (plik zamknięty)                         │
└─────────────────────────────────────────────────────────┘
```

**Metody:**
| Metoda | Opis |
|--------|------|
| `start_session()` | Tworzy nowy plik CSV, aktywuje nagrywanie |
| `stop_session()` | Kończy sesję, zwraca podsumowanie |
| `add_cycle()` | Zapisuje cykl (tylko gdy sesja aktywna) |
| `is_session_active` | Property - czy sesja trwa |

### 3. CSVHandler (`src/data/csv_handler.py`)

**Odpowiedzialność:** Niskopoziomowy zapis/odczyt plików CSV.

```
┌─────────────────────────────────────────┐
│              CSVHandler                  │
├─────────────────────────────────────────┤
│  csv_path: Path                         │
│  _records_cache: deque[CycleRecord]     │
│  _lock: RLock                           │
├─────────────────────────────────────────┤
│  + add_cycle() ──────▶ Zapis do pliku   │
│  + get_all_records()                    │
│  + get_statistics()                     │
│  + export_to_path()                     │
└─────────────────────────────────────────┘
```

**Format pliku CSV:**
```csv
timestamp,cycle_number,cycle_duration_ms
2026-04-01 14:30:22,1,2340
2026-04-01 14:32:45,2,2280
```

### 4. FastAPI Server (`src/api/fastapi_server.py`)

**Odpowiedzialność:** REST API do zdalnego dostępu.

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Server                        │
│                    Port: 8000                            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  /api/session/start  ◀────── POST ────── Klient        │
│  /api/session/stop   ◀────── POST ────── Klient        │
│  /api/session/status ◀────── GET  ────── Klient        │
│                                                         │
│  /api/cycles         ◀────── GET  ────── Klient        │
│  /api/stats          ◀────── GET  ────── Klient        │
│  /api/export/csv     ◀────── GET  ────── Klient        │
│                                                         │
│  /api/simulate/cycle ◀────── POST ────── Klient        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 5. GUI (`src/gui/touchscreen_gui.py`)

**Odpowiedzialność:** Interfejs użytkownika dla ekranu dotykowego.

```
┌─────────────────────────────────────────────────────────────────┐
│  🏭 Windows CCounter          🔴 REC: session_xxx    ● CZUJNIK │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────┬───────────────────────┐              │
│  │    LICZBA CYKLI       │    OSTATNI CYKL       │              │
│  │                       │                       │              │
│  │        42             │      2340 ms          │              │
│  │                       │                       │              │
│  └───────────────────────┴───────────────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│  📜 Ostatnie cykle                          ┌─────────────────┐ │
│  ┌────┬──────────────┬────────┐             │   ▶ START       │ │
│  │ #  │ Czas         │ ms     │             ├─────────────────┤ │
│  ├────┼──────────────┼────────┤             │   ⏹ STOP        │ │
│  │ 42 │ 14:32:45     │ 2340   │             ├─────────────────┤ │
│  │ 41 │ 14:30:22     │ 2280   │             │ 💾 Eksport USB  │ │
│  │ 40 │ 14:28:10     │ 2310   │             ├─────────────────┤ │
│  └────┴──────────────┴────────┘             │ 📊 Statystyki   │ │
│                                             └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## 🔄 Przepływ danych

### Rejestracja cyklu (sesja aktywna)

```
┌──────────┐    GPIO     ┌─────────────────┐   CycleEvent   ┌─────────────────┐
│ Czujnik  │────────────▶│ InductiveSensor │───────────────▶│ CycleCounterApp │
│ fizyczny │   sygnał    │                 │   callback     │   (main.py)     │
└──────────┘             └─────────────────┘                └────────┬────────┘
                                                                     │
                                                                     ▼
┌──────────┐             ┌─────────────────┐   add_cycle()  ┌─────────────────┐
│ Plik CSV │◀────────────│   CSVHandler    │◀───────────────│ SessionManager  │
│          │   zapis     │                 │                │ (jeśli aktywna) │
└──────────┘             └─────────────────┘                └─────────────────┘
```

### Aktualizacja GUI

```
┌─────────────────┐   co 500ms    ┌─────────────────┐
│      GUI        │──────────────▶│ SessionManager  │
│ _update_display │               │ get_latest()    │
└────────┬────────┘               └────────┬────────┘
         │                                 │
         │◀────────── dane ────────────────┘
         │
         ▼
    Aktualizacja:
    - Licznik cykli
    - Czas ostatniego cyklu
    - Status sesji
    - Tabela historii
```

## 🧵 Model wątkowy

```
┌─────────────────────────────────────────────────────────────────┐
│                        GŁÓWNY PROCES                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ WĄTEK GŁÓWNY (Main Thread)                              │   │
│  │                                                         │   │
│  │  - Tkinter mainloop()                                   │   │
│  │  - Obsługa GUI                                          │   │
│  │  - _update_display() co 500ms                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ WĄTEK API (daemon=True)                                 │   │
│  │                                                         │   │
│  │  - Uvicorn server                                       │   │
│  │  - FastAPI endpoints                                    │   │
│  │  - asyncio event loop                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ WĄTEK GPIO (tylko na Raspberry Pi)                      │   │
│  │                                                         │   │
│  │  - RPi.GPIO event detection                             │   │
│  │  - Callback przy zmianie stanu                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Synchronizacja:**
- `threading.RLock` w SessionManager i CSVHandler
- Thread-safe callbacks przez kolejkę zdarzeń

## 📁 Struktura plików

```
Windows_CCounter/
├── main.py                      # Punkt wejścia, CycleCounterApp
├── config.yaml                  # Konfiguracja
├── requirements.txt             # Zależności
│
├── src/
│   ├── __init__.py
│   │
│   ├── sensor/
│   │   ├── __init__.py
│   │   └── inductive_sensor.py  # Obsługa GPIO
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── csv_handler.py       # Zapis CSV
│   │   └── session_manager.py   # Zarządzanie sesjami
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── fastapi_server.py    # REST API
│   │
│   └── gui/
│       ├── __init__.py
│       └── touchscreen_gui.py   # Interfejs Tkinter
│
├── data/
│   └── session_*.csv            # Pliki sesji
│
├── logs/
│   └── system.log               # Logi
│
└── docs/
    └── architecture.md          # Ten plik
```

## 🔌 Interfejsy między komponentami

### CycleEvent (sensor → app)
```python
@dataclass
class CycleEvent:
    cycle_number: int
    start_time: datetime
    end_time: datetime
    duration_ms: float
```

### CycleRecord (session_manager → csv_handler)
```python
@dataclass
class CycleRecord:
    timestamp: str
    cycle_number: int
    cycle_duration_ms: float
```

### SessionInfo (session_manager → gui/api)
```python
@dataclass
class SessionInfo:
    session_id: str
    start_time: datetime
    end_time: Optional[datetime]
    csv_filename: str
    cycle_count: int
    is_active: bool
```

## 🔧 Konfiguracja

System konfigurowany przez `config.yaml`:

```yaml
sensor:
  gpio_pin: 17          # Pin GPIO
  debounce_ms: 50       # Debouncing

data:
  csv_path: "./data"    # Katalog danych

api:
  host: "0.0.0.0"
  port: 8000

gui:
  enabled: true
  fullscreen: false
  window_width: 800
  window_height: 600
```

## 🚀 Tryby pracy

| Tryb | GPIO | GUI | API | Użycie |
|------|------|-----|-----|--------|
| Produkcja (RPi) | ✅ Real | ✅ Fullscreen | ✅ | Raspberry Pi z czujnikiem |
| Symulacja (PC) | ❌ Fake | ✅ Window | ✅ | Testowanie na PC |
| Headless | ✅ Real | ❌ | ✅ | Serwer bez ekranu |
| API Only | ❌ Fake | ❌ | ✅ | Tylko REST API |
