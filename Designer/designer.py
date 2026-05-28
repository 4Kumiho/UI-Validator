"""Designer - Recording orchestrator."""

import os
import sys
import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import cv2

from Databases.designer_database import DesignerDatabase
from Databases.models import DesignerStep
from Models.model_registry import get_model
from Designer.Designer_Logic.screenshot_handler import ScreenshotHandler
from Designer.Designer_Logic.bbox_generator import BBoxGenerator
from Designer.Designer_Logic.action_capture import ActionCapture
from Designer.Designer_Logic.ocr_generator import OCRGenerator
from Designer.Designer_Logic.efficientnet_generator import EfficientNetGenerator
from Designer.Designer_Logic.layoutlm_generator import LayoutLMGenerator
from Designer.Designer_Logic.sam_generator import SAMGenerator
from Designer.Designer_Logic.clip_generator import CLIPGenerator
from Designer.Designer_Interfaces.designer_ui import MiniUI
from Designer.Designer_Interfaces.designer_menu import DesignerMenu

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Designer:
    def __init__(self, session_name: str, save_folder: str, monitor_info: dict, settings: dict = None,
                 ocr_model=None, efficientnet_model=None, layoutlm_model=None, layoutlm_processor=None,
                 sam_model=None, clip_model=None, clip_preprocess=None):
        """
        session_name: nome della sessione
        save_folder: cartella dove salvare il DB
        monitor_info: dict con left, top, width, height del monitor
        settings: dict con config (default: Open_Designer_Menu_key)
        ocr_model: OCR model (PaddleOCR)
        efficientnet_model: EfficientNetV2-L model
        layoutlm_model: LayoutLMv3 model for UI element type classification
        layoutlm_processor: LayoutLMv3 processor
        sam_model: SAM (Segment Anything) model for precise element detection
        clip_model: CLIP model
        clip_preprocess: CLIP preprocessing function
        """
        self.session_name = session_name
        self.save_folder = save_folder
        self.monitor_info = monitor_info
        self.settings = settings or {'Open_Designer_Menu_key': 'ctrl+shift+d'}

        # Models passed from caller
        self.ocr_model = ocr_model
        self.efficientnet_model = efficientnet_model
        self.layoutlm_model = layoutlm_model
        self.layoutlm_processor = layoutlm_processor
        self.sam_model = sam_model
        self.clip_model = clip_model
        self.clip_preprocess = clip_preprocess

        # State
        self.should_stop = False
        self.recording_active = False

        # Database
        self.project_folder = os.path.join(save_folder, session_name)
        self.db_path = os.path.join(self.project_folder, f"{session_name}_designer.db")
        self.db = None

        # UI & Capture
        self.mini_ui = None
        self.action_capture = None
        self.menu_thread = None

        # Screenshot buffer
        self._screenshot_buffer = None

        # Step counter (shows next step number, not current)
        self.step_count = 1

    def start(self):
        """Avvia la registrazione."""
        try:
            self._initialize()
            self._start_recording()
            self._main_loop()
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            self._cleanup()

    def _initialize(self):
        """Inizializza cartella e database."""
        logger.info(f"[INIT] Creating project folder: {self.project_folder}")
        Path(self.project_folder).mkdir(parents=True, exist_ok=True)

        logger.info(f"[INIT] Creating database: {self.db_path}")
        self.db = DesignerDatabase(self.db_path)

        # Get screen info
        screen_resolution = {
            "width": self.monitor_info.get("width"),
            "height": self.monitor_info.get("height")
        }
        screen_zoom = {"zoom_level": 100, "unit": "percent"}

        # Create session
        self.db.create_session(
            screen_resolution=json.dumps(screen_resolution),
            screen_zoom=json.dumps(screen_zoom)
        )
        logger.info("[INIT] Session created")


    def _start_recording(self):
        """Avvia la cattura delle azioni."""
        logger.info("[RECORDING] Starting...")

        # Minimize Kivy window (Windows only)
        try:
            import ctypes
            hwnd = ctypes.windll.kernel32.GetForegroundWindow()
            ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
        except Exception:
            pass

        # Center mouse on monitor
        screen_center_x = self.monitor_info['left'] + self.monitor_info['width'] // 2
        screen_center_y = self.monitor_info['top'] + self.monitor_info['height'] // 2
        from pynput.mouse import Controller
        Controller().position = (screen_center_x, screen_center_y)

        # Create UI
        self.mini_ui = MiniUI(self.monitor_info, corner="bottom-left")
        self.mini_ui.set_loading()

        # Create screenshot handler
        self.screenshot_handler = ScreenshotHandler(self.monitor_info)

        # Capture first screenshot
        self._screenshot_buffer = self.screenshot_handler.capture_full_screen()

        # Mark as ready
        self.recording_active = True
        self.mini_ui.set_ready()
        logger.info("[RECORDING] Ready")

        # Start action capture
        self.action_capture = ActionCapture(
            settings=self.settings,
            monitor_info=self.monitor_info,
            on_action_callback=self._on_action_captured,
            on_menu_callback=self._on_menu_requested,
            get_recording_active=lambda: self.recording_active
        )
        self.action_capture.start_recording()

    def _main_loop(self):
        """Main loop di registrazione."""
        logger.info("[LOOP] Starting main loop...")
        while not self.should_stop:
            time.sleep(0.05)
        logger.info("[LOOP] Main loop ended")

    def _on_action_captured(self, action_dict: dict):
        """Callback quando un'azione viene catturata."""
        if not self.recording_active:
            logger.debug("[ACTION] Recording not active, ignoring action")
            return

        self.recording_active = False
        self.mini_ui.set_saving()

        try:
            action_type = action_dict['action_type']
            logger.info(f"[ACTION] {action_type}")

            # Get relative coordinates within monitor
            coords = action_dict['coordinates']
            click_x = coords['x'] - self.monitor_info['left']
            click_y = coords['y'] - self.monitor_info['top']

            # Get screenshot
            screenshot = self._screenshot_buffer

            # Process action based on type
            if action_type in ['SINGLE_CLICK', 'DOUBLE_CLICK', 'RIGHT_CLICK', 'SCROLL']:
                self._process_click_action(action_dict, screenshot, click_x, click_y)
            elif action_type == 'DRAG_AND_DROP':
                self._process_drag_action(action_dict, screenshot)
            else:
                logger.warning(f"Unknown action type: {action_type}")

            # Update step counter and UI
            logger.debug(f"[COUNTER] Before increment: {self.step_count}")
            self.step_count += 1
            logger.info(f"[COUNTER] After increment: {self.step_count}")
            self.mini_ui.set_step(self.step_count)
            logger.info(f"[UI] MiniUI updated with step {self.step_count}")

        except Exception as e:
            logger.error(f"Error processing action: {e}", exc_info=True)
        finally:
            # Capture next screenshot
            self._screenshot_buffer = self.screenshot_handler.capture_full_screen()
            self.recording_active = True
            self.mini_ui.set_ready()

    def _process_click_action(self, action_dict: dict, screenshot: np.ndarray, click_x: int, click_y: int):
        """Processa SINGLE_CLICK, DOUBLE_CLICK, RIGHT_CLICK, SCROLL."""
        action_type = action_dict['action_type']
        pressed_keys = action_dict.get('pressed_keys', [])

        # Generate BBox (OCR + SAM merge for icon + text)
        bbox = BBoxGenerator.generate_smart_bbox_with_ai(screenshot, click_x, click_y,
                                                         ocr_model=self.ocr_model, sam_model=self.sam_model)
        bbox_image = BBoxGenerator.crop_image(screenshot, bbox)

        # Extract features
        ocr_text = OCRGenerator.extract(self.ocr_model, bbox_image)
        efficientnet_features = EfficientNetGenerator.extract(self.efficientnet_model, bbox_image)
        layoutlm_type, layoutlm_confidence = LayoutLMGenerator.extract(self.layoutlm_model, self.layoutlm_processor, bbox_image)
        sam_mask, sam_contours = SAMGenerator.extract(self.sam_model, bbox_image, click_x - bbox['x'], click_y - bbox['y'])
        clip_features = CLIPGenerator.extract(self.clip_model, self.clip_preprocess, bbox_image)

        # Screenshot PNG
        _, screenshot_png = cv2.imencode('.png', screenshot)
        _, bbox_template_png = cv2.imencode('.png', bbox_image)

        # Relative coordinates within bbox
        rel_coords = {
            "x": click_x - bbox['x'],
            "y": click_y - bbox['y']
        }

        # Special handling for SCROLL
        if action_type == 'SCROLL':
            scroll = action_dict.get('scroll', {'dx': 0, 'dy': 0})
            step = DesignerStep(
                Step_number=self.step_count + 1,
                Action_type='SCROLL',
                Screenshot=screenshot_png.tobytes(),
                Modifier_keys=json.dumps(pressed_keys),
                BBox=json.dumps(bbox),
                BBox_rel_coordinates=json.dumps(rel_coords),
                BBox_Template=bbox_template_png.tobytes(),
                BBox_OCR_text=ocr_text,
                BBox_EfficientNet_Features=efficientnet_features,
                BBox_LayoutLM_Type=layoutlm_type,
                BBox_LayoutLM_Confidence=layoutlm_confidence,
                BBox_SAM_Mask=sam_mask,
                BBox_SAM_Contours=sam_contours,
                BBox_CLIP_Features=clip_features,
                Scroll_DX=scroll.get('dx', 0),
                Scroll_DY=scroll.get('dy', 0)
            )
        else:
            step = DesignerStep(
                Step_number=self.step_count + 1,
                Action_type=action_type,
                Screenshot=screenshot_png.tobytes(),
                Modifier_keys=json.dumps(pressed_keys),
                BBox=json.dumps(bbox),
                BBox_rel_coordinates=json.dumps(rel_coords),
                BBox_Template=bbox_template_png.tobytes(),
                BBox_OCR_text=ocr_text,
                BBox_EfficientNet_Features=efficientnet_features,
                BBox_LayoutLM_Type=layoutlm_type,
                BBox_LayoutLM_Confidence=layoutlm_confidence,
                BBox_SAM_Mask=sam_mask,
                BBox_SAM_Contours=sam_contours,
                BBox_CLIP_Features=clip_features
            )

        self.db.add_step(step)
        logger.info(f"[DB] Step {self.step_count + 1} saved: {action_type}")

    def _process_drag_action(self, action_dict: dict, screenshot: np.ndarray):
        """Processa DRAG_AND_DROP."""
        pressed_keys = action_dict.get('pressed_keys', [])
        drag = action_dict.get('drag', {})

        start_x = drag.get('start_x') - self.monitor_info['left']
        start_y = drag.get('start_y') - self.monitor_info['top']
        end_x = drag.get('end_x') - self.monitor_info['left']
        end_y = drag.get('end_y') - self.monitor_info['top']

        # Generate BBox for start (OCR + SAM merge)
        bbox_start = BBoxGenerator.generate_smart_bbox_with_ai(screenshot, start_x, start_y,
                                                               ocr_model=self.ocr_model, sam_model=self.sam_model)
        bbox_start_image = BBoxGenerator.crop_image(screenshot, bbox_start)

        # Generate BBox for end (OCR + SAM merge)
        bbox_end = BBoxGenerator.generate_smart_bbox_with_ai(screenshot, end_x, end_y,
                                                             ocr_model=self.ocr_model, sam_model=self.sam_model)
        bbox_end_image = BBoxGenerator.crop_image(screenshot, bbox_end)

        # Extract features for start
        ocr_start = OCRGenerator.extract(self.ocr_model, bbox_start_image)
        efficientnet_start = EfficientNetGenerator.extract(self.efficientnet_model, bbox_start_image)
        layoutlm_type_start, layoutlm_conf_start = LayoutLMGenerator.extract(self.layoutlm_model, self.layoutlm_processor, bbox_start_image)
        sam_mask_start, sam_contours_start = SAMGenerator.extract(self.sam_model, bbox_start_image, start_x - bbox_start['x'], start_y - bbox_start['y'])
        clip_start = CLIPGenerator.extract(self.clip_model, self.clip_preprocess, bbox_start_image)

        # Extract features for end
        ocr_end = OCRGenerator.extract(self.ocr_model, bbox_end_image)
        efficientnet_end = EfficientNetGenerator.extract(self.efficientnet_model, bbox_end_image)
        layoutlm_type_end, layoutlm_conf_end = LayoutLMGenerator.extract(self.layoutlm_model, self.layoutlm_processor, bbox_end_image)
        sam_mask_end, sam_contours_end = SAMGenerator.extract(self.sam_model, bbox_end_image, end_x - bbox_end['x'], end_y - bbox_end['y'])
        clip_end = CLIPGenerator.extract(self.clip_model, self.clip_preprocess, bbox_end_image)

        # Screenshot PNG
        _, screenshot_png = cv2.imencode('.png', screenshot)
        _, bbox_start_png = cv2.imencode('.png', bbox_start_image)
        _, bbox_end_png = cv2.imencode('.png', bbox_end_image)

        # Relative coords
        rel_coords_start = {
            "x": start_x - bbox_start['x'],
            "y": start_y - bbox_start['y']
        }
        rel_coords_end = {
            "x": end_x - bbox_end['x'],
            "y": end_y - bbox_end['y']
        }

        step = DesignerStep(
            Step_number=self.step_count + 1,
            Action_type='DRAG_AND_DROP',
            Screenshot=screenshot_png.tobytes(),
            Modifier_keys=json.dumps(pressed_keys),
            BBox=json.dumps(bbox_start),
            BBox_rel_coordinates=json.dumps(rel_coords_start),
            BBox_Template=bbox_start_png.tobytes(),
            BBox_OCR_text=ocr_start,
            BBox_EfficientNet_Features=efficientnet_start,
            BBox_LayoutLM_Type=layoutlm_type_start,
            BBox_LayoutLM_Confidence=layoutlm_conf_start,
            BBox_SAM_Mask=sam_mask_start,
            BBox_SAM_Contours=sam_contours_start,
            BBox_CLIP_Features=clip_start,
            BBox_drag=json.dumps(bbox_end),
            BBox_drag_rel_coordinates=json.dumps(rel_coords_end),
            BBox_drag_Template=bbox_end_png.tobytes(),
            BBox_drag_OCR_text=ocr_end,
            BBox_drag_EfficientNet_Features=efficientnet_end,
            BBox_drag_LayoutLM_Type=layoutlm_type_end,
            BBox_drag_LayoutLM_Confidence=layoutlm_conf_end,
            BBox_drag_SAM_Mask=sam_mask_end,
            BBox_drag_SAM_Contours=sam_contours_end,
            BBox_drag_CLIP_Features=clip_end
        )

        self.db.add_step(step)
        logger.info(f"[DB] Step {self.step_count + 1} saved: DRAG_AND_DROP")

    def _on_menu_requested(self):
        """Callback quando l'utente preme il tasto hotkey menu."""
        self.recording_active = False
        self.mini_ui.set_saving()
        self.action_capture.set_menu_open(True)

        # Mostra il menu in un thread separato
        show_end_input = self.action_capture.input_active
        menu = DesignerMenu(
            self.monitor_info,
            show_end_input=show_end_input,
            on_choice_callback=self._on_menu_choice
        )
        self.menu_thread = threading.Thread(target=menu.show, daemon=True)
        self.menu_thread.start()

    def _on_menu_choice(self, choice: str):
        """Callback quando l'utente sceglie dal menu."""
        self.action_capture.set_menu_open(False)

        if choice == 'refresh':
            logger.info("[MENU] Refresh screenshot")
            self._screenshot_buffer = self.screenshot_handler.capture_full_screen()
            self.recording_active = True
            self.mini_ui.set_ready()

        elif choice == 'end_input':
            logger.info("[MENU] End input")
            self._finalize_input()
            self.recording_active = True
            self.mini_ui.set_ready()

        elif choice == 'end_session':
            logger.info("[MENU] End session")
            self.should_stop = True

    def _finalize_input(self):
        """Finalizza la sequenza di input."""
        if not self.action_capture.input_text:
            return

        # Get last step (il click sul campo di input)
        last_step = self.db.get_last_step()
        if not last_step:
            logger.warning("No previous step to finalize input")
            return

        # Create INPUT step riusando i dati del passo precedente
        screenshot = self._screenshot_buffer
        _, screenshot_png = cv2.imencode('.png', screenshot)

        input_step = DesignerStep(
            Step_number=self.step_count + 1,
            Action_type='INPUT',
            Screenshot=screenshot_png.tobytes(),
            Modifier_keys=json.dumps([]),
            BBox=last_step.BBox,
            BBox_Template=last_step.BBox_Template,
            BBox_rel_coordinates=last_step.BBox_rel_coordinates,
            BBox_OCR_text=last_step.BBox_OCR_text,
            BBox_EfficientNet_Features=last_step.BBox_EfficientNet_Features,
            BBox_LayoutLM_Type=last_step.BBox_LayoutLM_Type,
            BBox_LayoutLM_Confidence=last_step.BBox_LayoutLM_Confidence,
            BBox_SAM_Mask=last_step.BBox_SAM_Mask,
            BBox_SAM_Contours=last_step.BBox_SAM_Contours,
            BBox_CLIP_Features=last_step.BBox_CLIP_Features,
            Input_text=self.action_capture.input_text,
            Enter_After_Input_text=1 if self.action_capture.input_text.endswith('\n') else 0
        )

        self.db.add_step(input_step)
        self.step_count += 1
        self.mini_ui.set_step(self.step_count)

        self.action_capture.reset_input()
        logger.info(f"[DB] Step {self.step_count} saved: INPUT")

    def _cleanup(self):
        """Cleanup alla fine della sessione."""
        logger.info("[CLEANUP] Cleaning up...")

        if self.action_capture:
            self.action_capture.stop_recording()

        if self.mini_ui:
            self.mini_ui.close()

        if self.db:
            self.db.close()

        logger.info(f"[CLEANUP] Done. Database saved to: {self.db_path}")
