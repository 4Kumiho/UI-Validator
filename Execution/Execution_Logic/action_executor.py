"""Action execution using pynput for mouse and keyboard control."""

import json
import time
import logging
from pynput import mouse, keyboard

logger = logging.getLogger(__name__)

_MODIFIER_MAP = {
    "ctrl": keyboard.Key.ctrl_l,
    "shift": keyboard.Key.shift_l,
    "alt": keyboard.Key.alt_l,
    "tab": keyboard.Key.tab,
    "esc": keyboard.Key.esc,
    "f1": keyboard.Key.f1,
    "f2": keyboard.Key.f2,
    "f3": keyboard.Key.f3,
    "f4": keyboard.Key.f4,
    "f5": keyboard.Key.f5,
    "f6": keyboard.Key.f6,
    "f7": keyboard.Key.f7,
    "f8": keyboard.Key.f8,
    "f9": keyboard.Key.f9,
    "f10": keyboard.Key.f10,
    "f11": keyboard.Key.f11,
    "f12": keyboard.Key.f12,
    "home": keyboard.Key.home,
    "end": keyboard.Key.end,
    "page_up": keyboard.Key.page_up,
    "page_down": keyboard.Key.page_down,
    "insert": keyboard.Key.insert,
    "delete": keyboard.Key.delete,
}


