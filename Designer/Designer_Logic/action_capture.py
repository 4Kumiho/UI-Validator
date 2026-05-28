"""Action capture system - Automatic action capturing via global hooks."""

import time
import json
import sys
import logging
import threading
import numpy as np
from pynput import mouse, keyboard

logger = logging.getLogger(__name__)

# Mapping of pynput keyboard keys to human-readable names
KEY_MAPPING = {
    keyboard.Key.ctrl_l: 'ctrl', keyboard.Key.ctrl_r: 'ctrl',
    keyboard.Key.shift: 'shift', keyboard.Key.shift_r: 'shift',
    keyboard.Key.alt: 'alt', keyboard.Key.alt_r: 'alt',
    keyboard.Key.tab: 'tab', keyboard.Key.delete: 'delete',
    keyboard.Key.backspace: 'backspace', keyboard.Key.enter: 'enter',
    keyboard.Key.space: 'space', keyboard.Key.esc: 'esc',
    keyboard.Key.home: 'home', keyboard.Key.end: 'end',
    keyboard.Key.page_up: 'page_up', keyboard.Key.page_down: 'page_down',
    keyboard.Key.up: 'up', keyboard.Key.down: 'down',
    keyboard.Key.left: 'left', keyboard.Key.right: 'right',
    keyboard.Key.f1: 'f1', keyboard.Key.f2: 'f2', keyboard.Key.f3: 'f3',
    keyboard.Key.f4: 'f4', keyboard.Key.f5: 'f5', keyboard.Key.f6: 'f6',
    keyboard.Key.f7: 'f7', keyboard.Key.f8: 'f8', keyboard.Key.f9: 'f9',
    keyboard.Key.f10: 'f10', keyboard.Key.f11: 'f11', keyboard.Key.f12: 'f12',
}


