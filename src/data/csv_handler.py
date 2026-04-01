"""
Moduł obsługi zapisu danych do pliku CSV
"""

import csv
import os
import shutil
import logging
import threading
import aiofiles
import aiofiles.os
from datetime import datetime, date
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class CycleRecord:
    """Rekord pojedynczego cyklu"""
    timestamp: str
    cycle_number: int
    cycle_duration_ms: float
    
    @classmethod
    def from_dict(cls, data: dict) -> "CycleRecord":
        return cls(
            timestamp=data["timestamp"],
            cycle_number=int(data["cycle_number"]),
            cycle_duration_ms=float(data["cycle_duration_ms"])
        )
    
    def to_dict(self) -> dict:
        return asdict(self)


class CSVHandler:
    """
    Obsługa zapisu i odczytu danych cykli do/z pliku CSV.
    
    Format CSV:
    timestamp,cycle_number,cycle_duration_ms
    """
    
    FIELDNAMES = ["timestamp", "cycle_number", "cycle_duration_ms"]
    TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
    
    def __init__(
        self,
        csv_path: str = "./data/cycles.csv",
        backup_enabled: bool = True,
        backup_path: str = "./data/backup/",
        max_records_in_memory: int = 1000
    ):
        """
        Inicjalizacja handlera CSV.
        
        Args:
            csv_path: Ścieżka do pliku CSV
            backup_enabled: Czy tworzyć backup
            backup_path: Ścieżka do katalogu backup
            max_records_in_memory: Maksymalna liczba rekordów w pamięci
        """
        self.csv_path = Path(csv_path)
        self.backup_enabled = backup_enabled
        self.backup_path = Path(backup_path)
        self.max_records_in_memory = max_records_in_memory
        
        self._lock = threading.Lock()
        self._records_cache: deque[CycleRecord] = deque(maxlen=max_records_in_memory)
        self._last_cycle_number = 0
        
        self._ensure_directories()
        self._load_existing_data()
    
    def _ensure_directories(self):
        """Utwórz katalogi jeśli nie istnieją"""
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        if self.backup_enabled:
            self.backup_path.mkdir(parents=True, exist_ok=True)
    
    def _load_existing_data(self):
        """Wczytaj istniejące dane z pliku CSV"""
        if not self.csv_path.exists():
            logger.info(f"Plik CSV nie istnieje, zostanie utworzony: {self.csv_path}")
            return
        
        try:
            with open(self.csv_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    record = CycleRecord.from_dict(row)
                    self._records_cache.append(record)
                    self._last_cycle_number = max(self._last_cycle_number, record.cycle_number)
            
            logger.info(f"Wczytano {len(self._records_cache)} rekordów, ostatni cykl: #{self._last_cycle_number}")
        except Exception as e:
            logger.error(f"Błąd wczytywania CSV: {e}")
    
    def _write_header_if_needed(self):
        """Zapisz nagłówek jeśli plik nie istnieje lub jest pusty"""
        if not self.csv_path.exists() or self.csv_path.stat().st_size == 0:
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.FIELDNAMES)
                writer.writeheader()
    
    def add_cycle(
        self,
        cycle_number: int,
        duration_ms: float,
        timestamp: Optional[datetime] = None
    ) -> CycleRecord:
        """
        Dodaj nowy rekord cyklu.
        
        Args:
            cycle_number: Numer cyklu
            duration_ms: Czas trwania w milisekundach
            timestamp: Znacznik czasu (domyślnie teraz)
        
        Returns:
            Utworzony rekord
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        record = CycleRecord(
            timestamp=timestamp.strftime(self.TIMESTAMP_FORMAT),
            cycle_number=cycle_number,
            cycle_duration_ms=round(duration_ms, 2)
        )
        
        with self._lock:
            # Zapisz do pliku
            self._write_header_if_needed()
            with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.FIELDNAMES)
                writer.writerow(record.to_dict())
            
            # Dodaj do cache
            self._records_cache.append(record)
            self._last_cycle_number = cycle_number
        
        logger.debug(f"Zapisano cykl #{cycle_number}")
        return record
    
    def get_all_records(self) -> list[CycleRecord]:
        """Pobierz wszystkie rekordy z pamięci cache"""
        with self._lock:
            return list(self._records_cache)
    
    def get_records_by_date_range(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None
    ) -> list[CycleRecord]:
        """
        Pobierz rekordy z zakresu dat.
        
        Args:
            from_date: Data początkowa (włącznie)
            to_date: Data końcowa (włącznie)
        """
        records = self.get_all_records()
        
        filtered = []
        for record in records:
            record_date = datetime.strptime(record.timestamp, self.TIMESTAMP_FORMAT).date()
            
            if from_date and record_date < from_date:
                continue
            if to_date and record_date > to_date:
                continue
            
            filtered.append(record)
        
        return filtered
    
    def get_latest_record(self) -> Optional[CycleRecord]:
        """Pobierz ostatni rekord"""
        with self._lock:
            if self._records_cache:
                return self._records_cache[-1]
            return None
    
    def get_last_n_records(self, n: int) -> list[CycleRecord]:
        """Pobierz ostatnie N rekordów"""
        with self._lock:
            records = list(self._records_cache)
            return records[-n:] if len(records) >= n else records
    
    @property
    def last_cycle_number(self) -> int:
        """Numer ostatniego cyklu"""
        return self._last_cycle_number
    
    @property
    def total_cycles(self) -> int:
        """Całkowita liczba cykli"""
        return len(self._records_cache)
    
    def get_statistics(self) -> dict:
        """
        Oblicz statystyki.
        
        Returns:
            Słownik ze statystykami
        """
        records = self.get_all_records()
        
        if not records:
            return {
                "total_cycles": 0,
                "avg_duration_ms": 0,
                "min_duration_ms": 0,
                "max_duration_ms": 0,
                "first_cycle_time": None,
                "last_cycle_time": None
            }
        
        durations = [r.cycle_duration_ms for r in records]
        
        return {
            "total_cycles": len(records),
            "avg_duration_ms": round(sum(durations) / len(durations), 2),
            "min_duration_ms": round(min(durations), 2),
            "max_duration_ms": round(max(durations), 2),
            "first_cycle_time": records[0].timestamp,
            "last_cycle_time": records[-1].timestamp
        }
    
    def create_backup(self) -> Optional[str]:
        """
        Utwórz backup pliku CSV.
        
        Returns:
            Ścieżka do pliku backup lub None
        """
        if not self.backup_enabled or not self.csv_path.exists():
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"cycles_backup_{timestamp}.csv"
        backup_file = self.backup_path / backup_filename
        
        try:
            shutil.copy2(self.csv_path, backup_file)
            logger.info(f"Utworzono backup: {backup_file}")
            return str(backup_file)
        except Exception as e:
            logger.error(f"Błąd tworzenia backup: {e}")
            return None
    
    def export_to_path(self, destination_path: str) -> bool:
        """
        Eksportuj plik CSV do wskazanej lokalizacji.
        
        Args:
            destination_path: Ścieżka docelowa
        
        Returns:
            True jeśli sukces
        """
        try:
            destination = Path(destination_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.csv_path, destination)
            logger.info(f"Wyeksportowano do: {destination}")
            return True
        except Exception as e:
            logger.error(f"Błąd eksportu: {e}")
            return False
    
    def get_csv_content(self) -> str:
        """Pobierz zawartość pliku CSV jako string"""
        if not self.csv_path.exists():
            return ""
        
        with open(self.csv_path, "r", encoding="utf-8") as f:
            return f.read()
    
    async def get_csv_content_async(self) -> str:
        """Pobierz zawartość pliku CSV asynchronicznie"""
        if not await aiofiles.os.path.exists(self.csv_path):
            return ""
        
        async with aiofiles.open(self.csv_path, "r", encoding="utf-8") as f:
            return await f.read()
    
    def reload_from_file(self):
        """Przeładuj dane z pliku (np. po ręcznej edycji)"""
        with self._lock:
            self._records_cache.clear()
            self._last_cycle_number = 0
        self._load_existing_data()
