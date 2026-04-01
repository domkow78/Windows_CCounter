"""
Moduł czujnika indukcyjnego - obsługa GPIO Raspberry Pi
"""

import time
import threading
import logging
from typing import Callable, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

# Próba importu GPIO - będzie działać tylko na Raspberry Pi
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    logger.warning("RPi.GPIO niedostępne - tryb symulacji")


@dataclass
class CycleEvent:
    """Reprezentuje zdarzenie cyklu"""
    cycle_number: int
    start_time: datetime
    end_time: datetime
    duration_ms: float


class InductiveSensor:
    """
    Klasa obsługująca czujnik indukcyjny podłączony do GPIO Raspberry Pi.
    
    Wykrywa cykle otwarcia/zamknięcia na podstawie impulsów z czujnika.
    Czujnik widzi siłownik w pozycji początkowej (okno zamknięte).
    Cykl rozpoczyna się gdy siłownik opuszcza pole widzenia czujnika
    i kończy się gdy wraca.
    """
    
    def __init__(
        self,
        gpio_pin: int = 17,
        debounce_ms: int = 50,
        pull_up: bool = True,
        active_low: bool = True,
        simulation_mode: bool = False
    ):
        """
        Inicjalizacja czujnika.
        
        Args:
            gpio_pin: Numer pinu GPIO
            debounce_ms: Czas debouncingu w ms
            pull_up: Czy włączyć wewnętrzny pull-up
            active_low: Czy czujnik jest aktywny stanem niskim (NPN)
            simulation_mode: Wymuś tryb symulacji (do testów)
        """
        self.gpio_pin = gpio_pin
        self.debounce_ms = debounce_ms
        self.pull_up = pull_up
        self.active_low = active_low
        self.simulation_mode = simulation_mode or not GPIO_AVAILABLE
        
        self._cycle_count = 0
        self._cycle_start_time: Optional[datetime] = None
        self._is_running = False
        self._lock = threading.Lock()
        self._callbacks: list[Callable[[CycleEvent], None]] = []
        
        # Stan czujnika
        self._sensor_active = True  # Zakładamy że na starcie siłownik jest widoczny
        self._last_state_change = time.time()
        
        if not self.simulation_mode:
            self._setup_gpio()
        else:
            logger.info("Czujnik działa w trybie symulacji")
    
    def _setup_gpio(self):
        """Konfiguracja GPIO"""
        GPIO.setmode(GPIO.BCM)
        
        pull = GPIO.PUD_UP if self.pull_up else GPIO.PUD_DOWN
        GPIO.setup(self.gpio_pin, GPIO.IN, pull_up_down=pull)
        
        # Odczytaj początkowy stan
        self._sensor_active = self._read_sensor_state()
        logger.info(f"GPIO {self.gpio_pin} skonfigurowane, stan początkowy: {'aktywny' if self._sensor_active else 'nieaktywny'}")
    
    def _read_sensor_state(self) -> bool:
        """Odczytaj stan czujnika (True = siłownik widoczny)"""
        if self.simulation_mode:
            return self._sensor_active
        
        raw_state = GPIO.input(self.gpio_pin)
        # Jeśli active_low, to stan niski oznacza że czujnik widzi obiekt
        return (raw_state == GPIO.LOW) if self.active_low else (raw_state == GPIO.HIGH)
    
    def _gpio_callback(self, channel):
        """Callback wywoływany przy zmianie stanu GPIO"""
        current_time = time.time()
        
        # Debouncing
        if (current_time - self._last_state_change) * 1000 < self.debounce_ms:
            return
        
        self._last_state_change = current_time
        new_state = self._read_sensor_state()
        
        if new_state == self._sensor_active:
            return  # Brak faktycznej zmiany stanu
        
        self._sensor_active = new_state
        self._handle_state_change(new_state)
    
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
        """Uruchom nasłuchiwanie na GPIO"""
        if self._is_running:
            return
        
        self._is_running = True
        
        if not self.simulation_mode:
            # Nasłuchuj na obu zboczach (rising i falling)
            GPIO.add_event_detect(
                self.gpio_pin,
                GPIO.BOTH,
                callback=self._gpio_callback,
                bouncetime=self.debounce_ms
            )
        
        logger.info("Czujnik uruchomiony")
    
    def stop(self):
        """Zatrzymaj nasłuchiwanie"""
        if not self._is_running:
            return
        
        self._is_running = False
        
        if not self.simulation_mode:
            GPIO.remove_event_detect(self.gpio_pin)
        
        logger.info("Czujnik zatrzymany")
    
    def cleanup(self):
        """Zwolnij zasoby GPIO"""
        self.stop()
        if not self.simulation_mode:
            GPIO.cleanup(self.gpio_pin)
    
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
