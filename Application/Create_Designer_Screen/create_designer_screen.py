import os
import sys
import json
import threading
from pathlib import Path
from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty
from kivy.lang import Builder

try:
    from kivy.core.window import Window
    HAS_KIVY = True
except ImportError:
    HAS_KIVY = False

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

SETTINGS_PATH = os.path.join(PROJECT_ROOT, "settings.json")

from Designer.designer import Designer

Builder.load_string("""
<StyledSpinnerOption@SpinnerOption>:
    background_color: 0.12, 0.12, 0.22, 1
    background_normal: ''
    color: 0.9, 0.9, 1, 1
    font_size: '13sp'
""")

Builder.load_file(os.path.join(os.path.dirname(__file__), "create_designer_screen.kv"))


class CreateDesignerScreen(Screen):
    SCREEN_NAME = "create_designer"
    error_msg = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.monitors_data = []

    def on_enter(self):
        """Load monitors and clear error message"""
        self.error_msg = ""
        self.refresh_monitors()

    # ===== UI Actions (user-triggered) =====
    def browse_folder(self):
        """Open folder browser dialog"""
        folder = self._browse_folder_dialog(title="Select save location")
        if folder:
            self.ids.output_folder_input.text = folder

    def go_back(self):
        """Torna al menu."""
        self.manager.current = "menu"

    def start_recording(self):
        """Validate input and launch Designer"""
        session_name = self.ids.name_input.text.strip()
        save_folder = self.ids.output_folder_input.text.strip()
        monitor_text = self.ids.monitor_spinner.text

        # Reset error
        self.error_msg = ""

        # Validation
        if not session_name:
            self.error_msg = "Session name is required"
            return

        if not save_folder:
            self.error_msg = "Save folder is required"
            return

        if not monitor_text or monitor_text == "Select monitor":
            self.error_msg = "Monitor selection is required"
            return

        # Check if session already exists
        project_folder = Path(save_folder) / session_name
        if project_folder.exists():
            self.error_msg = "Designer with this name already exists"
            return

        # Validation OK - launch Designer
        self._launch_designer(session_name, save_folder, monitor_text)

    # ===== Monitor Management =====
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

    # ===== Designer Launch =====
    def _launch_designer(self, session_name: str, save_folder: str, monitor_text: str):
        """Launch Designer in daemon thread"""
        try:
            monitor_index = self.get_monitor_index(monitor_text)
            monitor_info = self.monitors_data[monitor_index].copy()

            # Load settings from JSON
            try:
                with open(SETTINGS_PATH, 'r') as f:
                    settings = json.load(f).get("designer", {})
            except Exception as e:
                print(f"[WARN] Failed to load settings.json: {e}")
                settings = {}

            # Get models from registry
            from Models.model_registry import get_model
            models = {
                'ocr': get_model('ocr'),
                'efficientnet': get_model('efficientnet'),
                'sam': get_model('sam'),
            }

            layoutlm_result = get_model('layoutlm')
            models['layoutlm'], models['layoutlm_processor'] = (layoutlm_result if layoutlm_result else (None, None))

            clip_result = get_model('clip')
            models['clip'], models['clip_preprocess'] = (clip_result if clip_result else (None, None))

            # Check if critical models are loaded
            if not models['ocr'] or not models['efficientnet'] or not models['sam']:
                self.error_msg = "Modelli non caricati. Riavviare la app."
                return

            # Debug logging
            for name, model in [('ocr', models['ocr']), ('efficientnet', models['efficientnet']),
                               ('layoutlm', models['layoutlm']), ('sam', models['sam']), ('clip', models['clip'])]:
                print(f"[DEBUG] {name.upper()} model: {type(model).__name__ if model else 'None'}")

            self.minimize_window()

            def run_designer():
                designer = Designer(
                    session_name, save_folder, monitor_info,
                    settings,
                    ocr_model=models['ocr'],
                    efficientnet_model=models['efficientnet'],
                    layoutlm_model=models['layoutlm'],
                    layoutlm_processor=models['layoutlm_processor'],
                    sam_model=models['sam'],
                    clip_model=models['clip'],
                    clip_preprocess=models['clip_preprocess']
                )
                designer.start()
                self.restore_window()

            threading.Thread(target=run_designer, daemon=True).start()

        except Exception as e:
            self.error_msg = f"Error launching Designer: {str(e)}"
            print(f"[Error] {e}")
            import traceback
            traceback.print_exc()

    # ===== Window Management =====
    def minimize_window(self):
        """Minimizza finestra Kivy."""
        self._set_window_visibility(False)

    def restore_window(self):
        """Ripristina finestra Kivy."""
        self._set_window_visibility(True)

    @staticmethod
    def _set_window_visibility(show: bool):
        """Set window visibility (minimize/restore)."""
        try:
            if not HAS_KIVY or os.name != 'nt':
                return
            import ctypes
            hwnd = ctypes.windll.user32.FindWindowW(None, "UI-Validator")
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 9 if show else 6)  # 9=RESTORE, 6=MINIMIZE
                if show:
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception as e:
            print(f"[Warning] Could not set window visibility: {e}")

    # ===== Helper Methods =====
    @staticmethod
    def _browse_folder_dialog(title: str = "Seleziona cartella") -> str:
        """Apre file dialog per scegliere cartella."""
        result = [""]

        def _open_dialog():
            try:
                from tkinter import filedialog, Tk
                root = Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                folder = filedialog.askdirectory(title=title)
                result[0] = folder or ""
                root.destroy()
            except Exception as e:
                print(f"[browse_folder] Error: {e}")

        thread = threading.Thread(target=_open_dialog, daemon=False)
        thread.start()
        thread.join()
        return result[0]