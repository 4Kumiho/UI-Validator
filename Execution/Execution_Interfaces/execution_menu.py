"""Execution Menu - Modal window to end execution."""

import tkinter as tk
from tkinter import ttk
import time
import gc

_BG = "#1a1a2e"
_FG = "#e0e0e0"
_BUTTON_BG = "#2d3561"
_BUTTON_HOVER = "#3d4571"


class ExecutionMenu:
    """Menu to end execution during automation."""

    def __init__(self, monitor_info: dict, on_choice_callback=None):
        """
        Initialize execution menu.

        Args:
            monitor_info: dict with left, top, width, height of monitor
            on_choice_callback: callback(choice) where choice is 'continue' or 'stop'
        """
        self.monitor_info = monitor_info
        self.on_choice_callback = on_choice_callback
        self.choice = None
        self.window = None
        self.should_close = False

    def show(self):
        """Show menu and wait for user choice."""
        self.should_close = False  # Reset close flag
        self.choice = None  # Reset choice
        self.window = tk.Tk()
        self.window.overrideredirect(True)
        self.window.attributes('-topmost', True)
        self.window.attributes('-alpha', 0.95)
        self.window.configure(bg=_BG)

        # Position at center of monitor
        w, h = 250, 150
        x = self.monitor_info['left'] + (self.monitor_info['width'] - w) // 2
        y = self.monitor_info['top'] + (self.monitor_info['height'] - h) // 2
        self.window.geometry(f"{w}x{h}+{x}+{y}")

        # Ensure window is visible and focused
        self.window.lift()
        self.window.focus_force()
        self.window.deiconify()

        # Title
        title = tk.Label(self.window, text="Execution Menu", fg=_FG, bg=_BG,
                        font=("Segoe UI", 10, "bold"))
        title.pack(pady=(10, 15))

        # Buttons frame
        buttons_frame = tk.Frame(self.window, bg=_BG)
        buttons_frame.pack(padx=10, pady=0)

        # Resume Execution button
        self._create_button(buttons_frame, "Resume Execution", lambda: self._on_choice('resume'))

        # End Execution button
        self._create_button(buttons_frame, "End Execution", lambda: self._on_choice('stop'))

        # Process pending events to ensure window is drawn
        self.window.update_idletasks()
        time.sleep(0.05)  # Small delay to ensure window is rendered

        # Custom loop instead of mainloop for thread-safe closing
        while not self.should_close:
            try:
                self.window.update()
            except:
                break
            time.sleep(0.01)

        # Cleanup
        try:
            self.window.destroy()
        except:
            pass
        self.window = None
        time.sleep(0.2)
        gc.collect()  # Force garbage collection to clean up tkinter objects

    def close(self):
        """Close the menu window safely from another thread."""
        self.should_close = True

    def _create_button(self, parent, text, command):
        """Create a styled button."""
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
        """Callback when user chooses."""
        self.choice = choice
        self.should_close = True
        try:
            self.window.destroy()
        except:
            pass
        time.sleep(0.2)  # Wait for menu to fully disappear
        if self.on_choice_callback:
            self.on_choice_callback(choice)
