"""Execution HUD - Shows current step during automated execution."""

import tkinter as tk
from threading import Thread
import queue
import time

_BG      = "#1a1a2e"
_FG      = "#e0e0e0"
_RED     = "#e74c3c"
_ORANGE  = "#f39c12"
_GREEN   = "#27ae60"


class ExecutionUI:
    """HUD showing current step number and status during execution."""

    def __init__(self, monitor_info: dict, corner: str = "bottom-left"):
        """
        Initialize execution HUD.

        Args:
            monitor_info: dict with left, top, width, height of monitor
            corner: position ("bottom-left", "bottom-right", "top-left", "top-right")
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
        """Start window in separate thread."""
        self._running = True
        self._thread = Thread(target=self._run_window, daemon=True)
        self._thread.start()

    def _run_window(self):
        """Create and run tkinter window with custom event loop."""
        self.window = tk.Tk()
        self.window.overrideredirect(True)
        self.window.attributes('-topmost', True)
        self.window.attributes('-alpha', 0.92)
        self.window.configure(bg=_BG)

        # Position based on corner
        w, h = 160, 28
        x, y = self._calculate_position(w, h)
        self.window.geometry(f"{w}x{h}+{x}+{y}")

        # Single row with all elements
        main_row = tk.Frame(self.window, bg=_BG)
        main_row.pack(fill="both", padx=1, pady=0)

        # Status indicator (●)
        tk.Label(main_row, text="●", fg=_ORANGE, bg=_BG,
                 font=("Segoe UI", 9, "bold")).pack(side="left")

        # Status text
        self.status_label = tk.Label(main_row, text="EXEC", fg=_FG, bg=_BG,
                                     font=("Segoe UI", 8, "bold"))
        self.status_label.pack(side="left", padx=(2, 0))

        # Step counter
        self.step_var = tk.StringVar(value="Step 1")
        tk.Label(main_row, textvariable=self.step_var, fg=_FG, bg=_BG,
                 font=("Segoe UI", 8)).pack(side="left", padx=(2, 0))

        # Custom event loop that processes queue and updates tkinter
        while self._running and self.window.winfo_exists():
            # Process all commands from queue
            try:
                while True:
                    cmd = self._state_queue.get_nowait()
                    if cmd == 'ready':
                        self._do_set_ready()
                    elif cmd == 'executing':
                        self._do_set_executing()
                    elif cmd == 'matching':
                        self._do_set_matching()
                    elif isinstance(cmd, tuple) and cmd[0] == 'step':
                        self._do_set_step(cmd[1])
            except queue.Empty:
                pass

            try:
                self.window.update()
            except:
                break
            time.sleep(0.01)

    def _calculate_position(self, w: int, h: int) -> tuple:
        """Calculate position (x, y) based on corner."""
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
        """Signal ready state to queue."""
        self._state_queue.put('ready')

    def _do_set_ready(self):
        """Update UI to green."""
        if self.status_label:
            self.status_label.config(fg=_GREEN)
            self._color = _GREEN

    def set_executing(self):
        """Signal executing state to queue."""
        self._state_queue.put('executing')

    def _do_set_executing(self):
        """Update UI to orange."""
        if self.status_label:
            self.status_label.config(fg=_ORANGE)
            self._color = _ORANGE

    def set_matching(self):
        """Signal matching state to queue."""
        self._state_queue.put('matching')

    def _do_set_matching(self):
        """Update UI to yellow-orange."""
        if self.status_label:
            self.status_label.config(fg=_ORANGE)
            self._color = _ORANGE

    def set_step(self, n: int):
        """Send step number to queue."""
        self._state_queue.put(('step', n))

    def _do_set_step(self, n: int):
        """Update step number."""
        if self.step_var:
            self.step_var.set(f"Step {n}")

    def close(self):
        """Close the execution UI."""
        self._running = False

    def update(self):
        """Update tkinter (no-op since mainloop runs in thread)."""
        pass
