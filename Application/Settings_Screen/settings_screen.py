import os
import sys
import json
from kivy.uix.screenmanager import Screen
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.lang import Builder
from kivy.properties import StringProperty, BooleanProperty, ListProperty
from kivy.metrics import dp

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

SETTINGS_PATH = os.path.join(PROJECT_ROOT, "settings.json")

Builder.load_file(os.path.join(os.path.dirname(__file__), "settings_screen.kv"))


class SettingsScreen(Screen):
    SCREEN_NAME = "settings"
    open_menu_key = StringProperty("esc")
    refresh_screenshot_key = StringProperty("f9")
    end_input_key = StringProperty("f8")
    end_designer_key = StringProperty("f7")

    # Available keys
    AVAILABLE_KEYS = (
        ['esc'] +
        [f'f{i}' for i in range(1, 13)] +
        ['tab', 'home', 'end', 'pageup', 'pagedown', 'delete', 'insert'] +
        ['ctrl', 'shift', 'alt']
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_keys_open_menu = {}
        self.selected_keys_refresh = {}
        self.selected_keys_end_input = {}
        self.selected_keys_end_designer = {}

    def on_enter(self):
        """Load settings from JSON when entering screen"""
        self.load_settings()


    def load_settings(self):
        """Read current settings from settings.json"""
        try:
            with open(SETTINGS_PATH, 'r') as f:
                settings = json.load(f)
            designer = settings.get("designer", {})

            self.open_menu_key = designer.get("open_menu_key", "esc")
            self.refresh_screenshot_key = designer.get("refresh_sreenshot_key_shortcut", "f9")
            self.end_input_key = designer.get("end_input_key_shortcut", "f7")
            self.end_designer_key = designer.get("end_designer_key_shortcut", "f8")

            self._parse_key_combo(self.open_menu_key, self.selected_keys_open_menu)
            self._parse_key_combo(self.refresh_screenshot_key, self.selected_keys_refresh)
            self._parse_key_combo(self.end_input_key, self.selected_keys_end_input)
            self._parse_key_combo(self.end_designer_key, self.selected_keys_end_designer)
        except Exception as e:
            print(f"[ERROR] Failed to load settings: {e}")

    def _parse_key_combo(self, combo_str: str, selected_dict: dict):
        """Parse key combo string (e.g., 'ctrl+shift+d') into components"""
        selected_dict.clear()
        for key in self.AVAILABLE_KEYS:
            selected_dict[key] = False

        parts = combo_str.lower().split('+')
        for part in parts:
            if part in selected_dict:
                selected_dict[part] = True

    def _build_key_combo(self, selected_dict: dict) -> str:
        """Build key combo string from selected keys dict"""
        parts = []
        if selected_dict.get('ctrl', False):
            parts.append("ctrl")
        if selected_dict.get('shift', False):
            parts.append("shift")
        if selected_dict.get('alt', False):
            parts.append("alt")

        for key in self.AVAILABLE_KEYS:
            if key not in ['ctrl', 'shift', 'alt'] and selected_dict.get(key, False):
                parts.append(key)

        if not parts:
            parts = ['esc']  # Default

        return "+".join(parts)

    def show_popup_open_menu(self):
        """Open popup for open_menu_key"""
        self._show_key_popup('open_menu', self.selected_keys_open_menu, self.open_menu_key)

    def show_popup_refresh_screenshot(self):
        """Open popup for refresh_screenshot_key"""
        self._show_key_popup('refresh', self.selected_keys_refresh, self.refresh_screenshot_key)

    def show_popup_end_input(self):
        """Open popup for end_input_key"""
        self._show_key_popup('end_input', self.selected_keys_end_input, self.end_input_key)

    def show_popup_end_designer(self):
        """Open popup for end_designer_key"""
        self._show_key_popup('end_designer', self.selected_keys_end_designer, self.end_designer_key)

    def _show_key_popup(self, field_type: str, selected_dict: dict, current_value: str):
        """Show popup with key selector checkboxes"""
        saved_value = current_value

        content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(15))

        # Scrollable checkbox list
        scroll = ScrollView(size_hint=(1, 0.8))
        checkbox_layout = GridLayout(cols=1, spacing=dp(10), size_hint_y=None, padding=dp(10))
        checkbox_layout.bind(minimum_height=checkbox_layout.setter('height'))

        for key in self.AVAILABLE_KEYS:
            row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(15))

            checkbox = CheckBox(
                size_hint_x=None,
                width=dp(30),
                active=selected_dict.get(key, False)
            )

            label = Label(
                text=key.upper(),
                size_hint_x=1,
                halign='left',
                valign='center',
                font_size='12sp',
                color=(1, 1, 1, 1)
            )

            def make_callback(k, sd):
                def on_checkbox_change(checkbox, value):
                    sd[k] = value
                    self._update_property(field_type, sd)
                return on_checkbox_change

            checkbox.bind(active=make_callback(key, selected_dict))
            row.add_widget(checkbox)
            row.add_widget(label)
            checkbox_layout.add_widget(row)

        scroll.add_widget(checkbox_layout)
        content.add_widget(scroll)

        # Buttons at bottom
        btn_layout = BoxLayout(size_hint_y=0.2, spacing=dp(15), padding=dp(10))

        cancel_btn = Button(
            text='CANCEL',
            background_color=(0.3, 0.3, 0.3, 1),
            color=(1, 1, 1, 1),
            bold=True,
            font_size='12sp'
        )
        done_btn = Button(
            text='DONE',
            background_color=(0.35, 0.53, 1.0, 1),
            color=(1, 1, 1, 1),
            bold=True,
            font_size='12sp'
        )

        btn_layout.add_widget(cancel_btn)
        btn_layout.add_widget(done_btn)
        content.add_widget(btn_layout)

        popup = Popup(
            title='Select Keys',
            content=content,
            size_hint=(0.8, 0.8),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )

        done_btn.bind(on_press=popup.dismiss)
        cancel_btn.bind(on_press=lambda x: self._parse_key_combo(saved_value, selected_dict))
        cancel_btn.bind(on_press=lambda x: self._update_property(field_type, selected_dict))
        cancel_btn.bind(on_press=popup.dismiss)

        popup.open()

    def _update_property(self, field_type: str, selected_dict: dict):
        """Update the property based on field_type"""
        new_value = self._build_key_combo(selected_dict)
        if field_type == 'open_menu':
            self.open_menu_key = new_value
        elif field_type == 'refresh':
            self.refresh_screenshot_key = new_value
        elif field_type == 'end_input':
            self.end_input_key = new_value
        elif field_type == 'end_designer':
            self.end_designer_key = new_value

    def set_defaults(self):
        """Reset all settings to default values"""
        self.open_menu_key = "esc"
        self.refresh_screenshot_key = "f9"
        self.end_input_key = "f8"
        self.end_designer_key = "f7"

        self._parse_key_combo(self.open_menu_key, self.selected_keys_open_menu)
        self._parse_key_combo(self.refresh_screenshot_key, self.selected_keys_refresh)
        self._parse_key_combo(self.end_input_key, self.selected_keys_end_input)
        self._parse_key_combo(self.end_designer_key, self.selected_keys_end_designer)

        print("[OK] Settings reset to defaults")

    def save_settings(self):
        """Save settings to JSON and go back"""
        try:
            with open(SETTINGS_PATH, 'r') as f:
                settings = json.load(f)

            settings["designer"]["open_menu_key"] = self.open_menu_key
            settings["designer"]["refresh_sreenshot_key_shortcut"] = self.refresh_screenshot_key
            settings["designer"]["end_input_key_shortcut"] = self.end_input_key
            settings["designer"]["end_designer_key_shortcut"] = self.end_designer_key

            with open(SETTINGS_PATH, 'w') as f:
                json.dump(settings, f, indent=2)

            print(f"[OK] Settings saved:")
            print(f"  open_menu_key: {self.open_menu_key}")
            print(f"  refresh_screenshot_key: {self.refresh_screenshot_key}")
            print(f"  end_input_key: {self.end_input_key}")
            print(f"  end_designer_key: {self.end_designer_key}")
            self.go_back()
        except Exception as e:
            print(f"[ERROR] Failed to save settings: {e}")

    def go_back(self):
        """Go back to menu"""
        self.manager.transition.direction = "right"
        self.manager.current = "menu"