class ActionCapture:
    def __init__(self, settings: dict, monitor_info: dict, on_action_callback=None, on_menu_callback=None, get_recording_active=None):
        """
        settings: dict con Open_Designer_Menu_key
        monitor_info: dict con left, top, width, height
        on_action_callback: (action_dict) -> quando azione catturata
        on_menu_callback: () -> quando hotkey menu premuto
        get_recording_active: callable che ritorna True se recording attivo (solo VERDE), False se ARANCIONE/ROSSO
        """
        self.settings = settings
        self.monitor_info = monitor_info
        self.on_action_callback = on_action_callback
        self.on_menu_callback = on_menu_callback
        self.get_recording_active = get_recording_active or (lambda: True)  # Default: sempre attivo

        self.menu_open = False
        self.input_active = False
        self.input_text = ""
        self.pressed_keys = set()

        self.mouse_listener = None
        self.keyboard_listener = None

        # Double-click detection - deferred registration
        self.last_click_time = 0
        self.last_click_pos = (0, 0)
        self.double_click_threshold = 0.5  # 500ms
        self.double_click_distance = 10  # 10px
        self.pending_click = None  # Pending single click awaiting double-click confirmation
        self.click_timer = None

        # Scroll debounce (consolidate multiple scroll events into one)
        self.last_scroll_time = 0
        self.scroll_debounce_threshold = 0.3  # 300ms - cattura tutti gli eventi di una singola azione
        self.pending_scroll = None

        # Drag detection
        self.dragging = False
        self.drag_start_pos = (0, 0)
        self.drag_end_pos = (0, 0)
        self.drag_threshold = 5  # minimo movimento in pixel per considerare un drag

        logger.debug("ActionCapture initialized")

    def start_recording(self):
        """Attiva global hooks per mouse e tastiera."""
        logger.debug("Starting recording...")

        self.mouse_listener = mouse.Listener(
            on_click=self._on_mouse_click,
            on_move=self._on_mouse_move,
            on_scroll=self._on_mouse_scroll
        )
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )

        self.mouse_listener.start()
        self.keyboard_listener.start()
        logger.debug("Listeners started")

    def stop_recording(self):
        """Ferma global hooks."""
        logger.debug("Stopping recording...")
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        logger.debug("Listeners stopped")

    def _on_mouse_click(self, x, y, button, pressed):
        """Cattura mouse click e drag."""
        if self.menu_open:
            return

        if button == mouse.Button.left:
            if pressed:
                # Mouse down: inizio potenziale drag
                logger.debug(f"MOUSE DOWN: pos=({x}, {y})")
                self.dragging = True
                self.drag_start_pos = (x, y)
                self.drag_end_pos = (x, y)
            else:
                # Mouse up: fine drag o click
                if not self.dragging:
                    return

                self.dragging = False
                dx = abs(self.drag_end_pos[0] - self.drag_start_pos[0])
                dy = abs(self.drag_end_pos[1] - self.drag_start_pos[1])
                distance = (dx**2 + dy**2) ** 0.5

                if distance >= self.drag_threshold:
                    # È un drag
                    logger.info(f"✓ DRAG from {self.drag_start_pos} to {self.drag_end_pos}")
                    self._process_drag(
                        self.drag_start_pos[0], self.drag_start_pos[1],
                        self.drag_end_pos[0], self.drag_end_pos[1]
                    )
                else:
                    # È un click (distanza < threshold) → deteccione doppio click
                    self._handle_click(self.drag_start_pos[0], self.drag_start_pos[1])
                return

        elif button == mouse.Button.right and pressed:
            logger.info(f"✓ RIGHT CLICK at ({x}, {y})")
            self._process_click(x, y, 'RIGHT_CLICK')

    def _handle_click(self, x, y):
        """Gestisce click singolo e doppio con deferred registration."""
        now = time.time()

        # Check if this is a double-click
        if self.pending_click:
            dx = abs(x - self.pending_click['x'])
            dy = abs(y - self.pending_click['y'])
            is_double_click = (
                (now - self.pending_click['time']) < self.double_click_threshold
                and dx < self.double_click_distance
                and dy < self.double_click_distance
            )

            # Cancel the pending single-click timer
            if self.click_timer:
                self.click_timer.cancel()
                self.click_timer = None

            if is_double_click:
                logger.info(f"✓ DOUBLE CLICK at ({x}, {y})")
                self._process_click(x, y, 'DOUBLE_CLICK')
                self.pending_click = None
            else:
                # Not a double-click: register pending click, then register this one
                logger.info(f"✓ LEFT CLICK at ({self.pending_click['x']}, {self.pending_click['y']})")
                self._process_click(self.pending_click['x'], self.pending_click['y'], 'SINGLE_CLICK')
                # Set new pending click
                self.pending_click = {'x': x, 'y': y, 'time': now}
                self._start_click_timer()
        else:
            # First click: defer registration and wait for potential double-click
            logger.debug(f"Click at ({x}, {y}) - waiting for potential double-click...")
            self.pending_click = {'x': x, 'y': y, 'time': now}
            self._start_click_timer()

    def _start_click_timer(self):
        """Avvia timer per registrare il pending click se non arriva un double-click."""
        if self.click_timer:
            self.click_timer.cancel()

        self.click_timer = threading.Timer(
            self.double_click_threshold,
            self._process_pending_click
        )
        self.click_timer.daemon = True
        self.click_timer.start()

    def _process_pending_click(self):
        """Registra il pending click come SINGLE_CLICK."""
        if self.pending_click:
            click_data = self.pending_click
            logger.info(f"✓ LEFT CLICK at ({click_data['x']}, {click_data['y']})")
            self._process_click(click_data['x'], click_data['y'], 'SINGLE_CLICK')
            self.pending_click = None
            self.click_timer = None

    def _on_mouse_move(self, x, y):
        """Traccia mouse movement per drag detection."""
        if self.dragging:
            self.drag_end_pos = (x, y)

    def _on_mouse_scroll(self, x, y, dx, dy):
        """Cattura scroll - consolida multipli eventi in uno (debounce)."""
        if self.menu_open:
            return

        # Accumula scroll deltas entro debounce threshold
        now = time.time()

        if self.pending_scroll is None:
            # Primo scroll event
            self.pending_scroll = {'x': x, 'y': y, 'dx': dx, 'dy': dy, 'time': now}
            logger.info(f"✓ SCROLL START: dx={dx}, dy={dy}")

            # Imposta timer per processare dopo debounce threshold
            self._scroll_timer = threading.Timer(
                self.scroll_debounce_threshold,
                self._process_pending_scroll
            )
            self._scroll_timer.daemon = True
            self._scroll_timer.start()
        else:
            # Accumula deltas
            self.pending_scroll['dx'] += dx
            self.pending_scroll['dy'] += dy
            logger.debug(f"  SCROLL ACCUMULATE: total dx={self.pending_scroll['dx']}, dy={self.pending_scroll['dy']}")

            # Resetta il timer: cancella vecchio e crea uno nuovo
            if self._scroll_timer:
                self._scroll_timer.cancel()

            self._scroll_timer = threading.Timer(
                self.scroll_debounce_threshold,
                self._process_pending_scroll
            )
            self._scroll_timer.daemon = True
            self._scroll_timer.start()

    def _process_pending_scroll(self):
        """Processa lo scroll accumulato dopo debounce."""
        if self.pending_scroll:
            scroll_data = self.pending_scroll
            logger.info(f"✓ SCROLL FINAL: dx={scroll_data['dx']}, dy={scroll_data['dy']}")
            self._process_scroll(scroll_data['x'], scroll_data['y'], scroll_data['dx'], scroll_data['dy'])
            self.pending_scroll = None

    def _on_key_release(self, key):
        """Cattura rilascio tasti."""
        try:
            self._update_pressed_keys(key, pressed=False)
        except Exception as e:
            logger.error(f"Error in key release: {e}")

    def _on_key_press(self, key):
        """Cattura tasti."""
        try:
            # Track pressed keys
            self._update_pressed_keys(key, pressed=True)

            # Check for menu hotkey
            menu_key = self.settings.get('Open_Designer_Menu_key')
            if not menu_key:
                logger.error("FATAL: Missing 'Open_Designer_Menu_key' in settings")
                return
            if self._check_menu_hotkey(menu_key):
                logger.info("✓ Menu hotkey detected")
                if self.on_menu_callback:
                    self.on_menu_callback()
                return

            # Character input (for typing)
            if hasattr(key, 'char') and key.char:
                self.input_active = True
                self.input_text += key.char
                logger.info(f"✎ Text buffer: '{self.input_text}'")

            # Special keys for input
            elif key == keyboard.Key.space:
                self.input_active = True
                self.input_text += ' '
                logger.info(f"✎ Text buffer: '{self.input_text}'")
            elif key == keyboard.Key.enter:
                self.input_active = True
                self.input_text += '\n'
                logger.info(f"✎ Text buffer (with newline): {repr(self.input_text)}")
            elif key == keyboard.Key.backspace:
                if self.input_text:
                    self.input_text = self.input_text[:-1]
                    self.input_active = True
                    logger.info(f"✎ Text buffer (after backspace): {repr(self.input_text)}")
            else:
                # Debug: log unknown keys per capire cosa viene premuto
                logger.debug(f"[KEY DEBUG] Unknown key: {key}, type: {type(key)}")
        except Exception as e:
            logger.error(f"Error in key press: {e}")

    def _update_pressed_keys(self, key, pressed):
        """Update the set of currently pressed keys using KEY_MAPPING lookup table."""
        try:
            key_name = KEY_MAPPING.get(key)
            if key_name:
                if pressed:
                    self.pressed_keys.add(key_name)
                else:
                    self.pressed_keys.discard(key_name)
        except (AttributeError, KeyError):
            pass

    def _check_menu_hotkey(self, hotkey_str):
        """Verifica se i tasti attualmente premuti corrispondono all'hotkey."""
        required_keys = set(hotkey_str.lower().split('+'))
        return self.pressed_keys == required_keys

    def _process_click(self, x, y, action_type):
        """Processa un click action."""
        if not self.get_recording_active():  # Ignora se recording non attivo
            logger.debug(f"Ignoring {action_type} - recording not active")
            return
        if self.on_action_callback:
            action = {
                'action_type': action_type,
                'coordinates': {"x": int(x), "y": int(y)},
                'pressed_keys': list(self.pressed_keys),
                'timestamp': time.time()
            }
            self.on_action_callback(action)

    def _process_scroll(self, x, y, dx, dy):
        """Processa uno scroll action."""
        if not self.get_recording_active():  # Ignora se recording non attivo
            logger.debug("Ignoring SCROLL - recording not active")
            return
        if self.on_action_callback:
            action = {
                'action_type': 'SCROLL',
                'coordinates': {"x": int(x), "y": int(y)},
                'scroll': {"dx": int(dx), "dy": int(dy)},
                'pressed_keys': list(self.pressed_keys),
                'timestamp': time.time()
            }
            self.on_action_callback(action)

    def _process_drag(self, start_x, start_y, end_x, end_y):
        """Processa un drag action."""
        if not self.get_recording_active():  # Ignora se recording non attivo
            logger.debug("Ignoring DRAG_AND_DROP - recording not active")
            return
        if self.on_action_callback:
            action = {
                'action_type': 'DRAG_AND_DROP',
                'coordinates': {"x": int(start_x), "y": int(start_y)},
                'drag': {
                    "start_x": int(start_x),
                    "start_y": int(start_y),
                    "end_x": int(end_x),
                    "end_y": int(end_y)
                },
                'pressed_keys': list(self.pressed_keys),
                'timestamp': time.time()
            }
            self.on_action_callback(action)

    def set_menu_open(self, is_open: bool):
        """Setta lo stato del menu."""
        self.menu_open = is_open

    def reset_input(self):
        """Resetta lo stato di input."""
        self.input_active = False
        self.input_text = ""
