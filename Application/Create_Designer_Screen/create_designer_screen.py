import os
import sys
import json
import threading
from pathlib import Path
from kivy.uix.screenmanager import Screen
from kivy.uix.spinner import SpinnerOption
from kivy.properties import StringProperty
from kivy.lang import Builder
from kivy.factory import Factory

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

SETTINGS_PATH = os.path.join(PROJECT_ROOT, "settings.json")

from Designer.designer import Designer
from Application.Create_Designer_Screen.designer_utils import DesignerScreenMixin

# Style spinner options
class StyledSpinnerOption(SpinnerOption):
    pass

Builder.load_string("""
<StyledSpinnerOption>:
    background_color: 0.12, 0.12, 0.22, 1
    background_normal: ''
    color: 0.9, 0.9, 1, 1
    font_size: '13sp'
""")
Factory.register('StyledSpinnerOption', cls=StyledSpinnerOption)

Builder.load_file(os.path.join(os.path.dirname(__file__), "create_designer_screen.kv"))


class CreateDesignerScreen(DesignerScreenMixin, Screen):
    SCREEN_NAME = "create_designer"
    error_msg = StringProperty("")

    def on_enter(self):
        """Load monitors and clear error message"""
        self.error_msg = ""
        self.refresh_monitors()

    def browse_folder(self):
        """Open folder browser dialog"""
        folder = DesignerScreenMixin.browse_folder(title="Select save location")
        if folder:
            self.ids.output_folder_input.text = folder

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
        self.error_msg = "✓ Launching Designer..."
        self._launch_designer(session_name, save_folder, monitor_text)

    def _launch_designer(self, session_name: str, save_folder: str, monitor_text: str):
        """Launch Designer in daemon thread"""
        try:
            # Get selected monitor info
            monitor_index = self.get_monitor_index(monitor_text)
            monitor_info = self.monitors_data[monitor_index].copy()

            # Load settings from JSON
            try:
                with open(SETTINGS_PATH, 'r') as f:
                    app_settings = json.load(f)
                menu_key = app_settings.get("designer", {}).get("open_menu_key", "ctrl+shift+d")
            except Exception as e:
                print(f"[WARN] Failed to load settings.json: {e}")
                menu_key = "ctrl+shift+d"

            settings = {
                "Open_Designer_Menu_key": menu_key
            }

            # Get models from registry (caricati da LoadingScreen)
            from Models.model_registry import get_model
            ocr_model = get_model('ocr')
            efficientnet_model = get_model('efficientnet')
            layoutlm_result = get_model('layoutlm')
            layoutlm_model, layoutlm_processor = layoutlm_result if layoutlm_result else (None, None)
            sam_model = get_model('sam')
            clip_result = get_model('clip')
            clip_model, clip_preprocess = clip_result if clip_result else (None, None)

            # Debug logging
            print(f"[DEBUG] OCR model: {type(ocr_model).__name__ if ocr_model else 'None'}")
            print(f"[DEBUG] EfficientNet model: {type(efficientnet_model).__name__ if efficientnet_model else 'None'}")
            print(f"[DEBUG] LayoutLMv3 model: {type(layoutlm_model).__name__ if layoutlm_model else 'None'}")
            print(f"[DEBUG] SAM model: {type(sam_model).__name__ if sam_model else 'None'}")
            print(f"[DEBUG] CLIP model: {type(clip_model).__name__ if clip_model else 'None'}")

            # Minimize Kivy before launching
            self.minimize_window()

            # Launch Designer with models as thread args
            def run_designer():
                designer = Designer(
                    session_name, save_folder, monitor_info, settings,
                    ocr_model=ocr_model,
                    efficientnet_model=efficientnet_model,
                    layoutlm_model=layoutlm_model,
                    layoutlm_processor=layoutlm_processor,
                    sam_model=sam_model,
                    clip_model=clip_model,
                    clip_preprocess=clip_preprocess
                )
                designer.start()

            designer_thread = threading.Thread(target=run_designer, daemon=True)
            designer_thread.start()

            # Restore window after designer finishes (in another thread)
            def wait_and_restore():
                designer_thread.join()
                self.restore_window()

            threading.Thread(target=wait_and_restore, daemon=True).start()

        except Exception as e:
            self.error_msg = f"Error launching Designer: {str(e)}"
            print(f"[Error] {e}")
            import traceback
            traceback.print_exc()
