"""
FastAPI Server - REST API do zdalnego dostępu do danych
"""

import os
import logging
import asyncio
from datetime import date, datetime
from typing import Optional
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# === Modele Pydantic ===

class CycleResponse(BaseModel):
    """Model odpowiedzi dla pojedynczego cyklu"""
    timestamp: str
    cycle_number: int
    cycle_duration_ms: float


class CycleListResponse(BaseModel):
    """Model odpowiedzi dla listy cykli"""
    total: int
    cycles: list[CycleResponse]


class StatisticsResponse(BaseModel):
    """Model odpowiedzi dla statystyk"""
    total_cycles: int
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    first_cycle_time: Optional[str] = None
    last_cycle_time: Optional[str] = None


class SystemStatusResponse(BaseModel):
    """Model odpowiedzi dla statusu systemu"""
    status: str = Field(description="Status systemu: running, stopped, error")
    sensor_active: bool = Field(description="Czy czujnik widzi siłownik")
    cycle_in_progress: bool = Field(description="Czy trwa cykl")
    current_cycle_count: int = Field(description="Aktualna liczba cykli")
    uptime_seconds: float = Field(description="Czas działania systemu")
    last_cycle_time: Optional[str] = None


class USBExportResponse(BaseModel):
    """Model odpowiedzi dla eksportu USB"""
    success: bool
    message: str
    path: Optional[str] = None


class USBExportRequest(BaseModel):
    """Model żądania eksportu USB"""
    filename: Optional[str] = "cycles_export.csv"


# === Klasa serwera API ===

class APIServer:
    """
    Klasa zarządzająca serwerem FastAPI.
    
    Przechowuje referencje do komponentów systemu (csv_handler, sensor, session_manager)
    i udostępnia je endpointom.
    """
    
    def __init__(self):
        self.csv_handler = None
        self.sensor = None
        self.session_manager = None
        self.start_time = datetime.now()
        self.usb_mount_path = "/media/usb"
    
    def set_csv_handler(self, handler):
        """Ustaw handler CSV"""
        self.csv_handler = handler
    
    def set_sensor(self, sensor):
        """Ustaw czujnik"""
        self.sensor = sensor
    
    def set_session_manager(self, manager):
        """Ustaw session manager"""
        self.session_manager = manager
    
    def set_usb_mount_path(self, path: str):
        """Ustaw ścieżkę montowania USB"""
        self.usb_mount_path = path


# Globalna instancja serwera
api_server = APIServer()


