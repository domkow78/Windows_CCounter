"""
Moduł zarządzania sesjami pomiarowymi.

Sesja pomiarowa to okres między START a STOP, podczas którego
cykle są zapisywane do dedykowanego pliku CSV.
"""

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

from .csv_handler import CSVHandler, CycleRecord

logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    """Informacje o sesji pomiarowej"""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime]
    csv_filename: str
    cycle_count: int
    is_active: bool


class SessionManager:
    """
    Zarządza sesjami pomiarowymi.
    
    - START tworzy nowy plik CSV z timestampem
    - STOP kończy sesję
    - Pomiary zapisywane tylko podczas aktywnej sesji
    """
    
    def __init__(
        self,
        data_dir: str = "./data",
        backup_enabled: bool = True,
        backup_path: str = "./data/backup/"
    ):
        """
        Inicjalizacja managera sesji.
        
        Args:
            data_dir: Katalog na pliki CSV
            backup_enabled: Czy tworzyć backup
            backup_path: Ścieżka do katalogu backup
        """
        self.data_dir = Path(data_dir)
        self.backup_enabled = backup_enabled
        self.backup_path = backup_path
        
        self._lock = threading.RLock()  # RLock pozwala na wielokrotne wejście z tego samego wątku
        self._current_session: Optional[SessionInfo] = None
        self._csv_handler: Optional[CSVHandler] = None
        self._session_cycle_count = 0
        
        # Callbacki
        self._on_session_start_callbacks: list[Callable[[SessionInfo], None]] = []
        self._on_session_stop_callbacks: list[Callable[[SessionInfo], None]] = []
        
        # Upewnij się że katalog istnieje
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"SessionManager zainicjalizowany, katalog: {self.data_dir}")
    
    @property
    def is_session_active(self) -> bool:
        """Czy sesja jest aktywna"""
        with self._lock:
            return self._current_session is not None and self._current_session.is_active
    
    @property
    def current_session(self) -> Optional[SessionInfo]:
        """Aktualna sesja"""
        with self._lock:
            return self._current_session
    
    @property
    def session_cycle_count(self) -> int:
        """Liczba cykli w bieżącej sesji"""
        with self._lock:
            return self._session_cycle_count
    
    def start_session(self, session_name: Optional[str] = None) -> SessionInfo:
        """
        Rozpocznij nową sesję pomiarową.
        
        Args:
            session_name: Opcjonalna nazwa sesji (domyślnie timestamp)
        
        Returns:
            Informacje o utworzonej sesji
        """
        with self._lock:
            if self._current_session and self._current_session.is_active:
                logger.warning("Sesja już aktywna, najpierw ją zakończ")
                return self._current_session
            
            # Utwórz ID sesji z timestampem
            start_time = datetime.now()
            session_id = start_time.strftime("%Y%m%d_%H%M%S")
            
            if session_name:
                csv_filename = f"session_{session_id}_{session_name}.csv"
            else:
                csv_filename = f"session_{session_id}.csv"
            
            csv_path = self.data_dir / csv_filename
            
            # Utwórz nowy handler CSV dla tej sesji
            self._csv_handler = CSVHandler(
                csv_path=str(csv_path),
                backup_enabled=self.backup_enabled,
                backup_path=self.backup_path
            )
            
            self._session_cycle_count = 0
            
            self._current_session = SessionInfo(
                session_id=session_id,
                start_time=start_time,
                end_time=None,
                csv_filename=csv_filename,
                cycle_count=0,
                is_active=True
            )
            
            logger.info(f"Sesja {session_id} rozpoczęta, plik: {csv_filename}")
        
        # Wywołaj callbacki (poza lockiem)
        for callback in self._on_session_start_callbacks:
            try:
                callback(self._current_session)
            except Exception as e:
                logger.error(f"Błąd w callbacku start sesji: {e}")
        
        return self._current_session
    
    def stop_session(self) -> Optional[SessionInfo]:
        """
        Zakończ aktywną sesję.
        
        Returns:
            Informacje o zakończonej sesji lub None
        """
        with self._lock:
            if not self._current_session or not self._current_session.is_active:
                logger.warning("Brak aktywnej sesji do zakończenia")
                return None
            
            end_time = datetime.now()
            self._current_session.end_time = end_time
            self._current_session.is_active = False
            self._current_session.cycle_count = self._session_cycle_count
            
            finished_session = self._current_session
            
            logger.info(
                f"Sesja {finished_session.session_id} zakończona, "
                f"cykli: {finished_session.cycle_count}"
            )
        
        # Wywołaj callbacki (poza lockiem)
        for callback in self._on_session_stop_callbacks:
            try:
                callback(finished_session)
            except Exception as e:
                logger.error(f"Błąd w callbacku stop sesji: {e}")
        
        return finished_session
    
    def add_cycle(
        self,
        cycle_number: int,
        duration_ms: float,
        timestamp: Optional[datetime] = None
    ) -> Optional[CycleRecord]:
        """
        Dodaj cykl do aktywnej sesji.
        
        Zwraca None jeśli sesja nie jest aktywna.
        """
        with self._lock:
            if not self._current_session or not self._current_session.is_active:
                logger.debug("Cykl pominięty - brak aktywnej sesji")
                return None
            
            if not self._csv_handler:
                logger.error("Brak CSV handlera")
                return None
            
            self._session_cycle_count += 1
            
            # Użyj numeru cyklu w ramach sesji
            record = self._csv_handler.add_cycle(
                cycle_number=self._session_cycle_count,
                duration_ms=duration_ms,
                timestamp=timestamp
            )
            
            return record
    
    def get_session_records(self) -> list[CycleRecord]:
        """Pobierz rekordy z aktywnej sesji"""
        with self._lock:
            if self._csv_handler:
                return self._csv_handler.get_all_records()
            return []
    
    def get_session_statistics(self) -> dict:
        """Pobierz statystyki aktywnej sesji"""
        with self._lock:
            if self._csv_handler:
                stats = self._csv_handler.get_statistics()
                stats["session_id"] = self._current_session.session_id if self._current_session else None
                stats["session_active"] = self.is_session_active
                return stats
            
            return {
                "total_cycles": 0,
                "avg_duration_ms": 0,
                "min_duration_ms": 0,
                "max_duration_ms": 0,
                "first_cycle_time": None,
                "last_cycle_time": None,
                "session_id": None,
                "session_active": False
            }
    
    def get_latest_record(self) -> Optional[CycleRecord]:
        """Pobierz ostatni rekord z aktywnej sesji"""
        with self._lock:
            if self._csv_handler:
                return self._csv_handler.get_latest_record()
            return None
    
    def get_last_n_records(self, n: int) -> list[CycleRecord]:
        """Pobierz ostatnie N rekordów z aktywnej sesji"""
        with self._lock:
            if self._csv_handler:
                return self._csv_handler.get_last_n_records(n)
            return []
    
    def get_csv_path(self) -> Optional[Path]:
        """Pobierz ścieżkę do aktualnego pliku CSV"""
        with self._lock:
            if self._csv_handler:
                return self._csv_handler.csv_path
            return None
    
    def export_session(self, destination_path: str) -> bool:
        """Eksportuj aktualną sesję do podanej lokalizacji"""
        with self._lock:
            if self._csv_handler:
                return self._csv_handler.export_to_path(destination_path)
            return False
    
    def list_sessions(self) -> list[str]:
        """Lista wszystkich plików sesji w katalogu danych"""
        sessions = []
        for f in self.data_dir.glob("session_*.csv"):
            sessions.append(f.name)
        return sorted(sessions, reverse=True)
    
    def register_on_start(self, callback: Callable[[SessionInfo], None]):
        """Zarejestruj callback wywoływany przy starcie sesji"""
        self._on_session_start_callbacks.append(callback)
    
    def register_on_stop(self, callback: Callable[[SessionInfo], None]):
        """Zarejestruj callback wywoływany przy stopie sesji"""
        self._on_session_stop_callbacks.append(callback)
