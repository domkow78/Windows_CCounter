"""
NiceGUI Web Interface - interfejs webowy do obsługi systemu CCounter
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from nicegui import ui, app

if TYPE_CHECKING:
    from src.data import SessionManager
    from src.sensor import InductiveSensor

logger = logging.getLogger(__name__)


class WebUI:
    """
    Interfejs webowy NiceGUI dla systemu CCounter.
    """
    
    def __init__(
        self,
        session_manager: Optional["SessionManager"] = None,
        sensor: Optional["InductiveSensor"] = None,
        title: str = "Windows CCounter"
    ):
        self.session_manager = session_manager
        self.sensor = sensor
        self.title = title
        
        # Elementy UI do aktualizacji
        self._cycle_count_label = None
        self._session_status_label = None
        self._sensor_status_label = None
        self._last_duration_label = None

        # Stan dashboardu
        self._total_cycles = 0
        self._avg_duration_ms = 0.0
        self._min_duration_ms = 0.0
        self._max_duration_ms = 0.0
        self._last_cycle_duration_ms = None

        # Elementy wykresu trendu (tworzone raz, aktualizowane in-place)
        self._echart = None
        self._chart_stats_label = None

        # Licznik cykli przy ostatnim odświeżeniu wykresu
        self._last_chart_cycle_count = -1
        
        # Timer do odświeżania
        self._refresh_timer = None
    
    def setup_routes(self):
        """Konfiguracja stron NiceGUI"""
        
        @ui.page('/')
        def main_page():
            self._create_main_page()
        
        @ui.page('/history')
        def history_page():
            self._create_history_page()
        
        @ui.page('/settings')
        def settings_page():
            self._create_settings_page()
    
    def _create_header(self):
        """Nagłówek strony"""
        with ui.header().classes('bg-blue-900 text-white items-center justify-between'):
            with ui.row().classes('items-center gap-4'):
                ui.icon('factory', size='lg')
                ui.label('Windows CCounter').classes('text-xl font-bold')
            
            with ui.row().classes('gap-2'):
                ui.button('Dashboard', on_click=lambda: ui.navigate.to('/')).props('flat color=white')
                ui.button('Historia', on_click=lambda: ui.navigate.to('/history')).props('flat color=white')
                ui.button('Ustawienia', on_click=lambda: ui.navigate.to('/settings')).props('flat color=white')
    
    def _create_main_page(self):
        """Główna strona - dashboard"""
        self._create_header()
        
        with ui.column().classes('w-full max-w-6xl mx-auto p-4 gap-4'):
            self._render_top_cards()
            
            # Panel symulacji (tylko gdy tryb symulacji)
            if self.sensor and self.sensor.simulation_mode:
                with ui.card().classes('w-full'):
                    ui.label('🧪 Symulacja czujnika').classes('text-lg font-bold mb-2')
                    ui.label('Tryb symulacji aktywny - brak fizycznego czujnika GPIO').classes('text-gray-500 text-sm mb-2')
                    with ui.row().classes('gap-2'):
                        ui.button('Symuluj cykl (1s)', on_click=lambda: self._simulate_cycle(1000)).props('icon=replay')
                        ui.button('Symuluj cykl (2s)', on_click=lambda: self._simulate_cycle(2000)).props('icon=replay')
                        ui.button('Symuluj cykl (3s)', on_click=lambda: self._simulate_cycle(3000)).props('icon=replay')
                        ui.button('5 cykli losowych', on_click=self._simulate_multiple_cycles).props('icon=auto_mode color=orange')
            
            self._create_trend_chart()
            
            self._render_stats_section()
        
        # Timer odświeżania
        ui.timer(0.5, self._refresh_ui)

    @ui.refreshable
    def _render_top_cards(self):
        """Renderuj górne kafelki dashboardu."""
        session_active = self.session_manager.is_session_active if self.session_manager else False
        cycle_count = self.session_manager.session_cycle_count if self.session_manager else 0
        sensor_text = '● ---'
        sensor_classes = 'text-xl'
        if self.sensor:
            if self.sensor.is_sensor_active:
                sensor_text = '● AKTYWNY'
                sensor_classes = 'text-xl text-green-600'
            elif self.sensor.is_cycle_in_progress:
                sensor_text = '○ W CYKLU'
                sensor_classes = 'text-xl text-orange-600'
            else:
                sensor_text = '● NIEAKTYWNY'
                sensor_classes = 'text-xl text-red-600'

        latest_record = self.session_manager.get_latest_record() if self.session_manager else None
        last_duration = f'{latest_record.cycle_duration_ms:.0f} ms' if latest_record else '-- ms'

        with ui.row().classes('w-full gap-4'):
            with ui.card().classes('flex-1 h-40 flex items-center justify-center'):
                with ui.column().classes('text-center'):
                    ui.label('Status sesji').classes('text-gray-500 text-sm')
                    ui.label('🔴 REC' if session_active else '⏹ STOP').classes(
                        'text-2xl font-bold text-red-600' if session_active else 'text-2xl font-bold text-gray-600'
                    )

            with ui.card().classes('flex-1 h-40 p-0 flex flex-col'):
                with ui.column().classes('gap-0 flex-1 w-full'):
                    ui.button('START', on_click=self._start_session, color='green').props('icon=play_arrow').classes('w-full h-full')
                    ui.button('STOP', on_click=self._stop_session, color='red').props('icon=stop').classes('w-full h-full')

            with ui.card().classes('flex-1 h-40 flex items-center justify-center'):
                with ui.column().classes('text-center'):
                    ui.label('Cykle w sesji').classes('text-gray-500 text-sm')
                    ui.label(str(cycle_count)).classes('text-4xl font-bold text-blue-600')

            with ui.card().classes('flex-1 h-40 flex items-center justify-center'):
                with ui.column().classes('text-center'):
                    ui.label('Status czujnika').classes('text-gray-500 text-sm')
                    ui.label(sensor_text).classes(sensor_classes)

            with ui.card().classes('flex-1 h-40 flex items-center justify-center'):
                with ui.column().classes('text-center'):
                    ui.label('Ostatni cykl').classes('text-gray-500 text-sm')
                    ui.label(last_duration).classes('text-2xl font-bold')

    def _create_trend_chart(self):
        """Utwórz panel wykresu trendu raz przy budowie strony."""
        with ui.card().classes('w-full'):
            ui.label('Trend czasów - ostatnie 500 cykli').classes('text-lg font-bold mb-2')

            self._echart = ui.echart({
                'animation': True,
                'animationDuration': 400,
                'tooltip': {'trigger': 'axis'},
                'grid': {'left': 50, 'right': 20, 'top': 20, 'bottom': 35},
                'xAxis': {
                    'type': 'category',
                    'boundaryGap': False,
                    'data': [],
                    'name': 'starsze → nowsze',
                    'nameLocation': 'middle',
                    'nameGap': 25,
                    'axisLabel': {'show': False},
                },
                'yAxis': {
                    'type': 'value',
                    'name': 'ms',
                    'scale': True,
                },
                'series': [
                    {
                        'name': 'czas cyklu',
                        'type': 'line',
                        'data': [],
                        'showSymbol': False,
                        'lineStyle': {'width': 2, 'color': '#16c79a'},
                        'itemStyle': {'color': '#16c79a'},
                    },
                    {
                        'name': 'srednia',
                        'type': 'line',
                        'data': [],
                        'showSymbol': False,
                        'lineStyle': {'width': 1, 'type': 'dashed', 'color': '#f9a825'},
                        'itemStyle': {'color': '#f9a825'},
                    },
                ],
            }).classes('w-full h-64')

            self._chart_stats_label = ui.label(
                'Brak danych - uruchom sesję i wykonaj cykle'
            ).classes('text-sm text-gray-500 font-mono')

    def _update_trend_chart_data(self):
        """Zaktualizuj dane wykresu in-place przez ECharts setOption (z animacją)."""
        if not self._echart:
            return

        current_count = self.session_manager.session_cycle_count if self.session_manager else 0
        if current_count == self._last_chart_cycle_count:
            return
        self._last_chart_cycle_count = current_count

        records = self.session_manager.get_last_n_records(500) if self.session_manager else []
        durations = [float(record.cycle_duration_ms) for record in records]

        if not durations:
            if self._chart_stats_label:
                self._chart_stats_label.set_text('Brak danych - uruchom sesję i wykonaj cykle')
            return

        avg_val = sum(durations) / len(durations)
        min_val = min(durations)
        max_val = max(durations)
        n = len(durations)

        # Aktualizacja in-place — ECharts animuje tylko zmienioną część
        self._echart.run_chart_method('setOption', {
            'xAxis': {'data': list(range(1, n + 1))},
            'series': [
                {'data': durations},
                {'data': [round(avg_val, 1)] * n},
            ],
        })

        if self._chart_stats_label:
            self._chart_stats_label.set_text(
                f'N={n} | min: {min_val:.0f} ms | avg: {avg_val:.0f} ms | '
                f'max: {max_val:.0f} ms | ostatni: {durations[-1]:.0f} ms'
            )

    @ui.refreshable
    def _render_stats_section(self):
        """Renderuj statystyki sesji."""
        stats = self.session_manager.get_session_statistics() if self.session_manager else {
            'total_cycles': 0,
            'avg_duration_ms': 0,
            'min_duration_ms': 0,
            'max_duration_ms': 0,
        }
        total_cycles = stats.get('total_cycles', 0)
        avg_duration = f"{stats.get('avg_duration_ms', 0):.0f} ms" if total_cycles else '-- ms'
        min_max = (
            f"{stats.get('min_duration_ms', 0):.0f} / {stats.get('max_duration_ms', 0):.0f} ms"
            if total_cycles else '-- / -- ms'
        )

        with ui.card().classes('w-full'):
            ui.label('Statystyki sesji').classes('text-lg font-bold mb-2')
            with ui.row().classes('w-full justify-between items-start'):
                with ui.row().classes('gap-8 flex-1'):
                    with ui.column():
                        ui.label('Suma cykli').classes('text-gray-500 text-sm')
                        ui.label(str(total_cycles)).classes('text-xl font-bold')
                    with ui.column():
                        ui.label('Średni czas').classes('text-gray-500 text-sm')
                        ui.label(avg_duration).classes('text-xl font-bold')
                    with ui.column():
                        ui.label('Min / Max').classes('text-gray-500 text-sm')
                        ui.label(min_max).classes('text-xl font-bold')
    
    def _create_history_page(self):
        """Strona historii"""
        self._create_header()
        
        with ui.column().classes('w-full max-w-6xl mx-auto p-4 gap-4'):
            ui.label('📜 Historia sesji').classes('text-2xl font-bold')
            
            with ui.card().classes('w-full'):
                with ui.row().classes('justify-between items-center mb-4'):
                    ui.label('Pliki sesji').classes('text-lg font-bold')
                    ui.button('Eksportuj wszystko', on_click=self._export_all).props('icon=download color=primary')
                
                # Lista plików sesji
                self._load_session_files()
    
    def _create_settings_page(self):
        """Strona ustawień"""
        self._create_header()
        
        with ui.column().classes('w-full max-w-4xl mx-auto p-4 gap-4'):
            ui.label('⚙️ Ustawienia').classes('text-2xl font-bold')
            
            with ui.card().classes('w-full'):
                ui.label('Konfiguracja systemu').classes('text-lg font-bold mb-4')
                
                with ui.column().classes('gap-4'):
                    ui.label('Dane').classes('font-bold')
                    ui.input('Katalog danych', value='./data').classes('w-full')
                    ui.checkbox('Automatyczny backup', value=True)
    
    def _load_session_files(self):
        """Załaduj listę plików sesji"""
        import os
        from pathlib import Path
        
        data_dir = Path('./data')
        if not data_dir.exists():
            ui.label('Brak plików sesji').classes('text-gray-500')
            return
        
        session_files = sorted(data_dir.glob('session_*.csv'), reverse=True)
        
        if not session_files:
            ui.label('Brak plików sesji').classes('text-gray-500')
            return
        
        for f in session_files[:20]:  # Ostatnie 20 sesji
            with ui.card().classes('w-full'):
                with ui.row().classes('justify-between items-center'):
                    with ui.column():
                        ui.label(f.name).classes('font-mono')
                        size_kb = f.stat().st_size / 1024
                        ui.label(f'{size_kb:.1f} KB').classes('text-gray-500 text-sm')
                    ui.button('Pobierz', on_click=lambda file=f: self._download_file(file)).props('icon=download flat')
    
    async def _start_session(self):
        """Rozpocznij sesję"""
        if self.session_manager:
            if not self.session_manager.is_session_active:
                self.session_manager.start_session()
                self._refresh_ui()
                ui.notify('Sesja rozpoczęta!', type='positive')
                logger.info("Sesja rozpoczęta przez WebUI")
            else:
                ui.notify('Sesja już aktywna', type='warning')
    
    async def _stop_session(self):
        """Zakończ sesję"""
        if self.session_manager:
            if self.session_manager.is_session_active:
                info = self.session_manager.stop_session()
                self._refresh_ui()
                if info:
                    ui.notify(f'Sesja zakończona! Zapisano {info.cycle_count} cykli.', type='positive')
                    logger.info(f"Sesja zakończona przez WebUI: {info.cycle_count} cykli")
            else:
                ui.notify('Brak aktywnej sesji', type='warning')
    
    async def _simulate_cycle(self, duration_ms: int = 2000):
        """Symuluj pojedynczy cykl"""
        if self.sensor and self.sensor.simulation_mode:
            ui.notify(f'Symulacja cyklu ({duration_ms}ms)...', type='info')
            
            # Uruchom w tle żeby nie blokować UI
            import threading
            thread = threading.Thread(
                target=self.sensor.simulate_full_cycle,
                args=(duration_ms,),
                daemon=True
            )
            thread.start()
    
    async def _simulate_multiple_cycles(self):
        """Symuluj wiele cykli"""
        import random
        import threading
        
        if self.sensor and self.sensor.simulation_mode:
            ui.notify('Symulacja 5 losowych cykli...', type='info')
            
            def run_cycles():
                for i in range(5):
                    duration = random.randint(1000, 4000)
                    self.sensor.simulate_full_cycle(duration)
                    import time
                    time.sleep(0.5)
            
            thread = threading.Thread(target=run_cycles, daemon=True)
            thread.start()
    
    def _refresh_ui(self):
        """Odśwież elementy UI"""
        self._render_top_cards.refresh()
        self._update_trend_chart_data()
        self._render_stats_section.refresh()
    
    async def _export_all(self):
        """Eksportuj wszystkie dane"""
        ui.notify('Funkcja eksportu w przygotowaniu...', type='info')

    async def _ask_download_filename(self, default_name: str) -> str | None:
        """Pokaż dialog i zwróć nazwę pliku do pobrania (lub None jeśli anulowano)."""
        with ui.dialog() as dialog, ui.card().classes('min-w-96'):
            ui.label('Nazwa pliku do pobrania').classes('text-lg font-bold')
            filename_input = ui.input('Nazwa pliku', value=default_name).classes('w-full')

            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Anuluj', on_click=lambda: dialog.submit(None)).props('flat')
                ui.button('Pobierz', on_click=lambda: dialog.submit(filename_input.value)).props('color=primary')

        result = await dialog
        if result is None:
            return None

        filename = str(result).strip()
        if not filename:
            return default_name
        if not filename.lower().endswith('.csv'):
            filename = f'{filename}.csv'
        return filename
    
    async def _download_file(self, filepath):
        """Pobierz plik"""
        suggested_name = filepath.name if hasattr(filepath, 'name') else 'session.csv'
        filename = await self._ask_download_filename(suggested_name)
        if filename is None:
            return

        ui.download(str(filepath), filename=filename)
        ui.notify(f'Pobieranie: {filename}', type='positive')


def create_nicegui_app(
    session_manager=None,
    sensor=None,
    host: str = "0.0.0.0",
    port: int = 8080,
    title: str = "Windows CCounter"
) -> WebUI:
    """
    Utwórz i skonfiguruj aplikację NiceGUI.
    
    Args:
        session_manager: Instancja SessionManager
        sensor: Instancja InductiveSensor
        host: Host do nasłuchiwania
        port: Port (domyślnie 8080, żeby nie kolidować z FastAPI na 8000)
        title: Tytuł aplikacji
    
    Returns:
        Instancja WebUI
    """
    web_ui = WebUI(
        session_manager=session_manager,
        sensor=sensor,
        title=title
    )
    
    web_ui.setup_routes()
    
    return web_ui