def create_app(
    csv_handler=None,
    sensor=None,
    session_manager=None,
    enable_cors: bool = True,
    usb_mount_path: str = "/media/usb"
) -> FastAPI:
    """
    Utwórz i skonfiguruj aplikację FastAPI.
    
    Args:
        csv_handler: Instancja CSVHandler
        sensor: Instancja InductiveSensor
        session_manager: Instancja SessionManager
        enable_cors: Czy włączyć CORS
        usb_mount_path: Ścieżka montowania pendrive
    
    Returns:
        Skonfigurowana aplikacja FastAPI
    """
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Lifecycle manager aplikacji"""
        logger.info("API Server uruchamiany...")
        api_server.start_time = datetime.now()
        yield
        logger.info("API Server zatrzymywany...")
    
    app = FastAPI(
        title="Windows CCounter API",
        description="API systemu pomiarowego cykli otwarcia/zamknięcia okien suszarki",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # Konfiguracja CORS
    if enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    # Ustaw komponenty
    if csv_handler:
        api_server.set_csv_handler(csv_handler)
    if sensor:
        api_server.set_sensor(sensor)
    if session_manager:
        api_server.set_session_manager(session_manager)
    api_server.set_usb_mount_path(usb_mount_path)
    
    # === Endpointy ===
    
    @app.get("/", tags=["Root"])
    async def root():
        """Strona główna API"""
        return {
            "name": "Windows CCounter API",
            "version": "1.0.0",
            "status": "running",
            "session_active": api_server.session_manager.is_session_active if api_server.session_manager else False
        }
    
    @app.get("/api/cycles", response_model=CycleListResponse, tags=["Cycles"])
    async def get_cycles(
        from_date: Optional[date] = Query(None, alias="from", description="Data początkowa (YYYY-MM-DD)"),
        to_date: Optional[date] = Query(None, alias="to", description="Data końcowa (YYYY-MM-DD)"),
        limit: Optional[int] = Query(None, ge=1, le=10000, description="Limit rekordów")
    ):
        """
        Pobierz listę cykli.
        
        Opcjonalnie filtruj po zakresie dat.
        """
        if not api_server.csv_handler:
            raise HTTPException(status_code=500, detail="CSV handler nie skonfigurowany")
        
        if from_date or to_date:
            records = api_server.csv_handler.get_records_by_date_range(from_date, to_date)
        else:
            records = api_server.csv_handler.get_all_records()
        
        if limit:
            records = records[-limit:]
        
        return CycleListResponse(
            total=len(records),
            cycles=[CycleResponse(**r.to_dict()) for r in records]
        )
    
    @app.get("/api/cycles/latest", response_model=Optional[CycleResponse], tags=["Cycles"])
    async def get_latest_cycle():
        """Pobierz ostatni zarejestrowany cykl"""
        if not api_server.csv_handler:
            raise HTTPException(status_code=500, detail="CSV handler nie skonfigurowany")
        
        record = api_server.csv_handler.get_latest_record()
        if not record:
            return None
        
        return CycleResponse(**record.to_dict())
    
    @app.get("/api/cycles/last/{n}", response_model=CycleListResponse, tags=["Cycles"])
    async def get_last_n_cycles(n: int):
        """Pobierz ostatnie N cykli"""
        if not api_server.csv_handler:
            raise HTTPException(status_code=500, detail="CSV handler nie skonfigurowany")
        
        if n < 1 or n > 10000:
            raise HTTPException(status_code=400, detail="N musi być między 1 a 10000")
        
        records = api_server.csv_handler.get_last_n_records(n)
        return CycleListResponse(
            total=len(records),
            cycles=[CycleResponse(**r.to_dict()) for r in records]
        )
    
    @app.get("/api/stats", response_model=StatisticsResponse, tags=["Statistics"])
    async def get_statistics():
        """Pobierz statystyki systemu"""
        if not api_server.csv_handler:
            raise HTTPException(status_code=500, detail="CSV handler nie skonfigurowany")
        
        stats = api_server.csv_handler.get_statistics()
        return StatisticsResponse(**stats)
    
    @app.get("/api/status", response_model=SystemStatusResponse, tags=["System"])
    async def get_system_status():
        """Pobierz status systemu"""
        uptime = (datetime.now() - api_server.start_time).total_seconds()
        
        status_data = {
            "status": "running",
            "sensor_active": False,
            "cycle_in_progress": False,
            "current_cycle_count": 0,
            "uptime_seconds": uptime,
            "last_cycle_time": None
        }
        
        if api_server.sensor:
            status_data["sensor_active"] = api_server.sensor.is_sensor_active
            status_data["cycle_in_progress"] = api_server.sensor.is_cycle_in_progress
            status_data["current_cycle_count"] = api_server.sensor.cycle_count
        
        if api_server.csv_handler:
            latest = api_server.csv_handler.get_latest_record()
            if latest:
                status_data["last_cycle_time"] = latest.timestamp
        
        return SystemStatusResponse(**status_data)
    
    @app.get("/api/export/csv", tags=["Export"])
    async def export_csv():
        """Pobierz plik CSV z danymi"""
        if not api_server.csv_handler:
            raise HTTPException(status_code=500, detail="CSV handler nie skonfigurowany")
        
        csv_path = api_server.csv_handler.csv_path
        
        if not csv_path.exists():
            raise HTTPException(status_code=404, detail="Plik CSV nie istnieje")
        
        return FileResponse(
            path=str(csv_path),
            media_type="text/csv",
            filename=f"cycles_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
    
    @app.get("/api/export/csv/content", response_class=PlainTextResponse, tags=["Export"])
    async def export_csv_content():
        """Pobierz zawartość pliku CSV jako tekst"""
        if not api_server.csv_handler:
            raise HTTPException(status_code=500, detail="CSV handler nie skonfigurowany")
        
        content = await api_server.csv_handler.get_csv_content_async()
        return PlainTextResponse(content=content, media_type="text/csv")
    
    @app.post("/api/usb/export", response_model=USBExportResponse, tags=["Export"])
    async def export_to_usb(request: USBExportRequest = USBExportRequest()):
        """Eksportuj dane na pendrive USB"""
        if not api_server.csv_handler:
            raise HTTPException(status_code=500, detail="CSV handler nie skonfigurowany")
        
        # Sprawdź czy pendrive jest zamontowany
        usb_path = Path(api_server.usb_mount_path)
        
        if not usb_path.exists():
            return USBExportResponse(
                success=False,
                message=f"Pendrive nie wykryty w {api_server.usb_mount_path}"
            )
        
        # Sprawdź czy można pisać
        if not os.access(usb_path, os.W_OK):
            return USBExportResponse(
                success=False,
                message="Brak uprawnień do zapisu na pendrive"
            )
        
        # Eksportuj
        destination = usb_path / request.filename
        success = api_server.csv_handler.export_to_path(str(destination))
        
        if success:
            return USBExportResponse(
                success=True,
                message="Dane wyeksportowane pomyślnie",
                path=str(destination)
            )
        else:
            return USBExportResponse(
                success=False,
                message="Błąd podczas eksportu"
            )
    
    @app.post("/api/backup", tags=["System"])
    async def create_backup():
        """Utwórz backup danych"""
        if not api_server.csv_handler:
            raise HTTPException(status_code=500, detail="CSV handler nie skonfigurowany")
        
        backup_path = api_server.csv_handler.create_backup()
        
        if backup_path:
            return {"success": True, "backup_path": backup_path}
        else:
            return {"success": False, "message": "Nie udało się utworzyć backup"}
    
    @app.get("/api/usb/status", tags=["Export"])
    async def get_usb_status():
        """Sprawdź status pendrive USB"""
        usb_path = Path(api_server.usb_mount_path)
        
        exists = usb_path.exists()
        writable = os.access(usb_path, os.W_OK) if exists else False
        
        return {
            "mounted": exists,
            "writable": writable,
            "path": api_server.usb_mount_path
        }
    
    # === Endpointy symulacji (tylko do testów) ===
    
    @app.post("/api/simulate/cycle", tags=["Simulation"])
    async def simulate_cycle(duration_ms: int = 2000):
        """
        Symuluj pojedynczy cykl otwarcia/zamknięcia.
        Działa tylko gdy system jest w trybie symulacji.
        """
        if not api_server.sensor:
            raise HTTPException(status_code=500, detail="Czujnik nie skonfigurowany")
        
        if not api_server.sensor.simulation_mode:
            raise HTTPException(status_code=400, detail="System nie jest w trybie symulacji")
        
        import time
        import threading
        
        def run_cycle():
            api_server.sensor.simulate_cycle_start()
            time.sleep(duration_ms / 1000)
            api_server.sensor.simulate_cycle_end()
        
        # Uruchom w osobnym wątku żeby nie blokować API
        thread = threading.Thread(target=run_cycle)
        thread.start()
        
        return {
            "success": True,
            "message": f"Symulacja cyklu rozpoczęta (czas: {duration_ms}ms)",
            "cycle_number": api_server.sensor.cycle_count + 1
        }
    
    @app.post("/api/simulate/cycles/{count}", tags=["Simulation"])
    async def simulate_multiple_cycles(count: int, duration_ms: int = 2000, interval_ms: int = 500):
        """
        Symuluj wiele cykli z określonym interwałem.
        """
        if not api_server.sensor:
            raise HTTPException(status_code=500, detail="Czujnik nie skonfigurowany")
        
        if not api_server.sensor.simulation_mode:
            raise HTTPException(status_code=400, detail="System nie jest w trybie symulacji")
        
        if count < 1 or count > 100:
            raise HTTPException(status_code=400, detail="Liczba cykli musi być między 1 a 100")
        
        import time
        import threading
        
        def run_cycles():
            for i in range(count):
                api_server.sensor.simulate_cycle_start()
                time.sleep(duration_ms / 1000)
                api_server.sensor.simulate_cycle_end()
                if i < count - 1:
                    time.sleep(interval_ms / 1000)
        
        thread = threading.Thread(target=run_cycles)
        thread.start()
        
        return {
            "success": True,
            "message": f"Symulacja {count} cykli rozpoczęta",
            "starting_cycle": api_server.sensor.cycle_count + 1
        }
    
    # === Endpointy sesji ===
    
    @app.post("/api/session/start", tags=["Session"])
    async def start_session(name: Optional[str] = None):
        """Rozpocznij nową sesję pomiarową"""
        if not api_server.session_manager:
            raise HTTPException(status_code=500, detail="Session manager nie skonfigurowany")
        
        if api_server.session_manager.is_session_active:
            raise HTTPException(status_code=400, detail="Sesja już aktywna")
        
        session = api_server.session_manager.start_session(session_name=name)
        
        return {
            "success": True,
            "session_id": session.session_id,
            "csv_filename": session.csv_filename,
            "start_time": session.start_time.isoformat()
        }
    
    @app.post("/api/session/stop", tags=["Session"])
    async def stop_session():
        """Zakończ aktywną sesję pomiarową"""
        if not api_server.session_manager:
            raise HTTPException(status_code=500, detail="Session manager nie skonfigurowany")
        
        if not api_server.session_manager.is_session_active:
            raise HTTPException(status_code=400, detail="Brak aktywnej sesji")
        
        session = api_server.session_manager.stop_session()
        
        return {
            "success": True,
            "session_id": session.session_id,
            "csv_filename": session.csv_filename,
            "cycle_count": session.cycle_count,
            "start_time": session.start_time.isoformat(),
            "end_time": session.end_time.isoformat() if session.end_time else None
        }
    
    @app.get("/api/session/status", tags=["Session"])
    async def get_session_status():
        """Pobierz status bieżącej sesji"""
        if not api_server.session_manager:
            return {
                "session_active": False,
                "session_id": None,
                "cycle_count": 0
            }
        
        session = api_server.session_manager.current_session
        
        return {
            "session_active": api_server.session_manager.is_session_active,
            "session_id": session.session_id if session else None,
            "csv_filename": session.csv_filename if session else None,
            "cycle_count": api_server.session_manager.session_cycle_count,
            "start_time": session.start_time.isoformat() if session and session.start_time else None
        }
    
    @app.get("/api/session/list", tags=["Session"])
    async def list_sessions():
        """Lista wszystkich zapisanych sesji"""
        if not api_server.session_manager:
            raise HTTPException(status_code=500, detail="Session manager nie skonfigurowany")
        
        sessions = api_server.session_manager.list_sessions()
        return {
            "total": len(sessions),
            "sessions": sessions
        }
    
    return app


def run_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    csv_handler=None,
    sensor=None,
    **kwargs
):
    """
    Uruchom serwer API.
    
    Args:
        host: Adres hosta
        port: Port
        csv_handler: Instancja CSVHandler
        sensor: Instancja InductiveSensor
    """
    import uvicorn
    
    app = create_app(csv_handler=csv_handler, sensor=sensor, **kwargs)
    uvicorn.run(app, host=host, port=port)


async def run_server_async(
    host: str = "0.0.0.0",
    port: int = 8000,
    csv_handler=None,
    sensor=None,
    **kwargs
):
    """
    Uruchom serwer API asynchronicznie.
    """
    import uvicorn
    
    app = create_app(csv_handler=csv_handler, sensor=sensor, **kwargs)
    config = uvicorn.Config(app, host=host, port=port)
    server = uvicorn.Server(config)
    await server.serve()
