"""Utility functions for Designer."""

import os
import platform

try:
    from kivy.core.window import Window
    HAS_KIVY = True
except ImportError:
    HAS_KIVY = False


class DesignerScreenMixin:
    """Mixin per metodi comuni designer screens."""

    def go_back(self):
        """Torna al menu."""
        self.manager.current = "menu"

    def minimize_window(self):
        """Minimizza finestra Kivy."""
        try:
            if not HAS_KIVY:
                return
            if os.name == 'nt':
                import ctypes
                hwnd = ctypes.windll.user32.FindWindowW(None, "UI-Validator")
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 6)  # 6 = SW_MINIMIZE
        except Exception as e:
            print(f"[Warning] Could not minimize window: {e}")

    def restore_window(self):
        """Ripristina finestra Kivy."""
        try:
            if not HAS_KIVY:
                return
            if os.name == 'nt':
                import ctypes
                hwnd = ctypes.windll.user32.FindWindowW(None, "UI-Validator")
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 9)  # 9 = SW_RESTORE
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception as e:
            print(f"[Warning] Could not restore window: {e}")

    @staticmethod
    def get_system_zoom(monitor_index: int = 0) -> int:
        """Detecta zoom level del monitor."""
        if os.name == 'nt':
            try:
                from mss import mss
                with mss() as sct:
                    if monitor_index + 1 < len(sct.monitors):
                        mon = sct.monitors[monitor_index + 1]
                        if 'pixel_ratio' in mon and mon['pixel_ratio'] is not None:
                            return round(mon['pixel_ratio'] * 100)

                    from ctypes import windll, POINTER, c_uint, WINFUNCTYPE, c_bool
                    from ctypes.wintypes import HMONITOR, RECT

                    monitors = []
                    MonitorEnumProc = WINFUNCTYPE(c_bool, HMONITOR, c_uint, POINTER(RECT), c_uint)

                    def callback(hmonitor, hdc, rect, data):
                        monitors.append(hmonitor)
                        return True

                    windll.user32.EnumDisplayMonitors(None, None, MonitorEnumProc(callback), 0)

                    if monitor_index < len(monitors):
                        hmonitor = monitors[monitor_index]
                        dpi_x = c_uint()
                        dpi_y = c_uint()
                        windll.shcore.GetDpiForMonitor(hmonitor, 0, POINTER(c_uint)(dpi_x), POINTER(c_uint)(dpi_y))
                        if dpi_x.value > 0:
                            return round((dpi_x.value / 96.0) * 100)
            except Exception:
                pass
            return 100
        return 100

    def refresh_monitors(self):
        """Enumera i monitor e popola lo spinner."""
        try:
            from mss import mss
            with mss() as sct:
                monitors = sct.monitors[1:]
                self.monitors_data = []
                spinner = self.ids.monitor_spinner
                values = []
                for i, m in enumerate(monitors):
                    monitor_copy = m.copy()
                    zoom = self.get_system_zoom(monitor_index=i)
                    monitor_copy['pixel_ratio'] = zoom / 100.0
                    self.monitors_data.append(monitor_copy)
                    values.append(f"Monitor {i + 1}  ({m['width']}×{m['height']})  —  {zoom}%")
                spinner.values = values
                if spinner.values:
                    spinner.text = spinner.values[0]
        except Exception as e:
            print(f"[ERROR] refresh_monitors failed: {e}")

    @staticmethod
    def get_monitor_index(monitor_text: str) -> int:
        """Estrae indice del monitor dal testo spinner."""
        try:
            parts = monitor_text.split("(")
            if len(parts) > 0:
                monitor_part = parts[0].strip()
                monitor_num = int(monitor_part.replace("Monitor", "").strip())
                return monitor_num - 1
        except Exception:
            pass
        return 0

    @staticmethod
    def browse_folder(title: str = "Seleziona cartella") -> str:
        """Apre file dialog per scegliere cartella."""
        result = [None]

        def _open_dialog():
            try:
                import time
                from tkinter import filedialog, Tk

                root = Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                time.sleep(0.1)

                folder = filedialog.askdirectory(title=title)

                root.quit()
                time.sleep(0.1)
                root.destroy()
                time.sleep(0.1)

                result[0] = folder if folder else ""
            except Exception as e:
                print(f"[browse_folder] Error: {e}")
                result[0] = ""

        import threading
        thread = threading.Thread(target=_open_dialog, daemon=False)
        thread.start()
        thread.join()

        return result[0] if result[0] else ""
