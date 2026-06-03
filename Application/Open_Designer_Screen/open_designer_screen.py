import os
from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty
from kivy.lang import Builder

Builder.load_file(os.path.join(os.path.dirname(__file__), "open_designer_screen.kv"))


class OpenDesignerScreen(Screen):
    SCREEN_NAME = "open_designer"
    error_msg = StringProperty("")

    def on_enter(self):
        """Clear error message when entering screen"""
        self.error_msg = ""

    def go_back(self):
        """Return to menu screen"""
        self.manager.current = "menu"

    def browse_folder(self):
        """Open folder browser dialog"""
        folder = self._browse_folder_dialog(title="Select designer folder")
        if folder:
            self.ids.designer_folder_input.text = folder

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

    def start_opening(self):
        """Validate input and open designer session summary"""
        designer_folder = self.ids.designer_folder_input.text.strip()

        self.error_msg = ""

        if not designer_folder:
            self.error_msg = "Designer folder is required"
            return

        try:
            from pathlib import Path
            folder = Path(designer_folder)
            db_files = list(folder.glob("*.db"))

            if not db_files:
                self.error_msg = "No .db file found in selected folder"
                return

            db_path = str(db_files[0])
            session_name = db_files[0].stem.replace("_designer", "")

            summary = self.manager.get_screen('summary_designer')
            summary.load_session(db_path, session_name)
            self.manager.current = 'summary_designer'

        except Exception as e:
            self.error_msg = f"Error opening session: {str(e)}"
            print(f"[Error] {e}")
