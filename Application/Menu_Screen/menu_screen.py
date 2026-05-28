import os
from kivy.uix.screenmanager import Screen
from kivy.lang import Builder

Builder.load_file(os.path.join(os.path.dirname(__file__), "menu_screen.kv"))


class MenuScreen(Screen):
    SCREEN_NAME = "menu"

    def go_designer(self):
        self.manager.transition.direction = "left"
        self.manager.current = "create_designer"

    def go_designer_open(self):
        self.manager.transition.direction = "left"
        self.manager.current = "open_designer"

    def go_designer_aggregate(self):
        self.manager.transition.direction = "left"
        self.manager.current = "aggregate_designer"

    def go_execution(self):
        self.manager.transition.direction = "left"
        self.manager.current = "create_execution"

    def go_execution_open(self):
        self.manager.transition.direction = "left"
        self.manager.current = "open_execution"

    def go_test_suite(self):
        print("→ Navigating to: Test Suite (not yet implemented)")
        self.manager.transition.direction = "left"
        # self.manager.current = "test_suite"

    def go_last_test_suite(self):
        print("→ Navigating to: Last Test Suite (not yet implemented)")
        self.manager.transition.direction = "left"
        # self.manager.current = "last_test_suite"

    def go_test_specific(self):
        print("→ Navigating to: Test Specific (not yet implemented)")
        self.manager.transition.direction = "left"
        # self.manager.current = "test_specific"

    def go_last_test_case(self):
        print("→ Navigating to: Last Test Case (not yet implemented)")
        self.manager.transition.direction = "left"
        # self.manager.current = "last_test_case"

    def go_settings(self):
        print("→ Navigating to: Settings")
        self.manager.transition.direction = "right"
        self.manager.current = "settings"
