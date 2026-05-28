"""Designer Menu - Modal window with action choices."""

import tkinter as tk
from tkinter import ttk
import time
import gc

# Theme colors
_BG = "#1a1a2e"
_FG = "#e0e0e0"
_BUTTON_BG = "#2d3561"
_BUTTON_HOVER = "#3d4571"

# Menu dimensions
_MENU_WIDTH = 250
_MENU_BASE_HEIGHT = 50
_BUTTON_HEIGHT = 50
_UPDATE_INTERVAL_MS = 10
_CLEANUP_WAIT_MS = 200


class DesignerMenu:
    def __init__(self, monitor_info: dict, show_end_input: bool = False, on_choice_callback=None):
        """
        monitor_info: dict con left, top, width, height del monitor
        show_end_input: se True, mostra il bottone "End Input"
        on_choice_callback: callback(choice) dove choice è 'refresh', 'end_input', o 'end_session'
        """
        self.monitor_info = monitor_info
        self.show_end_input = show_end_input
        self.on_choice_callback = on_choice_callback
        self.choice = None
        self.window = None
        self.should_close = False

    def show(self):
        """Mostra il menu e aspetta la scelta dell'utente."""
        self.window = tk.Tk()
        self.window.overrideredirect(True)
        self.window.attributes('-topmost', True)
        self.window.attributes('-alpha', 0.95)
        self.window.configure(bg=_BG)

        # Position at center of monitor
        button_count = 3 if self.show_end_input else 2
        w, h = _MENU_WIDTH, _MENU_BASE_HEIGHT + (button_count * _BUTTON_HEIGHT)
        x = self.monitor_info['left'] + (self.monitor_info['width'] - w) // 2
        y = self.monitor_info['top'] + (self.monitor_info['height'] - h) // 2
        self.window.geometry(f"{w}x{h}+{x}+{y}")

        # Title
        title = tk.Label(self.window, text="Designer Menu", fg=_FG, bg=_BG,
                        font=("Segoe UI", 10, "bold"))
        title.pack(pady=(10, 15))

        # Buttons frame
        buttons_frame = tk.Frame(self.window, bg=_BG)
        buttons_frame.pack(padx=10, pady=0)

        # Refresh Screenshot button
        self._create_button(buttons_frame, "Refresh Screenshot", lambda: self._on_choice('refresh'))

        # End Input button (only if typing active)
        if self.show_end_input:
            self._create_button(buttons_frame, "End Input", lambda: self._on_choice('end_input'))

        # End Session button
        self._create_button(buttons_frame, "End Session", lambda: self._on_choice('end_session'))

        # Custom loop instead of mainloop for thread-safe closing
        while not self.should_close:
            try:
                self.window.update()
            except:
                break
            time.sleep(_UPDATE_INTERVAL_MS / 1000)

        # Cleanup
        try:
            self.window.destroy()
        except:
            pass
        self.window = None
        time.sleep(_CLEANUP_WAIT_MS / 1000)
        gc.collect()  # Force garbage collection to clean up tkinter objects

    def close(self):
        """Close the menu window safely from another thread."""
        self.should_close = True

    def _create_button(self, parent, text, command):
        """Crea un bottone stilizzato."""
        btn = tk.Button(
            parent, text=text, command=command,
            bg=_BUTTON_BG, fg=_FG,
            activebackground=_BUTTON_HOVER, activeforeground=_FG,
            relief="flat", bd=0, padx=15, pady=8,
            font=("Segoe UI", 9, "bold"),
            width=20
        )
        btn.pack(pady=5)

    def _on_choice(self, choice):
        """Callback quando utente sceglie."""
        self.choice = choice
        self.should_close = True
        try:
            self.window.destroy()
        except:
            pass
        time.sleep(_CLEANUP_WAIT_MS / 1000)  # Wait for window to fully close
        if self.on_choice_callback:
            self.on_choice_callback(choice)
