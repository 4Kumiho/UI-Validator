"""Executor: Main orchestrator for automated execution of Designer sessions."""

import os
import sys
import json
import logging
import time
import threading
from pathlib import Path
from pynput import keyboard

sys.path.insert(0, str(Path(__file__).parent.parent))

from Databases.designer_database import DesignerDatabase
from Databases.execution_database import ExecutionDatabase
from Databases.models import ExecutionStep
from Designer.Designer_Logic.screenshot_handler import ScreenshotHandler
from Models.model_registry import get_model
from Execution.Execution_Logic.scaling_calculator import calculate_scale_factors, is_perfect_match_compatible
from Execution.Execution_Logic.model_scorer import ModelScorer
from Execution.Execution_Logic.perfect_matcher import PerfectMatcher
from Execution.Execution_Logic.smart_matcher import SmartMatcher
from Execution.Execution_Logic.action_executor import ActionExecutor
from Execution.Execution_Interfaces.execution_ui import ExecutionUI
from Execution.Execution_Interfaces.execution_menu import ExecutionMenu

logger = logging.getLogger(__name__)


class Executor:
    """Orchestrates execution of Designer steps."""

    def __init__(self, designer_db_path: str, execution_session_folder: str, monitor_info: dict, settings: dict):
        """
        Initialize executor.

        Args:
            designer_db_path: Path to Designer database
            execution_session_folder: Path to execution session folder
            monitor_info: Dict with 'left', 'top', 'width', 'height', 'index'
            settings: Settings dict from settings.json
        """
        self.designer_db_path = designer_db_path
        self.execution_session_folder = execution_session_folder
        self.execution_db_path = os.path.join(execution_session_folder, 'execution.db')
        self.monitor_info = monitor_info
        self.settings = settings

        self.designer_db = None
        self.execution_db = None
        self.screenshot_handler = None
        self.model_scorer = None
        self.perfect_matcher = None
        self.smart_matcher = None
        self.action_executor = None
        self.execution_ui = None
        self.execution_menu = None

        self.should_stop = False
        self.should_pause = False
        self.menu_is_open = False
        self.keyboard_listener = None

    def start(self):
        """Start execution."""
        try:
            logger.info(f"[EXECUTOR] Starting execution for Designer DB: {self.designer_db_path}")

            # === PHASE 1: Fast initialization ===
            logger.info("[EXECUTOR] PHASE 1: Fast initialization")

            # Initialize databases
            self.designer_db = DesignerDatabase(self.designer_db_path)
            self.execution_db = ExecutionDatabase(self.execution_db_path)

            # Load Designer session and steps
            designer_session = self.designer_db.get_session()
            if not designer_session:
                logger.error("No Designer session found")
                return

            steps = self.designer_db.get_steps()
            if not steps:
                logger.error("No steps found in Designer session")
                return

            logger.info(f"[EXECUTOR] Loaded {len(steps)} steps from Designer DB")

            # Create execution session
            self.execution_db.create_session(designer_session.ID, self.designer_db_path)

            # Calculate scale factors
            exec_zoom = 1.0  # Default: same zoom as desktop
            scale_x, scale_y = calculate_scale_factors(designer_session, self.monitor_info, exec_zoom)
            is_perfect = is_perfect_match_compatible(scale_x, scale_y)

            # Initialize screenshot handler
            self.screenshot_handler = ScreenshotHandler(self.monitor_info)

            # Load models
            logger.info("[EXECUTOR] Loading AI models...")
            ocr_model = get_model('ocr')
            efficientnet_model = get_model('efficientnet')
            layoutlm_data = get_model('layoutlm')
            clip_data = get_model('clip')
            sam_model = get_model('sam')

            layoutlm_model, layoutlm_processor = layoutlm_data if isinstance(layoutlm_data, tuple) else (layoutlm_data, None)
            clip_model, clip_preprocess = clip_data if isinstance(clip_data, tuple) else (clip_data, None)

            # Create components
            self.model_scorer = ModelScorer(
                ocr_model=ocr_model,
                efficientnet_model=efficientnet_model,
                layoutlm_model=layoutlm_model,
                layoutlm_processor=layoutlm_processor,
                clip_model=clip_model,
                clip_preprocess=clip_preprocess,
                sam_model=sam_model
            )

            self.perfect_matcher = PerfectMatcher(self.screenshot_handler, self.model_scorer, self.settings)
            self.smart_matcher = SmartMatcher(self.screenshot_handler, self.model_scorer, self.settings)
            self.action_executor = ActionExecutor(self.monitor_info)
            self.execution_ui = ExecutionUI(self.monitor_info)
            self.execution_menu = ExecutionMenu(self.monitor_info, on_choice_callback=self._on_menu_choice)

            # Setup keyboard listener
            self._setup_keyboard_listener()

            # Center mouse
            center_x = self.monitor_info['left'] + self.monitor_info['width'] // 2
            center_y = self.monitor_info['top'] + self.monitor_info['height'] // 2
            from pynput.mouse import Controller as MouseController
            mouse_ctrl = MouseController()
            mouse_ctrl.position = (center_x, center_y)
            logger.info(f"[EXECUTOR] Mouse centered at ({center_x}, {center_y})")

            # === PHASE 2: Execution loop ===
            logger.info("[EXECUTOR] PHASE 2: Execution loop")
            self.execution_ui.set_ready()

            for i, step in enumerate(steps):
                # Check pause
                while self.should_pause and not self.should_stop:
                    time.sleep(0.1)

                if self.should_stop:
                    logger.info("[EXECUTOR] Stop requested")
                    break

                # Execute step
                logger.info(f"[EXECUTOR] Executing step {i + 1}/{len(steps)}: {step.Action_type}")
                exec_step = self._execute_step(step, scale_x, scale_y, is_perfect)

                # Save to DB
                self.execution_db.add_step(exec_step)

                # Check result
                if exec_step.Status in ('FAILED', 'STOPPED'):
                    logger.warning(f"[EXECUTOR] Step {i + 1} failed with status {exec_step.Status}")
                    # Mark remaining steps as skipped
                    for remaining_step in steps[i+1:]:
                        skipped = ExecutionStep(
                            Step_number=remaining_step.Step_number,
                            Action_type=remaining_step.Action_type,
                            Status='SKIPPED'
                        )
                        self.execution_db.add_step(skipped)
                    break

                # Sleep between steps
                if i < len(steps) - 1:
                    time.sleep(2)

            # Finalize
            logger.info("[EXECUTOR] Execution completed")
            self.execution_db.update_session_status(1, result='COMPLETED')

        except Exception as e:
            logger.error(f"[EXECUTOR] Fatal error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._cleanup()

    def _execute_step(self, step, scale_x, scale_y, is_perfect):
        """Execute a single step and return ExecutionStep."""
        exec_step = ExecutionStep(
            Step_number=step.Step_number,
            Step_testcase=step.Step_testcase,
            Action_type=step.Action_type,
            Status='PASSED'
        )

        try:
            # Capture screenshot
            screenshot = self.screenshot_handler.capture_full_screen()
            if screenshot is None:
                logger.error(f"[STEP {step.Step_number}] Failed to capture screenshot")
                exec_step.Status = 'FAILED'
                return exec_step

            # For INPUT actions, no matching needed - just type
            if step.Action_type == 'INPUT':
                self.action_executor.execute_input(step.Input_text, step.Enter_After_Input_text)
                exec_step.Status = 'PASSED'
                return exec_step

            # For DRAG_AND_DROP, match both source and destination
            if step.Action_type == 'DRAG_AND_DROP':
                # Match source (BBox)
                if is_perfect:
                    match_src = self.perfect_matcher.match(step, screenshot, scale_x, scale_y, use_drag=False)
                else:
                    match_src = self.smart_matcher.match(step, screenshot, scale_x, scale_y, use_drag=False)

                if not match_src.found:
                    logger.warning(f"[STEP {step.Step_number}] Source drag location not found")
                    exec_step.Status = 'FAILED'
                    return exec_step

                # Match destination (BBox_drag)
                if is_perfect:
                    match_dst = self.perfect_matcher.match(step, screenshot, scale_x, scale_y, use_drag=True)
                else:
                    match_dst = self.smart_matcher.match(step, screenshot, scale_x, scale_y, use_drag=True)

                if not match_dst.found:
                    logger.warning(f"[STEP {step.Step_number}] Destination drag location not found")
                    exec_step.Status = 'FAILED'
                    return exec_step

                # Parse relative coordinates
                src_rel = json.loads(step.BBox_rel_coordinates) if step.BBox_rel_coordinates else {'x': 0, 'y': 0}
                dst_rel = json.loads(step.BBox_drag_rel_coordinates) if step.BBox_drag_rel_coordinates else {'x': 0, 'y': 0}

                # Scale relative coordinates
                src_rel['x'] = int(src_rel.get('x', 0) * scale_x)
                src_rel['y'] = int(src_rel.get('y', 0) * scale_y)
                dst_rel['x'] = int(dst_rel.get('x', 0) * scale_x)
                dst_rel['y'] = int(dst_rel.get('y', 0) * scale_y)

                # Execute drag
                self.action_executor.execute_drag(
                    match_src.bbox_detected,
                    src_rel,
                    match_dst.bbox_detected,
                    dst_rel,
                    step.Modifier_keys
                )

                exec_step.Status = 'PASSED'
                exec_step.BBox_Match_Score = match_src.score.match_score if match_src.score else 0.0
                return exec_step

            # For SINGLE_CLICK, DOUBLE_CLICK, RIGHT_CLICK, SCROLL
            if is_perfect:
                match_result = self.perfect_matcher.match(step, screenshot, scale_x, scale_y)
            else:
                match_result = self.smart_matcher.match(step, screenshot, scale_x, scale_y)

            if not match_result.found:
                if is_perfect:
                    logger.info(f"[STEP {step.Step_number}] PERFECT MATCH failed, trying SMART MATCH")
                    match_result = self.smart_matcher.match(step, screenshot, scale_x, scale_y)

                if not match_result.found:
                    logger.warning(f"[STEP {step.Step_number}] Neither PERFECT nor SMART MATCH found")
                    exec_step.Status = 'FAILED'
                    return exec_step

            # Save match result to exec_step
            if match_result.score:
                exec_step.BBox_Match_Score = match_result.score.match_score
                exec_step.BBox_Template_Score = match_result.score.template_score
                exec_step.BBox_OCR_Score = match_result.score.ocr_score
                exec_step.BBox_EfficientNet_Score = match_result.score.efficientnet_score
                exec_step.BBox_LayoutLM_Score = match_result.score.layoutlm_score
                exec_step.BBox_CLIP_Score = match_result.score.clip_score
                exec_step.BBox_SAM_Score = match_result.score.sam_score
                exec_step.BBox_Exec_Detected = json.dumps(match_result.bbox_detected)

            exec_step.Matched_Attempt = match_result.attempt

            # Parse relative coordinates
            rel_coords = json.loads(step.BBox_rel_coordinates) if step.BBox_rel_coordinates else {'x': 0, 'y': 0}
            rel_coords['x'] = int(rel_coords.get('x', 0) * scale_x)
            rel_coords['y'] = int(rel_coords.get('y', 0) * scale_y)

            # Execute action
            if step.Action_type in ('SINGLE_CLICK', 'DOUBLE_CLICK', 'RIGHT_CLICK'):
                self.action_executor.execute_click(step.Action_type, match_result.bbox_detected, rel_coords, step.Modifier_keys)
            elif step.Action_type == 'SCROLL':
                self.action_executor.execute_scroll(
                    match_result.bbox_detected,
                    rel_coords,
                    step.Scroll_DX or 0,
                    step.Scroll_DY or 0,
                    step.Modifier_keys
                )

            exec_step.Status = 'PASSED'
            return exec_step

        except Exception as e:
            logger.error(f"[STEP {step.Step_number}] Error: {e}")
            import traceback
            traceback.print_exc()
            exec_step.Status = 'FAILED'
            return exec_step

    def _setup_keyboard_listener(self):
        """Setup keyboard listener for menu key."""
        menu_key = self.settings.get('execution', {}).get('open_menu_key', 'ESC').lower()

        def on_press(key):
            try:
                if key == keyboard.Key.esc:
                    self.should_pause = True
                    self.menu_is_open = True
                    logger.info("[EXECUTOR] Menu key pressed")
                    threading.Thread(target=self.execution_menu.show, daemon=True).start()
            except Exception as e:
                logger.debug(f"Keyboard listener error: {e}")

        self.keyboard_listener = keyboard.Listener(on_press=on_press)
        self.keyboard_listener.start()

    def _on_menu_choice(self, choice):
        """Handle menu choice."""
        self.menu_is_open = False

        if choice == 'resume':
            logger.info("[EXECUTOR] Resume execution")
            self.should_pause = False
        elif choice == 'stop':
            logger.info("[EXECUTOR] Stop execution")
            self.should_stop = True

    def _cleanup(self):
        """Cleanup resources."""
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        if self.screenshot_handler:
            self.screenshot_handler.stop()
        if self.designer_db:
            self.designer_db.close()
        if self.execution_db:
            self.execution_db.close()
