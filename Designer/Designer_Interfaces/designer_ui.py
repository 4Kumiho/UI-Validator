"""Mini UI - Recording HUD indicator (dark theme, runs in separate thread)."""

import tkinter as tk
from threading import Thread
import queue
import time

# Theme colors
_BG      = "#1a1a2e"
_FG      = "#e0e0e0"
_RED     = "#e74c3c"
_ORANGE  = "#f39c12"
_GREEN   = "#27ae60"

# UI dimensions
_MINIUI_WIDTH = 135
_MINIUI_HEIGHT = 28
_MINIUI_ALPHA = 0.92
_UPDATE_INTERVAL_MS = 10


class MiniUI:
    def __init__(self, monitor_info: dict, corner: str = "bottom-left"):
        """
        monitor_info: dict con left, top, width, height del monitor
        corner: posizione angolo ("bottom-left", "bottom-right", "top-left", "top-right")
        """
        self.monitor_info = monitor_info
        self.corner = corner
        self.window = None
        self.status_label = None
        self.step_var = None
        self._running = False
        self._thread = None
        self._color = _RED
        self._state_queue = queue.Queue()
        self._start_window_thread()

    def _start_window_thread(self):
        """Avvia la finestra in un thread separato."""
        self._running = True
        self._thread = Thread(target=self._run_window, daemon=True)
        self._thread.start()

    def _run_window(self):
        """Crea e avvia la finestra tkinter con event loop custom."""
        self.window = tk.Tk()
        self.window.overrideredirect(True)
        self.window.attributes('-topmost', True)
        self.window.attributes('-alpha', _MINIUI_ALPHA)
        self.window.configure(bg=_BG)

        # Posizionamento in base al corner
        w, h = _MINIUI_WIDTH, _MINIUI_HEIGHT
        x, y = self._calculate_position(w, h)
        self.window.geometry(f"{w}x{h}+{x}+{y}")

        # Single row with all elements
        main_row = tk.Frame(self.window, bg=_BG)
        main_row.pack(fill="both", padx=1, pady=0)

        # Status indicator (●)
        tk.Label(main_row, text="●", fg=_ORANGE, bg=_BG,
                 font=("Segoe UI", 9, "bold")).pack(side="left")

        # Status text
        self.status_label = tk.Label(main_row, text="REC", fg=_FG, bg=_BG,
                                     font=("Segoe UI", 8, "bold"))
        self.status_label.pack(side="left", padx=(2, 0))

        # Step counter
        self.step_var = tk.StringVar(value="Step 1")
        tk.Label(main_row, textvariable=self.step_var, fg=_FG, bg=_BG,
                 font=("Segoe UI", 8)).pack(side="left", padx=(2, 0))

        # Custom event loop che processa queue e aggiorna tkinter
        while self._running and self.window.winfo_exists():
            # Processa tutti i comandi dalla queue
            try:
                while True:
                    cmd = self._state_queue.get_nowait()
                    if cmd == 'ready':
                        self._do_set_ready()
                    elif cmd == 'loading':
                        self._do_set_loading()
                    elif cmd == 'saving':
                        self._do_set_saving()
                    elif isinstance(cmd, tuple) and cmd[0] == 'step':
                        self._do_set_step(cmd[1])
            except queue.Empty:
                pass

            try:
                self.window.update()
            except:
                break
            time.sleep(_UPDATE_INTERVAL_MS / 1000)

    def _calculate_position(self, w: int, h: int) -> tuple:
        """Calcola posizione (x, y) in base al corner."""
        left = self.monitor_info['left']
        top = self.monitor_info['top']
        width = self.monitor_info['width']
        height = self.monitor_info['height']

        if self.corner == "bottom-left":
            x = left
            y = top + height - h
        elif self.corner == "bottom-right":
            x = left + width - w
            y = top + height - h
        elif self.corner == "top-left":
            x = left
            y = top
        elif self.corner == "top-right":
            x = left + width - w
            y = top
        else:
            x, y = left, top + height - h

        return x, y

    def set_ready(self):
        """Manda 'ready' alla queue."""
        self._state_queue.put('ready')

    def _do_set_ready(self):
        """Aggiorna UI a verde."""
        if self.status_label:
            self.status_label.config(fg=_GREEN)
            self._color = _GREEN

    def set_loading(self):
        """Manda 'loading' alla queue."""
        self._state_queue.put('loading')

    def _do_set_loading(self):
        """Aggiorna UI a arancione."""
        if self.status_label:
            self.status_label.config(fg=_ORANGE)
            self._color = _ORANGE

    def set_saving(self):
        """Manda 'saving' alla queue."""
        self._state_queue.put('saving')

    def _do_set_saving(self):
        """Aggiorna UI a rosso."""
        if self.status_label:
            self.status_label.config(fg=_RED)
            self._color = _RED

    def set_step(self, n: int):
        """Manda step numero alla queue."""
        self._state_queue.put(('step', n))

    def _do_set_step(self, n: int):
        """Aggiorna numero step."""
        if self.step_var:
            self.step_var.set(f"Step {n}")

    def close(self):
        """Chiude la Mini UI."""
        self._running = False

    def update(self):
        """Update tkinter (no-op since mainloop runs in thread)."""
        pass
