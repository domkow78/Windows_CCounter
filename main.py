"""
Windows_CCounter - Główny punkt wejścia systemu

System pomiarowy do zliczania cykli otwarcia/zamknięcia okien suszarki.
"""

import sys
import signal
import logging
import asyncio
import threading
from pathlib import Path
from datetime import datetime

import yaml

# Import modułów projektu
from src.sensor import InductiveSensor
from src.sensor.inductive_sensor import CycleEvent
from src.data import CSVHandler, SessionManager
from src.api import create_app, APIServer
from src.gui import CycleCounterGUI


# === Konfiguracja logowania ===

def setup_logging(log_level: str = "INFO", log_file: str = "./logs/system.log"):
    """Konfiguracja systemu logowania"""
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding="utf-8")
        ]
    )


# === Wczytywanie konfiguracji ===

def load_config(config_path: str = "config.yaml") -> dict:
    """Wczytaj konfigurację z pliku YAML"""
    config_file = Path(config_path)
    
    if not config_file.exists():
        logging.warning(f"Plik konfiguracyjny {config_path} nie istnieje, używam domyślnych wartości")
        return get_default_config()
    
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_default_config() -> dict:
    """Zwróć domyślną konfigurację"""
    return {
        "sensor": {
            "gpio_pin": 17,
            "debounce_ms": 50,
            "pull_up": True,
            "active_low": True
        },
        "data": {
            "data_dir": "./data",
            "backup_enabled": True,
            "backup_path": "./data/backup/",
            "max_records_in_memory": 1000
        },
        "api": {
            "host": "0.0.0.0",
            "port": 8000,
            "enable_cors": True
        },
        "gui": {
            "enabled": True,
            "fullscreen": False,
            "window_width": 800,
            "window_height": 480,
            "refresh_interval_ms": 500
        },
        "usb": {
            "mount_path": "/media/usb",
            "auto_detect": True
        },
        "logging": {
            "level": "INFO",
            "file": "./logs/system.log"
        }
    }


# === Główna klasa aplikacji ===

