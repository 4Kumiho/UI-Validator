import os
import sys
import json
import threading
from pathlib import Path
from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty
from kivy.lang import Builder

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

SETTINGS_PATH = os.path.join(PROJECT_ROOT, "settings.json")

Builder.load_file(os.path.join(os.path.dirname(__file__), "create_execution_screen.kv"))


class CreateExecutionScreen(Screen):
    SCREEN_NAME = "create_execution"
    error_msg = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.designer_db_path = None

    def on_enter(self):
        self.error_msg = ""

    def go_back(self):
        self.manager.current = "menu"

    def browse_designer_db(self):
        """Browse for Designer database file"""
        db_file = self._browse_file_dialog(title="Select Designer Database", filter_patterns=["*.db"])
        if db_file:
            self.ids.designer_db_input.text = db_file
            self.designer_db_path = db_file

    def browse_folder(self):
        """Browse for execution save folder"""
        folder = self._browse_folder_dialog(title="Select execution save location")
        if folder:
            self.ids.output_folder_input.text = folder

    @staticmethod
    def _browse_folder_dialog(title: str = "Select folder") -> str:
        """Open file dialog to select folder (cross-platform)."""
        try:
            from plyer import filechooser
            result = filechooser.choose_dir(title=title)
            return result[0] if result else ""
        except Exception as e:
            print(f"[browse_folder] Error: {e}")
            return ""

    @staticmethod
    def _browse_file_dialog(title: str = "Select file", filter_patterns=None) -> str:
        """Open file dialog to select file (cross-platform)."""
        try:
            from plyer import filechooser
            result = filechooser.open_file(title=title, filters=filter_patterns or ["*.*"])
            return result[0] if result else ""
        except Exception as e:
            print(f"[browse_file] Error: {e}")
            return ""

    def start_execution(self):
        session_name = self.ids.name_input.text.strip()
        designer_db_path = self.ids.designer_db_input.text.strip()
        save_folder = self.ids.output_folder_input.text.strip()

        self.error_msg = ""

        # Validation
        if not session_name:
            self.error_msg = "Session name is required"
            return

        if not designer_db_path:
            self.error_msg = "Designer database is required"
            return

        if not Path(designer_db_path).exists():
            self.error_msg = "Designer database file not found"
            return

        if not save_folder:
            self.error_msg = "Save folder is required"
            return

        # Create execution session folder
        try:
            execution_folder = Path(save_folder) / session_name
            execution_folder.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.error_msg = f"Error creating execution folder: {str(e)}"
            return

        # Get monitor info
        try:
            from mss import mss
            with mss() as sct:
                monitors = sct.monitors[1:]
                if not monitors:
                    self.error_msg = "No monitors found"
                    return
                # Use first monitor by default
                monitor_info = monitors[0].copy()
                zoom = self._get_system_zoom(monitor_index=0)
                monitor_info['pixel_ratio'] = zoom / 100.0
        except Exception as e:
            self.error_msg = f"Error detecting monitor: {str(e)}"
            return

        # Launch executor in daemon thread
        self._launch_executor(
            designer_db_path,
            str(execution_folder),
            monitor_info
        )

    def _launch_executor(self, designer_db_path: str, execution_session_folder: str, monitor_info: dict):
        """Launch Executor in daemon thread"""
        try:
            # Load settings
            try:
                with open(SETTINGS_PATH, 'r') as f:
                    settings = json.load(f)
            except Exception as e:
                print(f"[WARN] Failed to load settings.json: {e}")
                settings = {'execution': {}}

            def run_executor():
                try:
                    from Execution.executor import Executor

                    executor = Executor(
                        designer_db_path=designer_db_path,
                        execution_session_folder=execution_session_folder,
                        monitor_info=monitor_info,
                        settings=settings
                    )
                    executor.start()
                    print("[EXECUTOR] Execution completed")
                except Exception as e:
                    print(f"[EXECUTOR] Error: {e}")
                    import traceback
                    traceback.print_exc()

            threading.Thread(target=run_executor, daemon=True).start()
            self.error_msg = "✓ Execution started"

        except Exception as e:
            self.error_msg = f"Error launching Executor: {str(e)}"
            print(f"[Error] {e}")
            import traceback
            traceback.print_exc()

    @staticmethod
    def _get_system_zoom(monitor_index: int = 0) -> int:
        """Detect monitor zoom level."""
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
