import os
from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty
from kivy.lang import Builder

Builder.load_file(os.path.join(os.path.dirname(__file__), "create_execution_screen.kv"))


class CreateExecutionScreen(Screen):
    SCREEN_NAME = "create_execution"
    error_msg = StringProperty("")

    def on_enter(self):
        self.error_msg = ""

    def go_back(self):
        self.manager.current = "menu"

    def browse_folder(self):
        folder = self._browse_folder_dialog(title="Select save location")
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

    def start_execution(self):
        session_name = self.ids.name_input.text.strip()
        save_folder = self.ids.output_folder_input.text.strip()

        self.error_msg = ""

        if not session_name:
            self.error_msg = "Session name is required"
            return

        if not save_folder:
            self.error_msg = "Save folder is required"
            return

        self.error_msg = "✓ Validation OK - Execution ready"
