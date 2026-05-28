import os
from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty
from kivy.lang import Builder
from tkinter import Tk, filedialog

Builder.load_file(os.path.join(os.path.dirname(__file__), "aggregate_designer_screen.kv"))


class AggregateDesignerScreen(Screen):
    SCREEN_NAME = "aggregate_designer"
    error_msg = StringProperty("")

    def on_enter(self):
        """Clear error message when entering screen"""
        self.error_msg = ""

    def go_back(self):
        """Return to menu screen"""
        self.manager.current = "menu"

    def browse_designer1(self):
        """Open folder browser dialog for Designer 1"""
        try:
            root = Tk()
            root.withdraw()
            folder = filedialog.askdirectory(title="Select Designer 1 folder")
            root.destroy()

            if folder:
                self.ids.designer1_input.text = folder
        except Exception as e:
            print(f"[Error] Browse folder: {e}")

    def browse_designer2(self):
        """Open folder browser dialog for Designer 2"""
        try:
            root = Tk()
            root.withdraw()
            folder = filedialog.askdirectory(title="Select Designer 2 folder")
            root.destroy()

            if folder:
                self.ids.designer2_input.text = folder
        except Exception as e:
            print(f"[Error] Browse folder: {e}")

    def browse_save_folder(self):
        """Open folder browser dialog for save location"""
        try:
            root = Tk()
            root.withdraw()
            folder = filedialog.askdirectory(title="Select save location")
            root.destroy()

            if folder:
                self.ids.save_path_input.text = folder
        except Exception as e:
            print(f"[Error] Browse folder: {e}")

    def start_aggregating(self):
        """Validate input and show validation message"""
        designer_name = self.ids.designer_name_input.text.strip()
        designer1 = self.ids.designer1_input.text.strip()
        designer2 = self.ids.designer2_input.text.strip()
        save_path = self.ids.save_path_input.text.strip()

        # Reset error
        self.error_msg = ""

        # Validation
        if not designer_name:
            self.error_msg = "Designer name is required"
            return

        if not designer1:
            self.error_msg = "Designer 1 folder is required"
            return

        if not designer2:
            self.error_msg = "Designer 2 folder is required"
            return

        if not save_path:
            self.error_msg = "Save location is required"
            return

        # Validation OK
        self.error_msg = "✓ Validation OK - Aggregating designer sessions"
