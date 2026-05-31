"""Designer Menu - Modal window with action choices."""

import tkinter as tk
import time
import gc

# Theme colors (matching create_designer_screen.kv)
_BG = "#0d0d12"
_FG = "#ffffff"
_ACCENT = "#5987FF"    # rgba(0.35, 0.53, 1.0, 1)
_BTN_BG = "#0d0d12"
_BTN_HOVER = "#1a1f3a"

# Menu dimensions
_MENU_WIDTH = 260
_MENU_BASE_HEIGHT = 50
_BUTTON_HEIGHT = 56
_BUTTON_W = 220
_BUTTON_H = 42
_UPDATE_INTERVAL_MS = 10
_CLEANUP_WAIT_MS = 200


def _draw_rounded_rect(canvas, x1, y1, x2, y2, r=8, **kwargs):
    """Rounded rectangle via smooth polygon (tkinter canvas)."""
    points = [
        x1 + r, y1,   x2 - r, y1,
        x2,     y1,   x2,     y1 + r,
        x2,     y2 - r, x2,   y2,
        x2 - r, y2,   x1 + r, y2,
        x1,     y2,   x1,     y2 - r,
        x1,     y1 + r, x1,   y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


class DesignerMenu:
    def __init__(self, monitor_info: dict, show_end_input: bool = False, on_choice_callback=None):
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

        button_count = 4 if self.show_end_input else 3
        w = _MENU_WIDTH
        h = _MENU_BASE_HEIGHT + (button_count * _BUTTON_HEIGHT)
        x = self.monitor_info['left'] + (self.monitor_info['width'] - w) // 2
        y = self.monitor_info['top'] + (self.monitor_info['height'] - h) // 2
        self.window.geometry(f"{w}x{h}+{x}+{y}")

        tk.Label(self.window, text="Designer Menu", fg=_FG, bg=_BG,
                 font=("Segoe UI", 10, "bold")).pack(pady=(10, 15))

        buttons_frame = tk.Frame(self.window, bg=_BG)
        buttons_frame.pack(padx=10, pady=0)

        self._create_button(buttons_frame, "Resume Recording", lambda: self._on_choice('resume'))
        self._create_button(buttons_frame, "Refresh Screenshot", lambda: self._on_choice('refresh'))
        if self.show_end_input:
            self._create_button(buttons_frame, "End Input", lambda: self._on_choice('end_input'))
        self._create_button(buttons_frame, "End Session", lambda: self._on_choice('end_session'))

        while not self.should_close:
            try:
                self.window.update()
            except Exception:
                break
            time.sleep(_UPDATE_INTERVAL_MS / 1000)

        try:
            self.window.destroy()
        except Exception:
            pass
        self.window = None
        time.sleep(_CLEANUP_WAIT_MS / 1000)
        gc.collect()

        if self.choice and self.on_choice_callback:
            self.on_choice_callback(self.choice)

    def close(self):
        """Close the menu window safely from another thread."""
        self.should_close = True

    def _create_button(self, parent, text, command):
        """Bottone outlined stile Kivy: sfondo scuro + bordo blu arrotondato."""
        c = tk.Canvas(parent, width=_BUTTON_W, height=_BUTTON_H,
                      bg=_BG, highlightthickness=0, cursor="hand2")

        rect_id = _draw_rounded_rect(c, 2, 2, _BUTTON_W - 2, _BUTTON_H - 2,
                                     r=8, fill=_BTN_BG, outline=_ACCENT, width=2)
        text_id = c.create_text(_BUTTON_W // 2, _BUTTON_H // 2, text=text,
                                fill=_FG, font=("Segoe UI", 9, "bold"))

        def on_enter(_e):
            c.itemconfig(rect_id, fill=_BTN_HOVER)

        def on_leave(_e):
            c.itemconfig(rect_id, fill=_BTN_BG)

        def on_click(_e):
            command()

        for tag in (rect_id, text_id):
            c.tag_bind(tag, "<Enter>", on_enter)
            c.tag_bind(tag, "<Leave>", on_leave)
            c.tag_bind(tag, "<Button-1>", on_click)

        c.bind("<Enter>", on_enter)
        c.bind("<Leave>", on_leave)
        c.bind("<Button-1>", on_click)

        c.pack(pady=5)

    def _on_choice(self, choice):
        """Callback quando utente sceglie."""
        self.choice = choice
        self.should_close = True
