import os
from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty
from kivy.lang import Builder
from tkinter import Tk, filedialog

Builder.load_file(os.path.join(os.path.dirname(__file__), "open_execution_screen.kv"))


class OpenExecutionScreen(Screen):
    SCREEN_NAME = "open_execution"
    error_msg = StringProperty("")

    def on_enter(self):
        self.error_msg = ""

    def go_back(self):
        self.manager.current = "menu"

    def browse_folder(self):
        try:
            root = Tk()
            root.withdraw()
            folder = filedialog.askdirectory(title="Select execution folder")
            root.destroy()

            if folder:
                self.ids.execution_folder_input.text = folder
        except Exception as e:
            print(f"[Error] Browse folder: {e}")

    def open_execution(self):
        execution_folder = self.ids.execution_folder_input.text.strip()

        self.error_msg = ""

        if not execution_folder:
            self.error_msg = "Execution folder is required"
            return

        self.error_msg = "✓ Validation OK - Opening execution"
