"""
GUI dla ekranu dotykowego - interfejs użytkownika Tkinter
"""

import tkinter as tk
from tkinter import ttk, messagebox, font
import threading
import logging
import os
import subprocess
from datetime import datetime
from typing import Optional, Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class CycleCounterGUI:
    """
    Interfejs graficzny dla ekranu dotykowego LCD.
    
    Wyświetla:
    - Aktualną liczbę cykli
    - Czas ostatniego cyklu
    - Status czujnika
    - Przyciski eksportu i ustawień
    """
    
    # Kolory
    COLOR_BG = "#1a1a2e"
    COLOR_FG = "#eaeaea"
    COLOR_ACCENT = "#0f3460"
    COLOR_SUCCESS = "#16c79a"
    COLOR_WARNING = "#f9a825"
    COLOR_ERROR = "#e94560"
    COLOR_SENSOR_ACTIVE = "#16c79a"
    COLOR_SENSOR_INACTIVE = "#e94560"
    COLOR_RECORDING = "#ff6b6b"
    COLOR_STOPPED = "#6c757d"
    
    def __init__(
        self,
        csv_handler=None,
        sensor=None,
        session_manager=None,
        fullscreen: bool = False,
        window_width: int = 800,
        window_height: int = 480,
        refresh_interval_ms: int = 500,
        usb_mount_path: str = "/media/usb"
    ):
        """
        Inicjalizacja GUI.
        
        Args:
            csv_handler: Instancja CSVHandler (legacy, używaj session_manager)
            sensor: Instancja InductiveSensor
            session_manager: Instancja SessionManager
            fullscreen: Czy uruchomić w trybie pełnoekranowym
            window_width: Szerokość okna
            window_height: Wysokość okna
            refresh_interval_ms: Interwał odświeżania w ms
            usb_mount_path: Ścieżka montowania pendrive
        """
        self.csv_handler = csv_handler
        self.sensor = sensor
        self.session_manager = session_manager
        self.fullscreen = fullscreen
        self.window_width = window_width
        self.window_height = window_height
        self.refresh_interval_ms = refresh_interval_ms
        self.usb_mount_path = usb_mount_path
        
        self._is_running = False
        self._root: Optional[tk.Tk] = None
        
        # Zapamiętana wartość licznika po STOP
        self._last_session_cycle_count = 0

        # Licznik cykli przy ostatnim rysowaniu wykresu (żeby nie przerysowywać co 500ms)
        self._last_chart_cycle_count = -1
        
        # Widgety do aktualizacji
        self._cycle_count_label: Optional[tk.Label] = None
        self._last_duration_label: Optional[tk.Label] = None
        self._sensor_status_label: Optional[tk.Label] = None
        self._session_status_label: Optional[tk.Label] = None
        self._timestamp_label: Optional[tk.Label] = None
        self._trend_canvas: Optional[tk.Canvas] = None
        self._trend_stats_label: Optional[tk.Label] = None
        self._start_btn: Optional[tk.Button] = None
        self._stop_btn: Optional[tk.Button] = None
    
    def _create_main_window(self):
        """Utwórz główne okno"""
        self._root = tk.Tk()
        self._root.title("Windows CCounter")
        
        if self.fullscreen:
            self._root.attributes("-fullscreen", True)
            self._root.bind("<Escape>", lambda e: self._toggle_fullscreen())
        else:
            self._root.geometry(f"{self.window_width}x{self.window_height}")
        
        self._root.configure(bg=self.COLOR_BG)
        self._root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Style
        self._setup_styles()
        
        # Layout główny
        self._create_layout()
    
    def _setup_styles(self):
        """Konfiguracja stylów ttk"""
        style = ttk.Style()
        style.theme_use("clam")
        
        # Treeview
        style.configure(
            "Custom.Treeview",
            background=self.COLOR_ACCENT,
            foreground=self.COLOR_FG,
            fieldbackground=self.COLOR_ACCENT,
            rowheight=30
        )
        style.configure(
            "Custom.Treeview.Heading",
            background=self.COLOR_BG,
            foreground=self.COLOR_FG,
            font=("Arial", 10, "bold")
        )
        
        # Przyciski
        style.configure(
            "Big.TButton",
            font=("Arial", 14),
            padding=10
        )
    
    def _create_layout(self):
        """Utwórz layout interfejsu"""
        # Główny kontener
        main_frame = tk.Frame(self._root, bg=self.COLOR_BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Górna sekcja - tytuł i status
        self._create_header(main_frame)
        
        # Środkowa sekcja - główne dane
        self._create_main_display(main_frame)
        
        # Dolna sekcja - historia i przyciski
        self._create_bottom_section(main_frame)
    
    def _create_header(self, parent):
        """Utwórz nagłówek"""
        header_frame = tk.Frame(parent, bg=self.COLOR_BG)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Tytuł
        title_label = tk.Label(
            header_frame,
            text="Windows CCounter",
            font=("Arial", 24, "bold"),
            fg=self.COLOR_FG,
            bg=self.COLOR_BG
        )
        title_label.pack(side=tk.LEFT)
        
        # Status sesji (środek)
        self._session_status_label = tk.Label(
            header_frame,
            text="⏹ STOP",
            font=("Arial", 16, "bold"),
            fg=self.COLOR_STOPPED,
            bg=self.COLOR_BG
        )
        self._session_status_label.pack(side=tk.LEFT, padx=50)
        
        # Status czujnika
        self._sensor_status_label = tk.Label(
            header_frame,
            text="● CZUJNIK: ---",
            font=("Arial", 14),
            fg=self.COLOR_WARNING,
            bg=self.COLOR_BG
        )
        self._sensor_status_label.pack(side=tk.RIGHT)
    
    def _create_main_display(self, parent):
        """Utwórz główny wyświetlacz"""
        display_frame = tk.Frame(parent, bg=self.COLOR_ACCENT, relief=tk.RIDGE, bd=2)
        display_frame.pack(fill=tk.X, pady=10)
        
        # Licznik cykli
        cycle_frame = tk.Frame(display_frame, bg=self.COLOR_ACCENT)
        cycle_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=20, pady=10)
        
        tk.Label(
            cycle_frame,
            text="LICZBA CYKLI",
            font=("Arial", 12),
            fg=self.COLOR_FG,
            bg=self.COLOR_ACCENT
        ).pack()
        
        self._cycle_count_label = tk.Label(
            cycle_frame,
            text="0",
            font=("Arial", 36, "bold"),
            width=6,
            fg=self.COLOR_SUCCESS,
            bg=self.COLOR_ACCENT
        )
        self._cycle_count_label.pack()
        
        # Separator
        separator = tk.Frame(display_frame, bg=self.COLOR_FG, width=2)
        separator.pack(side=tk.LEFT, fill=tk.Y, pady=10)
        
        # Czas ostatniego cyklu
        duration_frame = tk.Frame(display_frame, bg=self.COLOR_ACCENT)
        duration_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=20, pady=10)
        
        tk.Label(
            duration_frame,
            text="OSTATNI CYKL",
            font=("Arial", 12),
            fg=self.COLOR_FG,
            bg=self.COLOR_ACCENT
        ).pack()
        
        self._last_duration_label = tk.Label(
            duration_frame,
            text="--- ms",
            font=("Arial", 24, "bold"),
            width=9,
            fg=self.COLOR_FG,
            bg=self.COLOR_ACCENT
        )
        self._last_duration_label.pack()
        
        self._timestamp_label = tk.Label(
            duration_frame,
            text="",
            font=("Arial", 10),
            width=19,
            fg=self.COLOR_FG,
            bg=self.COLOR_ACCENT
        )
        self._timestamp_label.pack()
    
    def _create_bottom_section(self, parent):
        """Utwórz dolną sekcję"""
        bottom_frame = tk.Frame(parent, bg=self.COLOR_BG)
        bottom_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Lewa strona - wykres trendu
        chart_frame = tk.Frame(bottom_frame, bg=self.COLOR_BG)
        chart_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        tk.Label(
            chart_frame,
            text="📈 Trend czasów - ostatnie 500 cykli",
            font=("Arial", 12, "bold"),
            fg=self.COLOR_FG,
            bg=self.COLOR_BG
        ).pack(anchor=tk.W)

        self._trend_canvas = tk.Canvas(
            chart_frame,
            bg="#132743",
            highlightthickness=1,
            highlightbackground="#2c4f7c"
        )
        self._trend_canvas.pack(fill=tk.BOTH, expand=True, pady=(5, 2))

        self._trend_stats_label = tk.Label(
            chart_frame,
            text="Brak danych",
            font=("Courier New", 10),
            width=74,
            anchor="w",
            justify=tk.LEFT,
            fg=self.COLOR_FG,
            bg=self.COLOR_BG
        )
        self._trend_stats_label.pack(anchor=tk.W, pady=(2, 0))
        
        # Prawa strona - przyciski
        buttons_frame = tk.Frame(bottom_frame, bg=self.COLOR_BG)
        buttons_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        
        # === PRZYCISKI START/STOP ===
        
        # Przycisk START
        self._start_btn = tk.Button(
            buttons_frame,
            text="▶ START",
            font=("Arial", 14, "bold"),
            bg=self.COLOR_SUCCESS,
            fg=self.COLOR_FG,
            activebackground="#20e3b2",
            activeforeground=self.COLOR_FG,
            width=15,
            height=1,
            command=self._on_start_session
        )
        self._start_btn.pack(pady=4)
        
        # Przycisk STOP
        self._stop_btn = tk.Button(
            buttons_frame,
            text="⏹ STOP",
            font=("Arial", 14, "bold"),
            bg=self.COLOR_STOPPED,
            fg=self.COLOR_FG,
            activebackground=self.COLOR_ERROR,
            activeforeground=self.COLOR_FG,
            width=15,
            height=1,
            command=self._on_stop_session,
            state=tk.DISABLED
        )
        self._stop_btn.pack(pady=4)
        
        # Separator
        sep = tk.Frame(buttons_frame, bg=self.COLOR_FG, height=2)
        sep.pack(fill=tk.X, pady=8)
        
        # Przycisk eksportu USB
        usb_btn = tk.Button(
            buttons_frame,
            text="Eksport USB",
            font=("Arial", 12),
            bg=self.COLOR_ACCENT,
            fg=self.COLOR_FG,
            activebackground=self.COLOR_SUCCESS,
            activeforeground=self.COLOR_FG,
            width=15,
            height=1,
            command=self._on_usb_export
        )
        usb_btn.pack(pady=3)
        
        # Przycisk zamknięcia (tylko jeśli nie fullscreen)
        if not self.fullscreen:
            close_btn = tk.Button(
                buttons_frame,
                text="❌ Zamknij",
                font=("Arial", 12),
                bg=self.COLOR_ERROR,
                fg=self.COLOR_FG,
                activebackground="#ff6b6b",
                activeforeground=self.COLOR_FG,
                width=15,
                height=1,
                command=self._on_closing
            )
            close_btn.pack(pady=3)
    
    def _on_start_session(self):
        """Obsługa przycisku START - rozpocznij nową sesję"""
        if not self.session_manager:
            messagebox.showerror("Błąd", "Session Manager nie skonfigurowany")
            return
        
        if self.session_manager.is_session_active:
            messagebox.showwarning("Uwaga", "Sesja już jest aktywna!")
            return
        
        # Rozpocznij sesję
        session = self.session_manager.start_session()
        
        # Aktualizuj UI
        self._start_btn.config(state=tk.DISABLED, bg=self.COLOR_STOPPED)
        self._stop_btn.config(state=tk.NORMAL, bg=self.COLOR_ERROR)
        self._session_status_label.config(
            text=f"🔴 REC: {session.csv_filename}",
            fg=self.COLOR_RECORDING
        )
        
        # Reset licznika w GUI dla nowej sesji
        self._cycle_count_label.config(text="0")

        # Wyczyść wykres trendu i zresetuj licznik cache
        self._last_chart_cycle_count = -1
        if self._trend_canvas:
            self._trend_canvas.delete("all")
        if self._trend_stats_label:
            self._trend_stats_label.config(text="Brak danych")
        
        logger.info(f"Sesja {session.session_id} rozpoczęta przez GUI")
    
    def _on_stop_session(self):
        """Obsługa przycisku STOP - zakończ sesję"""
        if not self.session_manager:
            messagebox.showerror("Błąd", "Session Manager nie skonfigurowany")
            return
        
        if not self.session_manager.is_session_active:
            messagebox.showwarning("Uwaga", "Brak aktywnej sesji!")
            return
        
        # Zapamiętaj liczbę cykli przed zakończeniem sesji
        self._last_session_cycle_count = self.session_manager.session_cycle_count
        
        # Zakończ sesję
        session = self.session_manager.stop_session()
        
        # Aktualizuj UI
        self._start_btn.config(state=tk.NORMAL, bg=self.COLOR_SUCCESS)
        self._stop_btn.config(state=tk.DISABLED, bg=self.COLOR_STOPPED)
        self._session_status_label.config(
            text="⏹ STOP",
            fg=self.COLOR_STOPPED
        )
        
        # Pokaż podsumowanie
        if session:
            messagebox.showinfo(
                "Sesja zakończona",
                f"Sesja: {session.session_id}\n"
                f"Plik: {session.csv_filename}\n"
                f"Liczba cykli: {session.cycle_count}"
            )
        
        logger.info(f"Sesja zakończona przez GUI, cykli: {session.cycle_count if session else 0}")
    
    def _update_display(self):
        """Aktualizuj wyświetlane dane"""
        if not self._is_running:
            return
        
        try:
            # Aktualizuj licznik cykli - z sesji jeśli aktywna, inaczej zapamiętana wartość
            if self.session_manager and self.session_manager.is_session_active:
                cycle_count = self.session_manager.session_cycle_count
                self._cycle_count_label.config(text=str(cycle_count))
            else:
                # Sesja nieaktywna - pokaż zapamiętaną wartość z ostatniej sesji
                self._cycle_count_label.config(text=str(self._last_session_cycle_count))
            
            # Status czujnika
            if self.sensor:
                if self.sensor.is_sensor_active:
                    self._sensor_status_label.config(
                        text="● CZUJNIK: AKTYWNY",
                        fg=self.COLOR_SENSOR_ACTIVE
                    )
                else:
                    self._sensor_status_label.config(
                        text="● CZUJNIK: NIEAKTYWNY",
                        fg=self.COLOR_SENSOR_INACTIVE
                    )
            
            # Aktualizuj ostatni cykl - z sesji lub csv_handler
            latest = None
            if self.session_manager and self.session_manager.is_session_active:
                latest = self.session_manager.get_latest_record()
            elif self.csv_handler:
                latest = self.csv_handler.get_latest_record()
            
            if latest:
                self._last_duration_label.config(
                    text=f"{latest.cycle_duration_ms:.0f} ms"
                )
                self._timestamp_label.config(text=latest.timestamp)
            
            # Aktualizuj wykres trendu
            self._update_trend_chart()
        
        except Exception as e:
            logger.error(f"Błąd aktualizacji GUI: {e}")
        
        # Zaplanuj następną aktualizację
        if self._is_running:
            self._root.after(self.refresh_interval_ms, self._update_display)
    
    def _update_trend_chart(self):
        """Aktualizuj wykres trendu czasów ostatnich 500 cykli"""
        if not self._trend_canvas:
            return

        # Przerysuj tylko gdy liczba cykli się zmieniła
        current_count = self.session_manager.session_cycle_count if self.session_manager else 0
        if current_count == self._last_chart_cycle_count:
            return
        self._last_chart_cycle_count = current_count

        # Pobierz rekordy z sesji lub csv_handler (fallback)
        records = []
        if self.session_manager:
            records = self.session_manager.get_last_n_records(500)
        elif self.csv_handler:
            records = self.csv_handler.get_last_n_records(500)

        self._trend_canvas.delete("all")

        width = self._trend_canvas.winfo_width()
        height = self._trend_canvas.winfo_height()

        # Canvas jeszcze nie ma wymiarów przy pierwszym renderze
        if width < 50 or height < 50:
            return

        if not records:
            self._trend_canvas.create_text(
                width / 2,
                height / 2,
                text="Brak danych - uruchom sesję i wykonaj cykle",
                fill=self.COLOR_FG,
                font=("Arial", 12)
            )
            if self._trend_stats_label:
                self._trend_stats_label.config(text="Brak danych")
            return

        durations = [float(record.cycle_duration_ms) for record in records]
        min_val = min(durations)
        max_val = max(durations)

        # Zabezpieczenie dla stałej wartości
        if min_val == max_val:
            min_val -= 1.0
            max_val += 1.0

        avg_val = sum(durations) / len(durations)

        left_margin = 52
        right_margin = 16
        top_margin = 12
        bottom_margin = 26

        plot_w = max(1, width - left_margin - right_margin)
        plot_h = max(1, height - top_margin - bottom_margin)

        # Siatka pozioma + etykiety osi Y
        grid_lines = 4
        for i in range(grid_lines + 1):
            y = top_margin + (plot_h * i / grid_lines)
            value = max_val - ((max_val - min_val) * i / grid_lines)

            self._trend_canvas.create_line(
                left_margin,
                y,
                width - right_margin,
                y,
                fill="#2c4f7c"
            )
            self._trend_canvas.create_text(
                left_margin - 6,
                y,
                text=f"{value:.0f}",
                fill=self.COLOR_FG,
                font=("Arial", 9),
                anchor="e"
            )

        # Osie
        self._trend_canvas.create_line(
            left_margin,
            top_margin,
            left_margin,
            height - bottom_margin,
            fill=self.COLOR_FG,
            width=1
        )
        self._trend_canvas.create_line(
            left_margin,
            height - bottom_margin,
            width - right_margin,
            height - bottom_margin,
            fill=self.COLOR_FG,
            width=1
        )

        # Punkty serii
        n = len(durations)
        points = []
        for idx, value in enumerate(durations):
            x = left_margin + (plot_w * idx / max(1, n - 1))
            y_norm = (value - min_val) / (max_val - min_val)
            y = top_margin + (plot_h * (1 - y_norm))
            points.extend([x, y])

        # Linia średniej
        avg_norm = (avg_val - min_val) / (max_val - min_val)
        avg_y = top_margin + (plot_h * (1 - avg_norm))
        self._trend_canvas.create_line(
            left_margin,
            avg_y,
            width - right_margin,
            avg_y,
            fill="#f9a825",
            dash=(4, 3),
            width=1
        )

        # Wykres trendu
        if len(points) >= 4:
            self._trend_canvas.create_line(
                *points,
                fill="#16c79a",
                width=2,
                smooth=False
            )

        # Podpis osi X
        self._trend_canvas.create_text(
            left_margin,
            height - 8,
            text="starsze",
            fill=self.COLOR_FG,
            font=("Arial", 9),
            anchor="w"
        )
        self._trend_canvas.create_text(
            width - right_margin,
            height - 8,
            text="nowsze",
            fill=self.COLOR_FG,
            font=("Arial", 9),
            anchor="e"
        )

        if self._trend_stats_label:
            self._trend_stats_label.config(
                text=(
                    f"N={n} | min: {min(durations):.0f} ms | "
                    f"avg: {avg_val:.0f} ms | max: {max(durations):.0f} ms | "
                    f"ostatni: {durations[-1]:.0f} ms"
                )
            )
    
    def _on_usb_export(self):
        """Obsługa przycisku eksportu USB"""
        # Sprawdź czy jest aktywna sesja lub csv_handler
        has_data = False
        if self.session_manager and self.session_manager.is_session_active:
            has_data = True
        elif self.csv_handler:
            has_data = True
        
        if not has_data:
            messagebox.showerror("Błąd", "Brak danych do eksportu")
            return
        
        usb_path = Path(self.usb_mount_path)
        
        # Sprawdź czy pendrive jest zamontowany
        if not usb_path.exists():
            messagebox.showwarning(
                "Pendrive nie wykryty",
                f"Nie znaleziono pendrive w:\n{self.usb_mount_path}\n\n"
                "Włóż pendrive i spróbuj ponownie."
            )
            return
        
        # Eksportuj - z sesji lub csv_handler
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cycles_export_{timestamp}.csv"
        destination = usb_path / filename
        
        success = False
        if self.session_manager and self.session_manager.is_session_active:
            success = self.session_manager.export_session(str(destination))
        elif self.csv_handler:
            success = self.csv_handler.export_to_path(str(destination))
        
        if success:
            messagebox.showinfo(
                "Eksport zakończony",
                f"Dane zostały zapisane na pendrive:\n{filename}"
            )
        else:
            messagebox.showerror(
                "Błąd eksportu",
                "Nie udało się zapisać danych na pendrive."
            )
    
    def _toggle_fullscreen(self):
        """Przełącz tryb pełnoekranowy"""
        self.fullscreen = not self.fullscreen
        self._root.attributes("-fullscreen", self.fullscreen)
    
    def _on_closing(self):
        """Obsługa zamknięcia okna"""
        if messagebox.askokcancel("Zamknij", "Czy na pewno chcesz zamknąć aplikację?"):
            self._is_running = False
            self._root.destroy()
    
    def start(self):
        """Uruchom GUI"""
        self._is_running = True
        self._create_main_window()
        
        # Rozpocznij aktualizację
        self._root.after(100, self._update_display)
        
        logger.info("GUI uruchomione")
        self._root.mainloop()
    
    def stop(self):
        """Zatrzymaj GUI"""
        self._is_running = False
        if self._root:
            self._root.quit()
    
    def run_in_thread(self) -> threading.Thread:
        """
        Uruchom GUI w osobnym wątku.
        
        Returns:
            Wątek GUI
        """
        thread = threading.Thread(target=self.start, daemon=True)
        thread.start()
        return thread


# Funkcja pomocnicza do uruchomienia GUI
def run_gui(
    csv_handler=None,
    sensor=None,
    **kwargs
):
    """Uruchom GUI"""
    gui = CycleCounterGUI(
        csv_handler=csv_handler,
        sensor=sensor,
        **kwargs
    )
    gui.start()
