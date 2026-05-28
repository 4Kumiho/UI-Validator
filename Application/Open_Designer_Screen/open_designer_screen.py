import os
from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty
from kivy.lang import Builder
from tkinter import Tk, filedialog

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
        try:
            root = Tk()
            root.withdraw()
            folder = filedialog.askdirectory(title="Select designer folder")
            root.destroy()

            if folder:
                self.ids.designer_folder_input.text = folder
        except Exception as e:
            print(f"[Error] Browse folder: {e}")

    def start_opening(self):
        """Validate input and show validation message"""
        designer_folder = self.ids.designer_folder_input.text.strip()

        # Reset error
        self.error_msg = ""

        # Validation
        if not designer_folder:
            self.error_msg = "Designer folder is required"
            return

        # Validation OK
        self.error_msg = "✓ Validation OK - Opening designer session"
