"""
Moduł czujnika indukcyjnego - Pimoroni Automation HAT Mini

Obsługuje wejście IN1 nakładki Automation HAT Mini jako źródło sygnału czujnika indukcyjnego.
"""

import time
import threading
import logging
from typing import Callable, Optional, Literal
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

# Próba importu biblioteki Automation HAT
try:
    import automationhat
    AUTOMATIONHAT_AVAILABLE = True
except ImportError:
    AUTOMATIONHAT_AVAILABLE = False
    logger.warning("Biblioteka automationhat niedostępna - wymagane: pip install automationhat")


@dataclass
class CycleEvent:
    """Reprezentuje zdarzenie cyklu"""
    cycle_number: int
    start_time: datetime
    end_time: datetime
    duration_ms: float


class AutomationHATSensor:
    """
    Klasa obsługująca czujnik indukcyjny podłączony do wejścia IN1 
    nakładki Pimoroni Automation HAT Mini.
    
    Wykrywa cykle otwarcia/zamknięcia na podstawie zmian stanu wejścia IN1.
    Czujnik widzi siłownik w pozycji początkowej (okno zamknięte).
    Cykl rozpoczyna się gdy siłownik opuszcza pole widzenia czujnika
    i kończy się gdy wraca.
    """
    
    def __init__(
        self,
        input_name: Literal["one", "two", "three"] = "one",
        debounce_ms: int = 50,
        active_low: bool = True,
        simulation_mode: bool = False
    ):
        """
        Inicjalizacja czujnika HAT.
        
        Args:
            input_name: Które wejście HAT ('one', 'two', 'three')
            debounce_ms: Czas debouncingu w ms
            active_low: Czy czujnik jest aktywny stanem niskim
            simulation_mode: Wymuś tryb symulacji (do testów)
        """
        self.input_name = input_name
        self.debounce_ms = debounce_ms
        self.active_low = active_low
        self.simulation_mode = simulation_mode or not AUTOMATIONHAT_AVAILABLE
        
        self._cycle_count = 0
        self._cycle_start_time: Optional[datetime] = None
        self._is_running = False
        self._lock = threading.Lock()
        self._callbacks: list[Callable[[CycleEvent], None]] = []
        
        # Stan czujnika
        self._sensor_active = True  # Zakładamy że na starcie siłownik jest widoczny
        self._last_state_change = time.time()
        
        # Referencja do obiektu wejścia HAT
        self._hat_input = None
        
        if not self.simulation_mode:
            self._setup_hat()
        else:
            logger.info(f"Automation HAT sensor (IN{input_name}) działa w trybie symulacji")
    
    def _setup_hat(self):
        """Konfiguracja Automation HAT"""
        try:
            if not AUTOMATIONHAT_AVAILABLE:
                raise ImportError("Biblioteka automationhat nie jest zainstalowana")
            
            # Mapowanie nazw na obiekty wejść
            input_mapping = {
                "one": automationhat.input.one,
                "two": automationhat.input.two,
                "three": automationhat.input.three,
            }
            
            if self.input_name not in input_mapping:
                raise ValueError(f"Nieznane wejście: {self.input_name}. Dostępne: one, two, three")
            
            self._hat_input = input_mapping[self.input_name]
            
            # Odczytaj początkowy stan
            self._sensor_active = self._read_sensor_state()
            logger.info(
                f"Automation HAT skonfigurowany na IN{self.input_name}, "
                f"stan początkowy: {'aktywny' if self._sensor_active else 'nieaktywny'}"
            )
            
        except Exception as e:
            logger.error(f"Błąd konfiguracji Automation HAT: {e}")
            logger.warning("Przełączam na tryb symulacji")
            self.simulation_mode = True
    
    def _read_sensor_state(self) -> bool:
        """Odczytaj stan czujnika (True = siłownik widoczny)"""
        if self.simulation_mode:
            return self._sensor_active
        
        try:
            # Odczytaj stan wejścia (0 = niski, 1 = wysoki)
            raw_state = self._hat_input.read()
            # Jeśli active_low, to stan niski (0) oznacza że czujnik widzi obiekt
            return (raw_state == 0) if self.active_low else (raw_state == 1)
        except Exception as e:
            logger.error(f"Błąd odczytu stanu HAT: {e}")
            return self._sensor_active
    
    def _handle_state_change(self, sensor_active: bool):
        """
        Obsługa zmiany stanu czujnika.
        
        sensor_active=True: siłownik wrócił do pozycji początkowej (koniec cyklu)
        sensor_active=False: siłownik opuścił pozycję początkową (początek cyklu)
        """
        with self._lock:
            if not sensor_active:
                # Siłownik opuścił pole widzenia - początek cyklu
                self._cycle_start_time = datetime.now()
                logger.debug("Początek cyklu - siłownik opuścił pozycję początkową")
            
            elif sensor_active and self._cycle_start_time is not None:
                # Siłownik wrócił - koniec cyklu
                end_time = datetime.now()
                self._cycle_count += 1
                
                duration_ms = (end_time - self._cycle_start_time).total_seconds() * 1000
                
                event = CycleEvent(
                    cycle_number=self._cycle_count,
                    start_time=self._cycle_start_time,
                    end_time=end_time,
                    duration_ms=duration_ms
                )
                
                logger.info(f"Cykl #{self._cycle_count} zakończony, czas: {duration_ms:.1f}ms")
                
                self._cycle_start_time = None
                
                # Wywołaj callbacki
                for callback in self._callbacks:
                    try:
                        callback(event)
                    except Exception as e:
                        logger.error(f"Błąd w callbacku: {e}")
    
    def start(self):
        """Uruchom nasłuchiwanie na wejściu HAT"""
        if self._is_running:
            return
        
        self._is_running = True
        
        if not self.simulation_mode:
            # W trybie Automation HAT używamy pollingu
            self._start_polling_mode()
        else:
            logger.info("Czujnik HAT uruchomiony (tryb symulacji)")
    
    def stop(self):
        """Zatrzymaj nasłuchiwanie"""
        if not self._is_running:
            return
        
        self._is_running = False
        logger.info("Czujnik HAT zatrzymany")
    
    def _start_polling_mode(self):
        """Uruchom tryb pollingu - sprawdza stan HAT co kilka ms"""
        self._polling_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self._polling_thread.start()
        logger.info(f"Czujnik HAT (IN{self.input_name}) uruchomiony w trybie pollingu")
    
    def _polling_loop(self):
        """Pętla pollingu - sprawdza stan IN wejścia co kilka ms"""
        last_state = self._read_sensor_state()
        poll_interval = max(self.debounce_ms / 1000 / 2, 0.01)  # Min 10ms
        
        while self._is_running:
            try:
                current_time = time.time()
                
                # Debouncing
                if (current_time - self._last_state_change) * 1000 < self.debounce_ms:
                    time.sleep(poll_interval)
                    continue
                
                current_state = self._read_sensor_state()
                if current_state != last_state:
                    self._last_state_change = current_time
                    self._sensor_active = current_state
                    self._handle_state_change(current_state)
                    last_state = current_state
                
                time.sleep(poll_interval)
            except Exception as e:
                logger.error(f"Błąd w pętli pollingu HAT: {e}")
                time.sleep(0.1)
    
    def cleanup(self):
        """Zwolnij zasoby"""
        self.stop()
    
    def register_callback(self, callback: Callable[[CycleEvent], None]):
        """
        Zarejestruj callback wywoływany po zakończeniu cyklu.
        
        Args:
            callback: Funkcja przyjmująca CycleEvent jako argument
        """
        self._callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable[[CycleEvent], None]):
        """Wyrejestruj callback"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    @property
    def cycle_count(self) -> int:
        """Aktualna liczba cykli"""
        with self._lock:
            return self._cycle_count
    
    @property
    def is_sensor_active(self) -> bool:
        """Czy czujnik aktualnie widzi siłownik"""
        return self._sensor_active
    
    @property
    def is_cycle_in_progress(self) -> bool:
        """Czy trwa cykl (siłownik poza pozycją początkową)"""
        return self._cycle_start_time is not None
    
    def set_cycle_count(self, count: int):
        """Ustaw licznik cykli (np. po odczycie z pliku)"""
        with self._lock:
            self._cycle_count = count
    
    # Metody do symulacji (do testów)
    def simulate_cycle_start(self):
        """Symuluj rozpoczęcie cyklu"""
        if self.simulation_mode:
            self._sensor_active = False
            self._handle_state_change(False)
    
    def simulate_cycle_end(self):
        """Symuluj zakończenie cyklu"""
        if self.simulation_mode:
            self._sensor_active = True
            self._handle_state_change(True)
    
    def simulate_full_cycle(self, duration_ms: int = 2000):
        """Symuluj pełny cykl z określonym czasem trwania"""
        if self.simulation_mode:
            self.simulate_cycle_start()
            time.sleep(duration_ms / 1000)
            self.simulate_cycle_end()