class ActionExecutor:
    """Executes designer actions (click, input, drag, scroll) on target element."""

    def __init__(self, monitor_info: dict):
        """
        Initialize action executor.

        Args:
            monitor_info: Dict with keys: 'left', 'top', 'width', 'height'
        """
        self._monitor = monitor_info
        self._mouse = mouse.Controller()
        self._keyboard = keyboard.Controller()

    def _get_modifier_keys(self, modifier_keys_json):
        """Extract modifier keys from JSON string and return list of pynput Key objects."""
        if not modifier_keys_json:
            return []
        try:
            mods_list = json.loads(modifier_keys_json)
            return [_MODIFIER_MAP[m] for m in mods_list if m in _MODIFIER_MAP]
        except (json.JSONDecodeError, TypeError):
            return []

    def execute_click(self, action_type: str, bbox_detected: dict, rel_coords: dict, modifier_keys_json=None):
        """
        Execute click action.

        Args:
            action_type: 'SINGLE_CLICK', 'RIGHT_CLICK', or 'DOUBLE_CLICK'
            bbox_detected: {'x': int, 'y': int, 'w': int, 'h': int} in execution screen coordinates
            rel_coords: {'x': float, 'y': float} relative to bbox origin
            modifier_keys_json: JSON string with modifier keys
        """
        x = bbox_detected['x'] + int(rel_coords.get('x', 0)) + self._monitor['left']
        y = bbox_detected['y'] + int(rel_coords.get('y', 0)) + self._monitor['top']

        logger.info(f"[CLICK] {action_type} at ({x}, {y})")

        # Gradual mouse movement (simulate natural movement)
        current_x, current_y = self._mouse.position
        num_steps = 10
        for i in range(num_steps + 1):
            progress = i / num_steps
            move_x = int(current_x + (x - current_x) * progress)
            move_y = int(current_y + (y - current_y) * progress)
            self._mouse.position = (move_x, move_y)
            time.sleep(0.03)

        time.sleep(0.2)

        keys = self._get_modifier_keys(modifier_keys_json)
        try:
            for k in keys:
                self._keyboard.press(k)
            time.sleep(0.15)

            if action_type == 'SINGLE_CLICK':
                self._mouse.press(mouse.Button.left)
                time.sleep(0.05)
                self._mouse.release(mouse.Button.left)
            elif action_type == 'RIGHT_CLICK':
                self._mouse.press(mouse.Button.right)
                time.sleep(0.05)
                self._mouse.release(mouse.Button.right)
            elif action_type == 'DOUBLE_CLICK':
                self._mouse.press(mouse.Button.left)
                time.sleep(0.05)
                self._mouse.release(mouse.Button.left)
                time.sleep(0.1)
                self._mouse.press(mouse.Button.left)
                time.sleep(0.05)
                self._mouse.release(mouse.Button.left)
        finally:
            time.sleep(0.05)
            for k in reversed(keys):
                self._keyboard.release(k)

    def execute_input(self, input_text: str, enter_after: bool = False):
        """
        Execute text input action.

        Args:
            input_text: Text to type
            enter_after: If True, press Enter after typing
        """
        text = input_text or ""
        logger.info(f"[INPUT] Typing {len(text)} chars" + (" + ENTER" if enter_after else ""))

        for char in text:
            if char == ' ':
                self._keyboard.press(keyboard.Key.space)
                self._keyboard.release(keyboard.Key.space)
            else:
                self._keyboard.type(char)
            time.sleep(0.02)

        if enter_after:
            time.sleep(0.1)
            self._keyboard.press(keyboard.Key.enter)
            self._keyboard.release(keyboard.Key.enter)

    def execute_scroll(self, bbox_detected: dict, rel_coords: dict, scroll_dx: int, scroll_dy: int, modifier_keys_json=None):
        """
        Execute scroll action.

        Args:
            bbox_detected: {'x': int, 'y': int, 'w': int, 'h': int} in execution screen coordinates
            rel_coords: {'x': float, 'y': float} relative to bbox origin
            scroll_dx: Horizontal scroll amount
            scroll_dy: Vertical scroll amount
            modifier_keys_json: JSON string with modifier keys
        """
        center_x = bbox_detected['x'] + int(rel_coords.get('x', 0)) + self._monitor['left']
        center_y = bbox_detected['y'] + int(rel_coords.get('y', 0)) + self._monitor['top']

        logger.info(f"[SCROLL] at ({center_x}, {center_y}): dx={scroll_dx}, dy={scroll_dy}")

        self._mouse.position = (center_x, center_y)
        time.sleep(0.1)

        keys = self._get_modifier_keys(modifier_keys_json)
        try:
            for k in keys:
                self._keyboard.press(k)
            time.sleep(0.15)

            self._mouse.scroll(scroll_dx, scroll_dy)
        finally:
            time.sleep(0.05)
            for k in reversed(keys):
                self._keyboard.release(k)

    def execute_drag(self, src_bbox: dict, src_rel: dict, dst_bbox: dict, dst_rel: dict, modifier_keys_json=None):
        """
        Execute drag and drop action.

        Args:
            src_bbox: Source element {'x': int, 'y': int, 'w': int, 'h': int}
            src_rel: Source relative coords {'x': float, 'y': float}
            dst_bbox: Destination element {'x': int, 'y': int, 'w': int, 'h': int}
            dst_rel: Destination relative coords {'x': float, 'y': float}
            modifier_keys_json: JSON string with modifier keys
        """
        start_x = src_bbox['x'] + int(src_rel.get('x', 0)) + self._monitor['left']
        start_y = src_bbox['y'] + int(src_rel.get('y', 0)) + self._monitor['top']

        end_x = dst_bbox['x'] + int(dst_rel.get('x', 0)) + self._monitor['left']
        end_y = dst_bbox['y'] + int(dst_rel.get('y', 0)) + self._monitor['top']

        logger.info(f"[DRAG] from ({start_x}, {start_y}) to ({end_x}, {end_y})")

        self._mouse.position = (start_x, start_y)
        time.sleep(0.1)

        keys = self._get_modifier_keys(modifier_keys_json)
        try:
            for k in keys:
                self._keyboard.press(k)
            time.sleep(0.15)

            self._mouse.press(mouse.Button.left)
            time.sleep(0.1)

            num_steps = 50
            for i in range(num_steps + 1):
                progress = i / num_steps
                x = int(start_x + (end_x - start_x) * progress)
                y = int(start_y + (end_y - start_y) * progress)
                self._mouse.position = (x, y)
                time.sleep(0.05)

            self._mouse.release(mouse.Button.left)
        finally:
            time.sleep(0.05)
            for k in reversed(keys):
                self._keyboard.release(k)
