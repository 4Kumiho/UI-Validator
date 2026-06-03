import os
from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty
from kivy.lang import Builder

Builder.load_file(os.path.join(os.path.dirname(__file__), "open_execution_screen.kv"))


class OpenExecutionScreen(Screen):
    SCREEN_NAME = "open_execution"
    error_msg = StringProperty("")

    def on_enter(self):
        self.error_msg = ""

    def go_back(self):
        self.manager.current = "menu"

    def browse_folder(self):
        folder = self._browse_folder_dialog(title="Select execution folder")
        if folder:
            self.ids.execution_folder_input.text = folder

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

    def open_execution(self):
        execution_folder = self.ids.execution_folder_input.text.strip()

        self.error_msg = ""

        if not execution_folder:
            self.error_msg = "Execution folder is required"
            return

        self.error_msg = "✓ Validation OK - Opening execution"
