import os
import sys

from kivy.app import App
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, FadeTransition

from Application.Loading_Screen.loading_screen import LoadingScreen
from Application.Menu_Screen.menu_screen import MenuScreen
from Application.Settings_Screen.settings_screen import SettingsScreen
from Application.Create_Designer_Screen.create_designer_screen import CreateDesignerScreen
from Application.Open_Designer_Screen.open_designer_screen import OpenDesignerScreen
from Application.Aggregate_Designer_Screen.aggregate_designer_screen import AggregateDesignerScreen
from Application.Create_Execution_Screen.create_execution_screen import CreateExecutionScreen
from Application.Open_Execution_Screen.open_execution_screen import OpenExecutionScreen

# Ensure the project root is in the system path for module imports
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class UIValidatorApp(App):

    def build(self):
        self.title = "UI-Validator"
        self.icon = os.path.join(PROJECT_ROOT, 'Application', '_Icons', 'Icon.png')

        Window.clearcolor = (0.05, 0.05, 0.10, 1)

        sm = ScreenManager(transition=FadeTransition(duration=0.3))
        sm.add_widget(LoadingScreen(name=LoadingScreen.SCREEN_NAME))
        sm.add_widget(MenuScreen(name=MenuScreen.SCREEN_NAME))
        sm.add_widget(SettingsScreen(name=SettingsScreen.SCREEN_NAME))
        sm.add_widget(CreateDesignerScreen(name=CreateDesignerScreen.SCREEN_NAME))
        sm.add_widget(OpenDesignerScreen(name=OpenDesignerScreen.SCREEN_NAME))
        sm.add_widget(AggregateDesignerScreen(name=AggregateDesignerScreen.SCREEN_NAME))
        sm.add_widget(CreateExecutionScreen(name=CreateExecutionScreen.SCREEN_NAME))
        sm.add_widget(OpenExecutionScreen(name=OpenExecutionScreen.SCREEN_NAME))

        sm.current = "loading"
        return sm


if __name__ == "__main__":
    UIValidatorApp().run()
