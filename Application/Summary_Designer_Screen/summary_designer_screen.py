"""Summary Designer Screen - Review and edit recorded steps"""

import os
import sys
import json
from pathlib import Path
from pynput import keyboard

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.metrics import dp
from kivy.uix.image import Image
from kivy.graphics import Color, Line, Ellipse, Quad, RoundedRectangle
from kivy.graphics.texture import Texture
from kivy.clock import Clock
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.image import Image as KivyImage
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
import numpy as np
import cv2

from Databases.designer_database import DesignerDatabase
from Models.model_registry import get_model
from Designer.Designer_Logic.ocr_generator import OCRGenerator
from Designer.Designer_Logic.efficientnet_generator import EfficientNetGenerator
from Designer.Designer_Logic.layoutlm_generator import LayoutLMGenerator
from Designer.Designer_Logic.sam_generator import SAMGenerator
from Designer.Designer_Logic.clip_generator import CLIPGenerator


Builder.load_file(os.path.join(os.path.dirname(__file__), "summary_designer_screen.kv"))


class BBoxImageEditor(Image):
    """BBox viewer with click point overlay and drag/resize support"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fit_mode = "contain"
        self._original_img = None
        self._bbox = None
        self._click_point = None
        self._bbox_drag = None
        self._click_drag = None
        self._on_bbox_changed = None
        self._on_bbox_drag_changed = None

        self._drag_mode = None
        self._last_touch_pos = None

        self.bind(size=lambda *_: self.draw_overlays(), pos=lambda *_: self.draw_overlays())

    def set_screenshot_bytes(self, screenshot_bytes):
        if screenshot_bytes is None:
            self._original_img = None
            self.texture = None
            return

        try:
            nparr = np.frombuffer(screenshot_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is not None:
                self._original_img = frame
                self.texture = self._frame_to_texture(frame)
                self.draw_overlays()
        except Exception as e:
            print(f"Error loading screenshot: {e}")

    def set_bbox(self, bbox):
        self._bbox = bbox
        Clock.schedule_once(lambda _: self.draw_overlays(), 0.1)

    def set_click_point(self, click_point):
        self._click_point = click_point
        self.draw_overlays()

    def set_bbox_drag(self, bbox_drag):
        self._bbox_drag = bbox_drag
        self.draw_overlays()

    def set_click_drag(self, click_drag):
        self._click_drag = click_drag
        self.draw_overlays()

    def _frame_to_texture(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb = cv2.flip(rgb, 0)
        h, w = rgb.shape[:2]
        tex = Texture.create(size=(w, h), colorfmt="rgb")
        tex.blit_buffer(rgb.tobytes(), colorfmt="rgb", bufferfmt="ubyte")
        return tex

    def draw_overlays(self):
        self.canvas.after.clear()

        if self._bbox is None or self._original_img is None:
            return

        with self.canvas.after:
            self._draw_bbox(self._bbox, self._click_point, (0.4, 0.6, 1.0, 1), (0.7, 0.0, 1.0, 1))

            if self._bbox_drag:
                self._draw_bbox(self._bbox_drag, self._click_drag, (0.2, 0.8, 0.5, 1), (1.0, 0.0, 0.0, 1))

    def _draw_bbox(self, bbox, click_point, bbox_color, click_color):
        if bbox is None:
            return

        x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
        p_tl = self._to_widget_coords(x, y)
        p_tr = self._to_widget_coords(x + w, y)
        p_bl = self._to_widget_coords(x, y + h)
        p_br = self._to_widget_coords(x + w, y + h)

        if p_tl[0] is None:
            return

        Color(*bbox_color[:3], 0.2)
        Quad(points=[p_tl[0], p_tl[1], p_tr[0], p_tr[1], p_br[0], p_br[1], p_bl[0], p_bl[1]])

        Color(*bbox_color)
        Line(points=[p_tl[0], p_tl[1], p_tr[0], p_tr[1], p_br[0], p_br[1], p_bl[0], p_bl[1], p_tl[0], p_tl[1]], width=2)

        handle_size = dp(2)
        Color(1, 1, 1, 1)
        handle_positions = [
            p_tl, p_tr, p_bl, p_br,
            ((p_tl[0] + p_tr[0]) / 2, (p_tl[1] + p_tr[1]) / 2),
            ((p_bl[0] + p_br[0]) / 2, (p_bl[1] + p_br[1]) / 2),
            ((p_tl[0] + p_bl[0]) / 2, (p_tl[1] + p_bl[1]) / 2),
            ((p_tr[0] + p_br[0]) / 2, (p_tr[1] + p_br[1]) / 2),
        ]

        for pos in handle_positions:
            if pos[0] is not None:
                Ellipse(pos=(pos[0] - handle_size, pos[1] - handle_size),
                       size=(handle_size * 2, handle_size * 2))

        if click_point:
            cp_abs_x = click_point['x']
            cp_abs_y = click_point['y']
            cp_widget = self._to_widget_coords(cp_abs_x, cp_abs_y)

            if cp_widget[0] is not None:
                Color(*click_color)
                inner_size = dp(6)
                Line(circle=(cp_widget[0], cp_widget[1], inner_size), width=0.5)

                Color(*click_color)
                cross_size = dp(12)
                Line(points=[cp_widget[0] - cross_size, cp_widget[1],
                            cp_widget[0] + cross_size, cp_widget[1]], width=1)
                Line(points=[cp_widget[0], cp_widget[1] - cross_size,
                            cp_widget[0], cp_widget[1] + cross_size], width=1)

    def _get_img_rect(self):
        if self._original_img is None or self.texture is None:
            return None, None, None, None, None, None

        img_h, img_w = self._original_img.shape[:2]
        widget_w, widget_h = self.width, self.height

        if widget_w <= 0 or widget_h <= 0:
            return None, None, None, None, None, None

        img_ratio = img_w / img_h
        widget_ratio = widget_w / widget_h

        if img_ratio > widget_ratio:
            disp_w = widget_w
            disp_h = widget_w / img_ratio
        else:
            disp_h = widget_h
            disp_w = widget_h * img_ratio

        offset_x = self.x + (widget_w - disp_w) / 2
        offset_y = self.y + (widget_h - disp_h) / 2
        scale = disp_w / img_w

        return offset_x, offset_y, disp_w, disp_h, scale, (img_w, img_h)

    def _to_widget_coords(self, img_x, img_y):
        result = self._get_img_rect()
        if result[0] is None:
            return None, None

        offset_x, offset_y, _, _, scale, (img_w, img_h) = result
        wx = offset_x + img_x * scale
        wy = offset_y + (img_h - img_y) * scale
        return wx, wy

    def _to_image_coords(self, wx, wy):
        result = self._get_img_rect()
        if result[0] is None:
            return None, None

        offset_x, offset_y, _, _, scale, (img_w, img_h) = result
        img_x = (wx - offset_x) / scale
        img_y = (img_h - (wy - offset_y) / scale)
        return img_x, img_y

    def _clamp_bbox(self, bbox):
        if self._original_img is None:
            return bbox

        img_h, img_w = self._original_img.shape[:2]

        bbox['x'] = max(0, min(bbox['x'], img_w - bbox['w']))
        bbox['y'] = max(0, min(bbox['y'], img_h - bbox['h']))
        bbox['w'] = min(bbox['w'], img_w - bbox['x'])
        bbox['h'] = min(bbox['h'], img_h - bbox['y'])

        return bbox

    def _clamp_click_point(self, click_point, bbox):
        if click_point is None or bbox is None:
            return click_point

        click_point['x'] = max(bbox['x'], min(click_point['x'], bbox['x'] + bbox['w']))
        click_point['y'] = max(bbox['y'], min(click_point['y'], bbox['y'] + bbox['h']))

        return click_point

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False

        if not self._bbox:
            return False

        img_x, img_y = self._to_image_coords(touch.x, touch.y)
        if img_x is None:
            return False

        bbox = self._bbox
        click_point_threshold = 15
        corner_threshold = 30

        if self._click_point:
            cp_x = self._click_point['x']
            cp_y = self._click_point['y']
            if abs(img_x - cp_x) < click_point_threshold and abs(img_y - cp_y) < click_point_threshold:
                self._drag_mode = "move_click"
                self._last_touch_pos = (img_x, img_y)
                return True

        edge_threshold = 20

        near_left = abs(img_x - bbox['x']) < edge_threshold
        near_right = abs(img_x - (bbox['x'] + bbox['w'])) < edge_threshold
        near_top = abs(img_y - bbox['y']) < edge_threshold
        near_bottom = abs(img_y - (bbox['y'] + bbox['h'])) < edge_threshold

        if near_left and near_top:
            self._drag_mode = "resize_tl"
            self._last_touch_pos = (img_x, img_y)
            return True
        if near_right and near_top:
            self._drag_mode = "resize_tr"
            self._last_touch_pos = (img_x, img_y)
            return True
        if near_left and near_bottom:
            self._drag_mode = "resize_bl"
            self._last_touch_pos = (img_x, img_y)
            return True
        if near_right and near_bottom:
            self._drag_mode = "resize_br"
            self._last_touch_pos = (img_x, img_y)
            return True

        if near_left and not (near_top or near_bottom):
            self._drag_mode = "resize_left"
            self._last_touch_pos = (img_x, img_y)
            return True
        if near_right and not (near_top or near_bottom):
            self._drag_mode = "resize_right"
            self._last_touch_pos = (img_x, img_y)
            return True
        if near_top and not (near_left or near_right):
            self._drag_mode = "resize_top"
            self._last_touch_pos = (img_x, img_y)
            return True
        if near_bottom and not (near_left or near_right):
            self._drag_mode = "resize_bottom"
            self._last_touch_pos = (img_x, img_y)
            return True

        inside = bbox['x'] <= img_x <= bbox['x'] + bbox['w'] and bbox['y'] <= img_y <= bbox['y'] + bbox['h']
        if inside and not (near_left or near_right or near_top or near_bottom):
            self._drag_mode = "move_bbox"
            self._last_touch_pos = (img_x, img_y)
            return True

        if self._bbox_drag:
            bbox_drag = self._bbox_drag

            if self._click_drag:
                cd_x = self._click_drag['x']
                cd_y = self._click_drag['y']
                if abs(img_x - cd_x) < click_point_threshold and abs(img_y - cd_y) < click_point_threshold:
                    self._drag_mode = "move_drag_click"
                    self._last_touch_pos = (img_x, img_y)
                    return True

            near_left_d = abs(img_x - bbox_drag['x']) < edge_threshold
            near_right_d = abs(img_x - (bbox_drag['x'] + bbox_drag['w'])) < edge_threshold
            near_top_d = abs(img_y - bbox_drag['y']) < edge_threshold
            near_bottom_d = abs(img_y - (bbox_drag['y'] + bbox_drag['h'])) < edge_threshold

            if near_left_d and near_top_d:
                self._drag_mode = "resize_drag_tl"
                self._last_touch_pos = (img_x, img_y)
                return True
            if near_right_d and near_top_d:
                self._drag_mode = "resize_drag_tr"
                self._last_touch_pos = (img_x, img_y)
                return True
            if near_left_d and near_bottom_d:
                self._drag_mode = "resize_drag_bl"
                self._last_touch_pos = (img_x, img_y)
                return True
            if near_right_d and near_bottom_d:
                self._drag_mode = "resize_drag_br"
                self._last_touch_pos = (img_x, img_y)
                return True

            if near_left_d and not (near_top_d or near_bottom_d):
                self._drag_mode = "resize_drag_left"
                self._last_touch_pos = (img_x, img_y)
                return True
            if near_right_d and not (near_top_d or near_bottom_d):
                self._drag_mode = "resize_drag_right"
                self._last_touch_pos = (img_x, img_y)
                return True
            if near_top_d and not (near_left_d or near_right_d):
                self._drag_mode = "resize_drag_top"
                self._last_touch_pos = (img_x, img_y)
                return True
            if near_bottom_d and not (near_left_d or near_right_d):
                self._drag_mode = "resize_drag_bottom"
                self._last_touch_pos = (img_x, img_y)
                return True

            inside_drag = bbox_drag['x'] <= img_x <= bbox_drag['x'] + bbox_drag['w'] and bbox_drag['y'] <= img_y <= bbox_drag['y'] + bbox_drag['h']
            if inside_drag and not (near_left_d or near_right_d or near_top_d or near_bottom_d):
                self._drag_mode = "move_drag_bbox"
                self._last_touch_pos = (img_x, img_y)
                return True

        return False

    def on_touch_move(self, touch):
        if not self._drag_mode or not self._last_touch_pos:
            return False

        img_x, img_y = self._to_image_coords(touch.x, touch.y)
        if img_x is None:
            return False

        delta_x = img_x - self._last_touch_pos[0]
        delta_y = img_y - self._last_touch_pos[1]

        if self._drag_mode == "move_bbox":
            self._bbox['x'] = int(round(self._bbox['x'] + delta_x))
            self._bbox['y'] = int(round(self._bbox['y'] + delta_y))
            if self._click_point:
                self._click_point['x'] = int(round(self._click_point['x'] + delta_x))
                self._click_point['y'] = int(round(self._click_point['y'] + delta_y))
            self._clamp_bbox(self._bbox)
            self._clamp_click_point(self._click_point, self._bbox)
            self._last_touch_pos = (img_x, img_y)
            self.draw_overlays()
            return True

        elif self._drag_mode == "move_click":
            new_x = int(round(self._click_point['x'] + delta_x))
            new_y = int(round(self._click_point['y'] + delta_y))

            bbox = self._bbox
            new_x = max(bbox['x'], min(new_x, bbox['x'] + bbox['w']))
            new_y = max(bbox['y'], min(new_y, bbox['y'] + bbox['h']))

            self._click_point['x'] = new_x
            self._click_point['y'] = new_y
            self._last_touch_pos = (img_x, img_y)
            self.draw_overlays()
            return True

        elif self._drag_mode == "resize_tl":
            self._bbox['x'] = int(round(self._bbox['x'] + delta_x))
            self._bbox['y'] = int(round(self._bbox['y'] + delta_y))
            self._bbox['w'] = int(round(self._bbox['w'] - delta_x))
            self._bbox['h'] = int(round(self._bbox['h'] - delta_y))
            self._clamp_bbox(self._bbox)
            self._clamp_click_point(self._click_point, self._bbox)
            self._last_touch_pos = (img_x, img_y)
            self.draw_overlays()
            return True

        elif self._drag_mode == "resize_tr":
            self._bbox['y'] = int(round(self._bbox['y'] + delta_y))
            self._bbox['w'] = int(round(self._bbox['w'] + delta_x))
            self._bbox['h'] = int(round(self._bbox['h'] - delta_y))
            self._clamp_bbox(self._bbox)
            self._clamp_click_point(self._click_point, self._bbox)
            self._last_touch_pos = (img_x, img_y)
            self.draw_overlays()
            return True

        elif self._drag_mode == "resize_bl":
            self._bbox['x'] = int(round(self._bbox['x'] + delta_x))
            self._bbox['w'] = int(round(self._bbox['w'] - delta_x))
            self._bbox['h'] = int(round(self._bbox['h'] + delta_y))
            self._clamp_bbox(self._bbox)
            self._clamp_click_point(self._click_point, self._bbox)
            self._last_touch_pos = (img_x, img_y)
            self.draw_overlays()
            return True

        elif self._drag_mode == "resize_br":
            self._bbox['w'] = int(round(self._bbox['w'] + delta_x))
            self._bbox['h'] = int(round(self._bbox['h'] + delta_y))
            self._clamp_bbox(self._bbox)
            self._clamp_click_point(self._click_point, self._bbox)
            self._last_touch_pos = (img_x, img_y)
            self.draw_overlays()
            return True

        elif self._drag_mode == "resize_left":
            self._bbox['x'] = int(round(self._bbox['x'] + delta_x))
            self._bbox['w'] = int(round(self._bbox['w'] - delta_x))
            self._clamp_bbox(self._bbox)
            self._clamp_click_point(self._click_point, self._bbox)
            self._last_touch_pos = (img_x, img_y)
            self.draw_overlays()
            return True

        elif self._drag_mode == "resize_right":
            self._bbox['w'] = int(round(self._bbox['w'] + delta_x))
            self._clamp_bbox(self._bbox)
            self._clamp_click_point(self._click_point, self._bbox)
            self._last_touch_pos = (img_x, img_y)
            self.draw_overlays()
            return True

        elif self._drag_mode == "resize_top":
            self._bbox['y'] = int(round(self._bbox['y'] + delta_y))
            self._bbox['h'] = int(round(self._bbox['h'] - delta_y))
            self._clamp_bbox(self._bbox)
            self._clamp_click_point(self._click_point, self._bbox)
            self._last_touch_pos = (img_x, img_y)
            self.draw_overlays()
            return True

        elif self._drag_mode == "resize_bottom":
            self._bbox['h'] = int(round(self._bbox['h'] + delta_y))
            self._clamp_bbox(self._bbox)
            self._clamp_click_point(self._click_point, self._bbox)
            self._last_touch_pos = (img_x, img_y)
            self.draw_overlays()
            return True

        elif self._drag_mode == "move_drag_bbox":
            self._bbox_drag['x'] = int(round(self._bbox_drag['x'] + delta_x))
            self._bbox_drag['y'] = int(round(self._bbox_drag['y'] + delta_y))
            if self._click_drag:
                self._click_drag['x'] = int(round(self._click_drag['x'] + delta_x))
                self._click_drag['y'] = int(round(self._click_drag['y'] + delta_y))
            self._clamp_bbox(self._bbox_drag)
            self._clamp_click_point(self._click_drag, self._bbox_drag)
            self._last_touch_pos = (img_x, img_y)
            self.draw_overlays()
            return True

        elif self._drag_mode == "move_drag_click":
            new_x = int(round(self._click_drag['x'] + delta_x))
            new_y = int(round(self._click_drag['y'] + delta_y))

            bbox_drag = self._bbox_drag
            new_x = max(bbox_drag['x'], min(new_x, bbox_drag['x'] + bbox_drag['w']))
            new_y = max(bbox_drag['y'], min(new_y, bbox_drag['y'] + bbox_drag['h']))

            self._click_drag['x'] = new_x
            self._click_drag['y'] = new_y
            self._last_touch_pos = (img_x, img_y)
            self.draw_overlays()
            return True

        elif self._drag_mode in ["resize_drag_tl", "resize_drag_tr", "resize_drag_bl", "resize_drag_br", "resize_drag_left", "resize_drag_right", "resize_drag_top", "resize_drag_bottom"]:
            mode = self._drag_mode.replace("resize_drag_", "resize_")
            if mode == "resize_tl":
                self._bbox_drag['x'] = int(round(self._bbox_drag['x'] + delta_x))
                self._bbox_drag['y'] = int(round(self._bbox_drag['y'] + delta_y))
                self._bbox_drag['w'] = int(round(self._bbox_drag['w'] - delta_x))
                self._bbox_drag['h'] = int(round(self._bbox_drag['h'] - delta_y))
            elif mode == "resize_tr":
                self._bbox_drag['y'] = int(round(self._bbox_drag['y'] + delta_y))
                self._bbox_drag['w'] = int(round(self._bbox_drag['w'] + delta_x))
                self._bbox_drag['h'] = int(round(self._bbox_drag['h'] - delta_y))
            elif mode == "resize_bl":
                self._bbox_drag['x'] = int(round(self._bbox_drag['x'] + delta_x))
                self._bbox_drag['w'] = int(round(self._bbox_drag['w'] - delta_x))
                self._bbox_drag['h'] = int(round(self._bbox_drag['h'] + delta_y))
            elif mode == "resize_br":
                self._bbox_drag['w'] = int(round(self._bbox_drag['w'] + delta_x))
                self._bbox_drag['h'] = int(round(self._bbox_drag['h'] + delta_y))
            elif mode == "resize_left":
                self._bbox_drag['x'] = int(round(self._bbox_drag['x'] + delta_x))
                self._bbox_drag['w'] = int(round(self._bbox_drag['w'] - delta_x))
            elif mode == "resize_right":
                self._bbox_drag['w'] = int(round(self._bbox_drag['w'] + delta_x))
            elif mode == "resize_top":
                self._bbox_drag['y'] = int(round(self._bbox_drag['y'] + delta_y))
                self._bbox_drag['h'] = int(round(self._bbox_drag['h'] - delta_y))
            elif mode == "resize_bottom":
                self._bbox_drag['h'] = int(round(self._bbox_drag['h'] + delta_y))

            self._clamp_bbox(self._bbox_drag)
            self._clamp_click_point(self._click_drag, self._bbox_drag)
            self._last_touch_pos = (img_x, img_y)
            self.draw_overlays()
            return True

        return False

    def on_touch_up(self, touch):
        if not self._drag_mode:
            return False

        if self._drag_mode in ["move_bbox", "resize_tl", "resize_tr", "resize_bl", "resize_br", "resize_left", "resize_right", "resize_top", "resize_bottom", "move_click"]:
            if self._on_bbox_changed:
                self._on_bbox_changed(self._bbox, self._click_point)

        elif self._drag_mode in ["move_drag_bbox", "resize_drag_tl", "resize_drag_tr", "resize_drag_bl", "resize_drag_br", "resize_drag_left", "resize_drag_right", "resize_drag_top", "resize_drag_bottom", "move_drag_click"]:
            if self._on_bbox_drag_changed:
                self._on_bbox_drag_changed(self._bbox_drag, self._click_drag)

        self._drag_mode = None
        self._last_touch_pos = None
        return True


class _StepRow(BoxLayout):
    def __init__(self, step_num, action_type, on_select, step_tc=None, on_tc_changed=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(32)
        self.spacing = dp(6)
        self.padding = [dp(6), dp(2), dp(6), dp(2)]
        self._on_select = on_select
        self._on_tc_changed = on_tc_changed
        self._step_num = step_num
        self._selected = False

        from kivy.graphics import Color, RoundedRectangle, Line
        with self.canvas.before:
            self._bg_color = Color(0, 0, 0, 1)
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(6)])

        with self.canvas.after:
            self._border_color = Color(0.35, 0.53, 1.0, 0.85)
            self._border_line = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(6)), width=1.5)

        self.bind(pos=self._sync_bg, size=self._sync_bg)

        num_label = Label(
            text=f"#{step_num}",
            font_size="14sp",
            bold=True,
            color=(0.4, 0.6, 1.0, 1),
            size_hint_x=None,
            width=dp(40),
        )
        self.add_widget(num_label)

        action_label = Label(
            text=action_type,
            font_size="12sp",
            color=(0.85, 0.85, 0.85, 1),
        )
        self.add_widget(action_label)

        tc_label = Label(
            text="TC:",
            font_size="11sp",
            color=(0.85, 0.85, 0.85, 1),
            size_hint_x=None,
            width=dp(25),
            halign="right",
        )
        self.add_widget(tc_label)

        tc_input = TextInput(
            text=str(step_tc) if step_tc else "",
            font_size="12sp",
            multiline=False,
            input_filter="int",
            size_hint_x=None,
            width=dp(35),
            padding=[dp(4), dp(6)],
            background_color=(0, 0, 0, 1),
            foreground_color=(1, 1, 1, 1),
            halign="center",
        )
        tc_input.bind(text=self._on_tc_input_changed)
        self.add_widget(tc_input)
        self._tc_input = tc_input

    def _sync_bg(self, *_):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._border_line.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(6))

    def set_selected(self, selected):
        self._selected = selected
        if selected:
            self._bg_color.rgba = (0.25, 0.40, 0.65, 1)
        else:
            self._bg_color.rgba = (0, 0, 0, 1)

    def _on_tc_input_changed(self, widget, value):
        if self._on_tc_changed:
            try:
                tc_val = int(value) if value else None
                self._on_tc_changed(self._step_num, tc_val)
            except ValueError:
                pass

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self._tc_input.collide_point(*touch.pos):
                return self._tc_input.on_touch_down(touch)
            self._on_select(self._step_num)
            return True
        return super().on_touch_down(touch)


class SummaryDesignerScreen(Screen):
    SCREEN_NAME = "summary_designer"
    recording_name = StringProperty("")
    steps_count = StringProperty("0")
    session_resolution = StringProperty("")
    session_zoom = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._db = None
        self._steps = []
        self._selected_step = None
        self._selected_row = None
        self._step_clean_values = {}
        self._bbox_modifications = {}
        self._updating_ui = False
        self._keyboard_listener = None

    def on_enter(self):
        self.ids.save_step_button.bind(disabled=self._update_save_button_style)
        self.ids.press_enter_checkbox.bind(active=self._on_press_enter_changed)

        if not self._keyboard_listener:
            self._keyboard_listener = keyboard.Listener(on_press=self._on_key_press_summary)
            self._keyboard_listener.start()

    def on_leave(self):
        if self._keyboard_listener:
            self._keyboard_listener.stop()
            self._keyboard_listener = None

    def _on_key_press_summary(self, key):
        try:
            if key == keyboard.Key.f9:
                Clock.schedule_once(lambda _: self._capture_all_monitors_and_choose(), 0)
        except Exception as e:
            print(f"Error in keyboard listener: {e}")

    def _capture_all_monitors_and_choose(self):
        try:
            from mss import mss

            print("[F9] Capturing screenshots from all monitors...")

            screenshots = {}
            with mss() as sct:
                for i, monitor in enumerate(sct.monitors[1:]):
                    print(f"  Capturing Monitor {i}: {monitor['width']}×{monitor['height']}")
                    screenshot = sct.grab(monitor)
                    h, w = screenshot.height, screenshot.width
                    img_rgb = np.frombuffer(screenshot.rgb, dtype=np.uint8).reshape((h, w, 3))
                    screenshots[i] = {
                        'image': img_rgb,
                        'monitor': monitor,
                        'label': f"Monitor {i}  ({monitor['width']}×{monitor['height']})"
                    }

            if not screenshots:
                print("[F9] No monitors found")
                return

            self._show_monitor_selection_popup(screenshots)

        except Exception as e:
            print(f"[F9] Error capturing monitors: {e}")
            import traceback
            traceback.print_exc()

    def _show_monitor_selection_popup(self, screenshots):
        try:
            popup_content = GridLayout(cols=1, spacing=dp(10), size_hint_y=None)
            popup_content.bind(minimum_height=popup_content.setter('height'))

            for monitor_idx, data in screenshots.items():
                btn_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(100), spacing=dp(10))

                img_array = data['image']
                scale = 80 / max(img_array.shape[0], img_array.shape[1])
                thumb_h = int(img_array.shape[0] * scale)
                thumb_w = int(img_array.shape[1] * scale)
                thumb = cv2.resize(img_array, (thumb_w, thumb_h))

                h, w = thumb.shape[:2]
                tex = Texture.create(size=(w, h), colorfmt='rgb')
                tex.blit_buffer(thumb.tobytes(), colorfmt='rgb', bufferfmt='ubyte')

                img_widget = KivyImage(texture=tex, size_hint_x=None, width=thumb_w)
                btn_layout.add_widget(img_widget)

                label = Label(text=data['label'], size_hint_x=None, width=dp(200))
                btn_layout.add_widget(label)

                select_btn = Button(text="Select", size_hint_x=None, width=dp(100))
                select_btn.bind(on_release=lambda btn, idx=monitor_idx, data=data: self._use_monitor_screenshot(idx, data))
                btn_layout.add_widget(select_btn)

                popup_content.add_widget(btn_layout)

            scroll = ScrollView(size_hint=(1, 1))
            scroll.add_widget(popup_content)

            popup = Popup(
                title="Choose Monitor Screenshot (F9)",
                content=scroll,
                size_hint=(0.9, 0.9)
            )
            popup.open()

        except Exception as e:
            print(f"Error showing monitor popup: {e}")
            import traceback
            traceback.print_exc()

    def _use_monitor_screenshot(self, monitor_idx, data):
        try:
            print(f"[F9] Using Monitor {monitor_idx} screenshot")

            img_array = data['image']
            img_bgr = img_array[:, :, ::-1]
            _, png_bytes = cv2.imencode('.png', img_bgr)

            if self._selected_step:
                self._selected_step.Screenshot = png_bytes.tobytes()
                self._load_step(self._selected_step)
                print(f"[F9] Screenshot updated for step {self._selected_step.Step_number}")

        except Exception as e:
            print(f"[F9] Error using screenshot: {e}")
            import traceback
            traceback.print_exc()

    def load_session(self, db_path, session_name):
        try:
            self._db = DesignerDatabase(db_path)
            self._steps = self._db.get_steps()
            self.recording_name = session_name
            self.steps_count = str(len(self._steps))

            try:
                session = self._db.get_session()
                if session:
                    resolution = session.Screen_resolution or "unknown"
                    zoom = session.Screen_zoom or "1.0"
                    self.session_resolution = str(resolution)
                    self.session_zoom = str(zoom)
            except:
                self.session_resolution = "unknown"
                self.session_zoom = "1.0"

            self._load_steps_list()

            if self._steps:
                self._load_step_by_number(self._steps[0].Step_number)

        except Exception as e:
            print(f"Error loading session: {e}")
            import traceback
            traceback.print_exc()

    def _load_steps_list(self):
        self.ids.steps_grid.clear_widgets()
        self._step_rows = {}

        for step in self._steps:
            row = _StepRow(
                step_num=step.Step_number,
                action_type=step.Action_type,
                step_tc=step.Step_testcase,
                on_select=lambda step_num: self._load_step_by_number(step_num),
                on_tc_changed=self._on_step_tc_changed
            )
            self._step_rows[step.Step_number] = row
            self.ids.steps_grid.add_widget(row)

    def _load_step_by_number(self, step_num):
        for step in self._steps:
            if step.Step_number == step_num:
                if self._selected_step and self._selected_step.Action_type == "INPUT":
                    try:
                        input_val = self.ids.input_text_input.text.strip()
                        self._selected_step.Input_text = input_val if input_val else None
                        self._db.update_step(self._selected_step)
                        print(f"Input Text auto-saved before switching step: {self._selected_step.Input_text}")
                    except Exception as e:
                        print(f"Error saving Input Text: {e}")

                if self._selected_row:
                    self._selected_row.set_selected(False)

                new_row = self._step_rows.get(step_num)
                if new_row:
                    new_row.set_selected(True)
                    self._selected_row = new_row

                self._load_step(step)
                break

    def _load_step(self, step):
        try:
            self._selected_step = step
            print(f"Loading step #{step.Step_number}: {step.Action_type}")

            if self._bbox_modifications:
                self.ids.save_step_button.disabled = False
            else:
                self.ids.save_step_button.disabled = True

            self.ids.screenshot_image._on_bbox_changed = self._on_bbox_changed
            self.ids.screenshot_image._on_bbox_drag_changed = self._on_bbox_drag_changed

            self.ids.screenshot_image.set_screenshot_bytes(None)
            self.ids.screenshot_image.set_bbox(None)
            self.ids.screenshot_image.set_click_point(None)
            self.ids.screenshot_image.set_bbox_drag(None)
            self.ids.screenshot_image.set_click_drag(None)

            if step.Screenshot:
                self.ids.screenshot_image.set_screenshot_bytes(step.Screenshot)

            if step.BBox:
                try:
                    bbox = json.loads(step.BBox)
                    self.ids.screenshot_image.set_bbox(bbox)

                    if step.BBox_rel_coordinates and step.Action_type != "INPUT":
                        click_rel = json.loads(step.BBox_rel_coordinates)
                        click_abs = {
                            "x": bbox.get('x', 0) + click_rel.get('x', 0),
                            "y": bbox.get('y', 0) + click_rel.get('y', 0)
                        }
                        self.ids.screenshot_image.set_click_point(click_abs)
                except json.JSONDecodeError:
                    print(f"ERROR parsing BBox JSON")

            if step.Action_type == "DRAG_AND_DROP":
                if hasattr(step, 'BBox_drag') and step.BBox_drag:
                    bbox_drag = json.loads(step.BBox_drag)
                    self.ids.screenshot_image.set_bbox_drag(bbox_drag)

                    if hasattr(step, 'BBox_drag_rel_coordinates') and step.BBox_drag_rel_coordinates:
                        click_drag_rel = json.loads(step.BBox_drag_rel_coordinates)
                        click_drag_abs = {
                            "x": bbox_drag.get('x', 0) + click_drag_rel.get('x', 0),
                            "y": bbox_drag.get('y', 0) + click_drag_rel.get('y', 0)
                        }
                        self.ids.screenshot_image.set_click_drag(click_drag_abs)

            self._populate_edit_panel(step)

        except Exception as e:
            print(f"Error loading step: {e}")
            import traceback
            traceback.print_exc()

    def _populate_edit_panel(self, step):
        self._updating_ui = True
        try:
            self._step_clean_values = {
                'tc': str(step.Step_testcase) if step.Step_testcase else "",
                'input_text': step.Input_text if step.Input_text else "",
                'scroll_dx': str(step.Scroll_DX) if step.Scroll_DX is not None else "",
                'scroll_dy': str(step.Scroll_DY) if step.Scroll_DY is not None else "",
            }

            self.ids.input_text_input.unbind(on_focus=self._on_input_text_focus)
            self.ids.input_text_input.bind(on_focus=self._on_input_text_focus)

            is_input = step.Action_type == "INPUT"

            self.ids.input_label.opacity = 1 if is_input else 0
            self.ids.input_label.disabled = not is_input
            self.ids.input_text_input.opacity = 1 if is_input else 0
            self.ids.input_text_input.disabled = not is_input

            if is_input:
                input_val = step.Input_text if step.Input_text else ""
                self.ids.input_text_input.text = str(input_val)
            else:
                self.ids.input_text_input.text = ""

            is_scroll = step.Action_type == "SCROLL"

            self.ids.scroll_dx_label.opacity = 1 if is_scroll else 0
            self.ids.scroll_dx_label.disabled = not is_scroll
            self.ids.scroll_dx_input.opacity = 1 if is_scroll else 0
            self.ids.scroll_dx_input.disabled = not is_scroll

            self.ids.scroll_dy_label.opacity = 1 if is_scroll else 0
            self.ids.scroll_dy_label.disabled = not is_scroll
            self.ids.scroll_dy_input.opacity = 1 if is_scroll else 0
            self.ids.scroll_dy_input.disabled = not is_scroll

            if is_scroll:
                scroll_dx_val = str(step.Scroll_DX) if step.Scroll_DX is not None else ""
                scroll_dy_val = str(step.Scroll_DY) if step.Scroll_DY is not None else ""
                self.ids.scroll_dx_input.text = scroll_dx_val
                self.ids.scroll_dy_input.text = scroll_dy_val
            else:
                self.ids.scroll_dx_input.text = ""
                self.ids.scroll_dy_input.text = ""

            self.ids.press_enter_label.opacity = 1 if is_input else 0
            self.ids.press_enter_label.disabled = not is_input
            self.ids.press_enter_checkbox.opacity = 1 if is_input else 0
            self.ids.press_enter_checkbox.disabled = not is_input

            if is_input:
                self.ids.press_enter_checkbox.active = bool(step.Enter_After_Input_text)
            else:
                self.ids.press_enter_checkbox.active = False

            self.ids.info_grid.clear_widgets()

            tc_val = str(step.Step_testcase) if step.Step_testcase else "null"
            self.ids.info_grid.add_widget(Label(
                text=f"[b]Test Case Step[/b]: {tc_val}",
                markup=True, font_size="13sp", color=(0.85, 0.85, 0.85, 1),
                size_hint_y=None, height=dp(30)
            ))

            if step.Action_type == "INPUT":
                input_val = step.Input_text[:40] if step.Input_text else "null"
                self.ids.info_grid.add_widget(Label(
                    text=f"[b]Input Text[/b]: {input_val}",
                    markup=True, font_size="13sp", color=(0.85, 0.85, 0.85, 1),
                    size_hint_y=None, height=dp(30)
                ))

            enter_val = "True" if step.Enter_After_Input_text else "False" if step.Action_type == "INPUT" else "null"
            self.ids.info_grid.add_widget(Label(
                text=f"[b]Press Enter at end[/b]: {enter_val}",
                markup=True, font_size="13sp", color=(0.85, 0.85, 0.85, 1),
                size_hint_y=None, height=dp(30)
            ))

            bbox_val = "null"
            if step.BBox:
                try:
                    bbox = json.loads(step.BBox)
                    bbox_val = f"x={bbox.get('x', 0)} y={bbox.get('y', 0)} w={bbox.get('w', 0)} h={bbox.get('h', 0)}"
                except:
                    pass
            self.ids.info_grid.add_widget(Label(
                text=f"[b]BBox Dimension[/b]: {bbox_val}",
                markup=True, font_size="13sp", color=(0.85, 0.85, 0.85, 1),
                size_hint_y=None, height=dp(30)
            ))

            click_val = "null"
            if step.BBox_rel_coordinates:
                try:
                    click_rel = json.loads(step.BBox_rel_coordinates)
                    click_val = f"x={click_rel.get('x', 0)} y={click_rel.get('y', 0)}"
                except:
                    pass
            self.ids.info_grid.add_widget(Label(
                text=f"[b]BBox Click[/b]: {click_val}",
                markup=True, font_size="13sp", color=(0.85, 0.85, 0.85, 1),
                size_hint_y=None, height=dp(30)
            ))

            ocr_val = step.BBox_OCR_text[:40] if step.BBox_OCR_text else "null"
            self.ids.info_grid.add_widget(Label(
                text=f"[b]BBox OCR[/b]: {ocr_val}",
                markup=True, font_size="13sp", color=(0.85, 0.85, 0.85, 1),
                size_hint_y=None, height=dp(30)
            ))

            efficientnet_val = f"{len(step.BBox_EfficientNet_Features)} bytes" if step.BBox_EfficientNet_Features else "null"
            self.ids.info_grid.add_widget(Label(
                text=f"[b]BBox EfficientNet[/b]: {efficientnet_val}",
                markup=True, font_size="13sp", color=(0.85, 0.85, 0.85, 1),
                size_hint_y=None, height=dp(30)
            ))

            layoutlm_type = step.BBox_LayoutLM_Type or "null"
            self.ids.info_grid.add_widget(Label(
                text=f"[b]BBox LayoutLM Type[/b]: {layoutlm_type}",
                markup=True, font_size="13sp", color=(0.85, 0.85, 0.85, 1),
                size_hint_y=None, height=dp(30)
            ))

            layoutlm_conf = step.BBox_LayoutLM_Confidence[:60] if step.BBox_LayoutLM_Confidence else "null"
            self.ids.info_grid.add_widget(Label(
                text=f"[b]BBox LayoutLM Conf[/b]: {layoutlm_conf}...",
                markup=True, font_size="13sp", color=(0.85, 0.85, 0.85, 1),
                size_hint_y=None, height=dp(30)
            ))

            clip_val = f"{len(step.BBox_CLIP_Features)} bytes" if step.BBox_CLIP_Features else "null"
            self.ids.info_grid.add_widget(Label(
                text=f"[b]BBox CLIP[/b]: {clip_val}",
                markup=True, font_size="13sp", color=(0.85, 0.85, 0.85, 1),
                size_hint_y=None, height=dp(30)
            ))

            sam_mask_val = "present" if step.BBox_SAM_Mask else "null"
            self.ids.info_grid.add_widget(Label(
                text=f"[b]BBox SAM Mask[/b]: {sam_mask_val}",
                markup=True, font_size="13sp", color=(0.85, 0.85, 0.85, 1),
                size_hint_y=None, height=dp(30)
            ))

            modifiers_val = "null"
            if step.Modifier_keys:
                try:
                    modifiers = json.loads(step.Modifier_keys)
                    if isinstance(modifiers, list):
                        modifiers_val = ", ".join(modifiers) if modifiers else "none"
                    elif isinstance(modifiers, dict):
                        active = [k for k, v in modifiers.items() if v]
                        modifiers_val = ", ".join(active) if active else "none"
                except:
                    pass
            self.ids.info_grid.add_widget(Label(
                text=f"[b]Modifier Keys[/b]: {modifiers_val}",
                markup=True, font_size="13sp", color=(0.85, 0.85, 0.85, 1),
                size_hint_y=None, height=dp(30)
            ))

            scroll_dx_val = str(step.Scroll_DX) if step.Scroll_DX is not None else "null"
            self.ids.info_grid.add_widget(Label(
                text=f"[b]Scroll DX[/b]: {scroll_dx_val}",
                markup=True, font_size="13sp", color=(0.85, 0.85, 0.85, 1),
                size_hint_y=None, height=dp(30)
            ))

            scroll_dy_val = str(step.Scroll_DY) if step.Scroll_DY is not None else "null"
            self.ids.info_grid.add_widget(Label(
                text=f"[b]Scroll DY[/b]: {scroll_dy_val}",
                markup=True, font_size="13sp", color=(0.85, 0.85, 0.85, 1),
                size_hint_y=None, height=dp(30)
            ))

        except Exception as e:
            print(f"Error populating edit panel: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._updating_ui = False

    def _update_save_button_style(self, widget, value):
        if value:
            self.ids.save_step_button.color = (0.5, 0.5, 0.5, 1)
            self.ids.save_step_button.canvas.before.clear()
            with self.ids.save_step_button.canvas.before:
                Color(0.3, 0.3, 0.3, 1)
                RoundedRectangle(pos=self.ids.save_step_button.pos,
                                size=self.ids.save_step_button.size,
                                radius=[dp(8)])
        else:
            self.ids.save_step_button.color = (1, 1, 1, 1)
            self.ids.save_step_button.canvas.before.clear()
            with self.ids.save_step_button.canvas.before:
                Color(0.4, 0.6, 1.0, 1)
                RoundedRectangle(pos=self.ids.save_step_button.pos,
                                size=self.ids.save_step_button.size,
                                radius=[dp(8)])

    def _on_bbox_changed(self, bbox, click_point):
        if not self._selected_step:
            return

        bbox_int = {
            'x': int(round(bbox['x'])),
            'y': int(round(bbox['y'])),
            'w': int(round(bbox['w'])),
            'h': int(round(bbox['h']))
        }

        self._selected_step.BBox = json.dumps(bbox_int)
        if click_point:
            click_rel = {
                "x": int(round(click_point['x'] - bbox_int['x'])),
                "y": int(round(click_point['y'] - bbox_int['y']))
            }
            self._selected_step.BBox_rel_coordinates = json.dumps(click_rel)

        step_num = self._selected_step.Step_number
        if step_num not in self._bbox_modifications:
            self._bbox_modifications[step_num] = {"bbox_modified": False, "bbox_drag_modified": False}
        self._bbox_modifications[step_num]["bbox_modified"] = True

        self.ids.save_step_button.disabled = False

        print(f"BBox modified for step #{step_num}")

    def _on_bbox_drag_changed(self, bbox_drag, click_drag):
        if not self._selected_step:
            return

        bbox_drag_int = {
            'x': int(round(bbox_drag['x'])),
            'y': int(round(bbox_drag['y'])),
            'w': int(round(bbox_drag['w'])),
            'h': int(round(bbox_drag['h']))
        }

        self._selected_step.BBox_drag = json.dumps(bbox_drag_int)
        if click_drag:
            click_drag_rel = {
                "x": int(round(click_drag['x'] - bbox_drag_int['x'])),
                "y": int(round(click_drag['y'] - bbox_drag_int['y']))
            }
            self._selected_step.BBox_drag_rel_coordinates = json.dumps(click_drag_rel)

        step_num = self._selected_step.Step_number
        if step_num not in self._bbox_modifications:
            self._bbox_modifications[step_num] = {"bbox_modified": False, "bbox_drag_modified": False}
        self._bbox_modifications[step_num]["bbox_drag_modified"] = True

        self.ids.save_step_button.disabled = False

        print(f"Destination BBox modified for step #{step_num}")

    def _on_input_text_focus(self, widget, focus):
        if not focus:
            self.autosave_input_text()

    def _on_press_enter_changed(self, checkbox, value):
        if not self._selected_step or not self._db or self._updating_ui:
            return

        self._updating_ui = True
        self.ids.press_enter_checkbox.unbind(active=self._on_press_enter_changed)

        try:
            to_save = 1 if value else 0
            self._selected_step.Enter_After_Input_text = to_save

            self._db.update_step(self._selected_step)

            self._steps = self._db.get_steps()
            for step in self._steps:
                if step.Step_number == self._selected_step.Step_number:
                    self._selected_step = step
                    break

            print(f"Enter_After_Input_text auto-saved: {self._selected_step.Enter_After_Input_text}")

            self._populate_edit_panel(self._selected_step)

        except Exception as e:
            print(f"Error auto-saving Enter_After_Input_text: {e}")
        finally:
            self.ids.press_enter_checkbox.bind(active=self._on_press_enter_changed)
            self._updating_ui = False

    def autosave_input_text(self):
        if not self._selected_step or not self._db:
            return

        if self._selected_step.Action_type != "INPUT":
            return

        try:
            input_val = self.ids.input_text_input.text
            self._selected_step.Input_text = input_val if input_val else None
            self._db.update_step(self._selected_step)

            self._steps = self._db.get_steps()
            for step in self._steps:
                if step.Step_number == self._selected_step.Step_number:
                    self._selected_step = step
                    break

            self._step_clean_values['input_text'] = self._selected_step.Input_text if self._selected_step.Input_text else ""
            self.ids.save_step_button.disabled = True

            self._populate_edit_panel(self._selected_step)

            print(f"Input Text auto-saved: {self._selected_step.Input_text}")

        except Exception as e:
            print(f"Error auto-saving Input Text: {e}")

    def _on_step_tc_changed(self, step_num, tc_val):
        if not self._db:
            return

        try:
            for step in self._steps:
                if step.Step_number == step_num:
                    step.Step_testcase = tc_val
                    self._db.update_step(step)
                    print(f"Step {step_num} TC auto-saved: {tc_val}")
                    break
        except Exception as e:
            print(f"Error auto-saving Step TC: {e}")

    def _recalculate_bbox_models(self, step, crop_image):
        if crop_image is None or crop_image.size == 0:
            return

        try:
            ocr_model = get_model('ocr')
            efficientnet_model = get_model('efficientnet')
            layoutlm_model = get_model('layoutlm')
            sam_model = get_model('sam')
            clip_model = get_model('clip')

            if not all([ocr_model, efficientnet_model, layoutlm_model, sam_model, clip_model]):
                print("Not all models loaded, skipping recalculation")
                return

            ocr_gen = OCRGenerator(ocr_model)
            efficientnet_gen = EfficientNetGenerator(efficientnet_model)
            layoutlm_gen = LayoutLMGenerator(layoutlm_model)
            sam_gen = SAMGenerator(sam_model)
            clip_gen = CLIPGenerator(clip_model)

            step._OCR_text = ocr_gen.generate(crop_image)
            step._EfficientNet_Features = efficientnet_gen.generate(crop_image)
            layoutlm_result = layoutlm_gen.generate(crop_image)
            step._LayoutLM_Type = layoutlm_result.get('type')
            step._LayoutLM_Confidence = json.dumps(layoutlm_result.get('confidence', {}))
            step._SAM_Mask = sam_gen.generate(crop_image)
            step._CLIP_Features = clip_gen.generate(crop_image)

            print(f"Models recalculated for step #{step.Step_number}")

        except Exception as e:
            print(f"Error recalculating models: {e}")
            import traceback
            traceback.print_exc()

    def save_step(self):
        if not self._db:
            print("No database")
            return

        try:
            if self._selected_step:
                if self._selected_step.Action_type == "INPUT":
                    input_val = self.ids.input_text_input.text.strip()
                    self._selected_step.Input_text = input_val if input_val else None

                if self._selected_step.Action_type == "SCROLL":
                    scroll_dx_val = self.ids.scroll_dx_input.text.strip()
                    scroll_dy_val = self.ids.scroll_dy_input.text.strip()
                    self._selected_step.Scroll_DX = int(scroll_dx_val) if scroll_dx_val else None
                    self._selected_step.Scroll_DY = int(scroll_dy_val) if scroll_dy_val else None

            modified_step_nums = list(self._bbox_modifications.keys())
            for step_num in modified_step_nums:
                step_to_save = None
                for step in self._steps:
                    if step.Step_number == step_num:
                        step_to_save = step
                        break

                if not step_to_save:
                    continue

                if step_to_save.Screenshot and step_to_save.BBox:
                    try:
                        nparr = np.frombuffer(step_to_save.Screenshot, np.uint8)
                        screenshot = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        bbox = json.loads(step_to_save.BBox)

                        x = int(bbox.get('x', 0))
                        y = int(bbox.get('y', 0))
                        w = int(bbox.get('w', 0))
                        h = int(bbox.get('h', 0))

                        crop_image = screenshot[y:y+h, x:x+w]
                        if crop_image.size > 0:
                            self._recalculate_bbox_models(step_to_save, crop_image)
                    except Exception as e:
                        print(f"Error extracting crop for step #{step_num}: {e}")

                self._db.update_step(step_to_save)
                print(f"Saved step #{step_num}")

            self._bbox_modifications.clear()

            self._steps = self._db.get_steps()
            for step in self._steps:
                if step.Step_number == self._selected_step.Step_number:
                    self._selected_step = step
                    break

            self._step_clean_values = {
                'tc': str(self._selected_step.Step_testcase) if self._selected_step.Step_testcase else "",
                'input_text': self._selected_step.Input_text if self._selected_step.Input_text else "",
                'scroll_dx': str(self._selected_step.Scroll_DX) if self._selected_step.Scroll_DX is not None else "",
                'scroll_dy': str(self._selected_step.Scroll_DY) if self._selected_step.Scroll_DY is not None else "",
            }
            self.ids.save_step_button.disabled = True

            self._populate_edit_panel(self._selected_step)

            print(f"Saved step #{self._selected_step.Step_number}")

        except ValueError as e:
            print(f"Error parsing numeric fields: {e}")
        except Exception as e:
            print(f"Error saving step: {e}")

    def go_home(self):
        self.manager.current = "menu"
