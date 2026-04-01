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
        
        # Widgety do aktualizacji
        self._cycle_count_label: Optional[tk.Label] = None
        self._last_duration_label: Optional[tk.Label] = None
        self._sensor_status_label: Optional[tk.Label] = None
        self._session_status_label: Optional[tk.Label] = None
        self._timestamp_label: Optional[tk.Label] = None
        self._history_tree: Optional[ttk.Treeview] = None
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
            text="🏭 Windows CCounter",
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
        cycle_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=20, pady=20)
        
        tk.Label(
            cycle_frame,
            text="LICZBA CYKLI",
            font=("Arial", 14),
            fg=self.COLOR_FG,
            bg=self.COLOR_ACCENT
        ).pack()
        
        self._cycle_count_label = tk.Label(
            cycle_frame,
            text="0",
            font=("Arial", 72, "bold"),
            fg=self.COLOR_SUCCESS,
            bg=self.COLOR_ACCENT
        )
        self._cycle_count_label.pack()
        
        # Separator
        separator = tk.Frame(display_frame, bg=self.COLOR_FG, width=2)
        separator.pack(side=tk.LEFT, fill=tk.Y, pady=20)
        
        # Czas ostatniego cyklu
        duration_frame = tk.Frame(display_frame, bg=self.COLOR_ACCENT)
        duration_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=20, pady=20)
        
        tk.Label(
            duration_frame,
            text="OSTATNI CYKL",
            font=("Arial", 14),
            fg=self.COLOR_FG,
            bg=self.COLOR_ACCENT
        ).pack()
        
        self._last_duration_label = tk.Label(
            duration_frame,
            text="--- ms",
            font=("Arial", 48, "bold"),
            fg=self.COLOR_FG,
            bg=self.COLOR_ACCENT
        )
        self._last_duration_label.pack()
        
        self._timestamp_label = tk.Label(
            duration_frame,
            text="",
            font=("Arial", 10),
            fg=self.COLOR_FG,
            bg=self.COLOR_ACCENT
        )
        self._timestamp_label.pack()
    
    def _create_bottom_section(self, parent):
        """Utwórz dolną sekcję"""
        bottom_frame = tk.Frame(parent, bg=self.COLOR_BG)
        bottom_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Lewa strona - historia
        history_frame = tk.Frame(bottom_frame, bg=self.COLOR_BG)
        history_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        tk.Label(
            history_frame,
            text="📜 Ostatnie cykle",
            font=("Arial", 12, "bold"),
            fg=self.COLOR_FG,
            bg=self.COLOR_BG
        ).pack(anchor=tk.W)
        
        # Treeview z historią
        columns = ("nr", "czas", "trwanie")
        self._history_tree = ttk.Treeview(
            history_frame,
            columns=columns,
            show="headings",
            height=6,
            style="Custom.Treeview"
        )
        
        self._history_tree.heading("nr", text="#")
        self._history_tree.heading("czas", text="Czas")
        self._history_tree.heading("trwanie", text="Trwanie (ms)")
        
        self._history_tree.column("nr", width=50, anchor=tk.CENTER)
        self._history_tree.column("czas", width=150, anchor=tk.CENTER)
        self._history_tree.column("trwanie", width=100, anchor=tk.CENTER)
        
        self._history_tree.pack(fill=tk.BOTH, expand=True, pady=5)
        
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
            text="💾 Eksport USB",
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
        
        # Przycisk statystyk
        stats_btn = tk.Button(
            buttons_frame,
            text="📊 Statystyki",
            font=("Arial", 12),
            bg=self.COLOR_ACCENT,
            fg=self.COLOR_FG,
            activebackground=self.COLOR_SUCCESS,
            activeforeground=self.COLOR_FG,
            width=15,
            height=1,
            command=self._on_show_stats
        )
        stats_btn.pack(pady=3)
        
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
        
        # Wyczyść historię
        if self._history_tree:
            for item in self._history_tree.get_children():
                self._history_tree.delete(item)
        
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
            
            # Aktualizuj historię
            self._update_history()
        
        except Exception as e:
            logger.error(f"Błąd aktualizacji GUI: {e}")
        
        # Zaplanuj następną aktualizację
        if self._is_running:
            self._root.after(self.refresh_interval_ms, self._update_display)
    
    def _update_history(self):
        """Aktualizuj tabelę historii"""
        if not self._history_tree:
            return
        
        # Pobierz rekordy z sesji lub csv_handler
        records = []
        if self.session_manager and self.session_manager.is_session_active:
            records = self.session_manager.get_last_n_records(10)
        elif self.csv_handler:
            records = self.csv_handler.get_last_n_records(10)
        
        if not records:
            return
        
        # Wyczyść
        for item in self._history_tree.get_children():
            self._history_tree.delete(item)
        
        # Dodaj ostatnie rekordy
        for record in reversed(records):  # Od najnowszego
            self._history_tree.insert("", tk.END, values=(
                record.cycle_number,
                record.timestamp,
                f"{record.cycle_duration_ms:.0f}"
            ))
    
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
    
    def _on_show_stats(self):
        """Pokaż okno statystyk"""
        stats = None
        session_info = ""
        
        if self.session_manager and self.session_manager.is_session_active:
            stats = self.session_manager.get_session_statistics()
            session = self.session_manager.current_session
            if session:
                session_info = f"\n📁 Sesja: {session.csv_filename}\n"
        elif self.csv_handler:
            stats = self.csv_handler.get_statistics()
        
        if not stats:
            messagebox.showinfo("Statystyki", "Brak danych")
            return
        
        stats_text = f"""
📊 STATYSTYKI{session_info}
Całkowita liczba cykli: {stats['total_cycles']}

Średni czas cyklu: {stats['avg_duration_ms']:.1f} ms
Minimalny czas: {stats['min_duration_ms']:.1f} ms
Maksymalny czas: {stats['max_duration_ms']:.1f} ms

Pierwszy cykl: {stats['first_cycle_time'] or 'brak'}
Ostatni cykl: {stats['last_cycle_time'] or 'brak'}
        """
        
        messagebox.showinfo("Statystyki", stats_text.strip())
    
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
