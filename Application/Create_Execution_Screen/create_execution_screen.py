import os
from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty
from kivy.lang import Builder
from tkinter import Tk, filedialog

Builder.load_file(os.path.join(os.path.dirname(__file__), "create_execution_screen.kv"))


class CreateExecutionScreen(Screen):
    SCREEN_NAME = "create_execution"
    error_msg = StringProperty("")

    def on_enter(self):
        self.error_msg = ""

    def go_back(self):
        self.manager.current = "menu"

    def browse_folder(self):
        try:
            root = Tk()
            root.withdraw()
            folder = filedialog.askdirectory(title="Select save location")
            root.destroy()

            if folder:
                self.ids.output_folder_input.text = folder
        except Exception as e:
            print(f"[Error] Browse folder: {e}")

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
