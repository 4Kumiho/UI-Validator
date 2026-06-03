import os
import sys
from pathlib import Path
from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty
from kivy.lang import Builder

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from Databases.designer_database import DesignerDatabase

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
        folder = self._browse_folder_dialog(title="Select Designer 1 folder")
        if folder:
            self.ids.designer1_input.text = folder

    def browse_designer2(self):
        """Open folder browser dialog for Designer 2"""
        folder = self._browse_folder_dialog(title="Select Designer 2 folder")
        if folder:
            self.ids.designer2_input.text = folder

    def browse_save_folder(self):
        """Open folder browser dialog for save location"""
        folder = self._browse_folder_dialog(title="Select save location")
        if folder:
            self.ids.save_path_input.text = folder

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

        # Validate that both folders have .db files
        try:
            folder1 = Path(designer1)
            folder2 = Path(designer2)

            db_files1 = list(folder1.glob("*.db"))
            db_files2 = list(folder2.glob("*.db"))

            if not db_files1:
                self.error_msg = "No .db file found in Designer 1 folder"
                return

            if not db_files2:
                self.error_msg = "No .db file found in Designer 2 folder"
                return

            db_path1 = str(db_files1[0])
            db_path2 = str(db_files2[0])

            # Check zoom and resolution match
            db1 = DesignerDatabase(db_path1)
            db2 = DesignerDatabase(db_path2)

            try:
                session1 = db1.get_session()
                session2 = db2.get_session()

                res1 = session1.Screen_resolution if session1 else "unknown"
                zoom1 = session1.Screen_zoom if session1 else "1.0"

                res2 = session2.Screen_resolution if session2 else "unknown"
                zoom2 = session2.Screen_zoom if session2 else "1.0"

                # Convert to string for comparison
                res1_str = str(res1)
                zoom1_str = str(zoom1)
                res2_str = str(res2)
                zoom2_str = str(zoom2)

                if res1_str != res2_str:
                    self.error_msg = f"Resolution mismatch: Designer 1={res1_str}, Designer 2={res2_str}"
                    return

                if zoom1_str != zoom2_str:
                    self.error_msg = f"Zoom mismatch: Designer 1={zoom1_str}, Designer 2={zoom2_str}"
                    return

            finally:
                db1.close()
                db2.close()

            # Validation OK
            self.error_msg = "✓ Validation OK - Aggregating designer sessions"

        except Exception as e:
            self.error_msg = f"Error validating sessions: {str(e)}"
            print(f"[Error] {e}")
            import traceback
            traceback.print_exc()