class CycleCounterApp:
    """
    Główna klasa aplikacji zarządzająca wszystkimi komponentami.
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Komponenty
        self.sensor: InductiveSensor = None
        self.csv_handler: CSVHandler = None
        self.session_manager: SessionManager = None
        self.gui: CycleCounterGUI = None
        
        # Flagi
        self._is_running = False
        self._shutdown_event = asyncio.Event()
        
        # Wątki
        self._api_thread: threading.Thread = None
        self._gui_thread: threading.Thread = None
    
    def _init_session_manager(self):
        """Inicjalizacja managera sesji"""
        data_config = self.config.get("data", {})
        
        # SessionManager zarządza sesjami pomiarowymi i plikami CSV
        self.session_manager = SessionManager(
            data_dir=data_config.get("data_dir", "./data"),
            backup_enabled=data_config.get("backup_enabled", True),
            backup_path=data_config.get("backup_path", "./data/backup/")
        )
        
        # csv_handler nie jest już używany - zostawiamy None
        self.csv_handler = None
        
        self.logger.info(f"SessionManager zainicjalizowany, katalog: {data_config.get('data_dir', './data')}")
    
    def _init_sensor(self):
        """Inicjalizacja czujnika"""
        sensor_config = self.config.get("sensor", {})
        
        self.sensor = InductiveSensor(
            gpio_pin=sensor_config.get("gpio_pin", 17),
            debounce_ms=sensor_config.get("debounce_ms", 50),
            pull_up=sensor_config.get("pull_up", True),
            active_low=sensor_config.get("active_low", True)
        )
        
        # Licznik cykli sensora zaczyna od 0
        # Każda sesja ma własny licznik w SessionManager
        
        # Zarejestruj callback zapisu cykli
        self.sensor.register_callback(self._on_cycle_complete)
        
        self.logger.info("Czujnik zainicjalizowany")
    
    def _on_cycle_complete(self, event: CycleEvent):
        """Callback wywoływany po zakończeniu cyklu"""
        # Zapisz do sesji jeśli aktywna
        if self.session_manager and self.session_manager.is_session_active:
            self.session_manager.add_cycle(
                cycle_number=event.cycle_number,
                duration_ms=event.duration_ms,
                timestamp=event.end_time
            )
            self.logger.info(f"Cykl #{self.session_manager.session_cycle_count} zapisany do sesji ({event.duration_ms:.1f}ms)")
        else:
            # Brak aktywnej sesji - cykl nie jest zapisywany
            self.logger.debug(f"Cykl pominięty - brak aktywnej sesji")
    
    def _run_api_server(self):
        """Uruchom serwer API w osobnym wątku"""
        import uvicorn
        
        api_config = self.config.get("api", {})
        usb_config = self.config.get("usb", {})
        
        app = create_app(
            csv_handler=self.csv_handler,
            sensor=self.sensor,
            session_manager=self.session_manager,
            enable_cors=api_config.get("enable_cors", True),
            usb_mount_path=usb_config.get("mount_path", "/media/usb")
        )
        
        config = uvicorn.Config(
            app,
            host=api_config.get("host", "0.0.0.0"),
            port=api_config.get("port", 8000),
            log_level="info"
        )
        
        server = uvicorn.Server(config)
        
        # Uruchom w nowej pętli asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.serve())
    
    def _run_gui(self):
        """Uruchom GUI w osobnym wątku"""
        gui_config = self.config.get("gui", {})
        usb_config = self.config.get("usb", {})
        
        self.gui = CycleCounterGUI(
            csv_handler=self.csv_handler,
            sensor=self.sensor,
            session_manager=self.session_manager,
            fullscreen=gui_config.get("fullscreen", False),
            window_width=gui_config.get("window_width", 800),
            window_height=gui_config.get("window_height", 480),
            refresh_interval_ms=gui_config.get("refresh_interval_ms", 500),
            usb_mount_path=usb_config.get("mount_path", "/media/usb")
        )
        
        self.gui.start()
    
    def start(self):
        """Uruchom wszystkie komponenty"""
        self.logger.info("=" * 50)
        self.logger.info("Uruchamianie Windows CCounter...")
        self.logger.info("=" * 50)
        
        self._is_running = True
        
        # Inicjalizacja komponentów
        self._init_session_manager()
        self._init_sensor()
        
        # Uruchom czujnik
        self.sensor.start()
        
        # Uruchom serwer API w osobnym wątku
        self._api_thread = threading.Thread(target=self._run_api_server, daemon=True)
        self._api_thread.start()
        self.logger.info(f"API Server uruchomiony na porcie {self.config.get('api', {}).get('port', 8000)}")
        
        # Uruchom GUI jeśli włączone
        gui_config = self.config.get("gui", {})
        if gui_config.get("enabled", True):
            self.logger.info("Uruchamianie GUI...")
            self._run_gui()  # To zablokuje wątek główny (mainloop Tkinter)
        else:
            # Jeśli GUI wyłączone, trzymaj proces przy życiu
            self.logger.info("GUI wyłączone, system działa w tle...")
            try:
                while self._is_running:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
    
    def stop(self):
        """Zatrzymaj wszystkie komponenty"""
        self.logger.info("Zatrzymywanie systemu...")
        self._is_running = False
        
        if self.sensor:
            self.sensor.cleanup()
        
        if self.gui:
            self.gui.stop()
        
        # Utwórz backup przy zamknięciu
        if self.csv_handler:
            self.csv_handler.create_backup()
        
        self.logger.info("System zatrzymany")


# === Punkt wejścia ===

def main():
    """Główna funkcja uruchamiająca aplikację"""
    # Wczytaj konfigurację
    config = load_config()
    
    # Konfiguracja logowania
    log_config = config.get("logging", {})
    setup_logging(
        log_level=log_config.get("level", "INFO"),
        log_file=log_config.get("file", "./logs/system.log")
    )
    
    logger = logging.getLogger(__name__)
    
    # Utwórz i uruchom aplikację
    app = CycleCounterApp(config)
    
    # Obsługa sygnałów
    def signal_handler(sig, frame):
        logger.info(f"Otrzymano sygnał {sig}, zamykanie...")
        app.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        app.start()
    except Exception as e:
        logger.error(f"Błąd krytyczny: {e}", exc_info=True)
        app.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
