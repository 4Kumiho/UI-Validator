"""SMART MATCH - fullscreen search with cascading filters."""

import json
import logging
import numpy as np
import cv2
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Candidate:
    """A candidate location found during fullscreen search."""
    x: int
    y: int
    w: int
    h: int
    scores: dict = None  # {model_name: score}


class SmartMatcher:
    """Matches using fullscreen slicing window with cascading model filters."""

    def __init__(self, screenshot_handler, model_scorer, settings):
        """
        Initialize smart matcher.

        Args:
            screenshot_handler: ScreenshotHandler for screenshots
            model_scorer: ModelScorer instance
            settings: settings dict with execution config
        """
        self.screenshot_handler = screenshot_handler
        self.model_scorer = model_scorer
        self.settings = settings

    def _get_field_name(self, base_name: str, use_drag: bool = False) -> str:
        """Get the field name for a reference (e.g., BBox_OCR_text or BBox_drag_OCR_text)."""
        if use_drag:
            return f"BBox_drag_{base_name}"
        return f"BBox_{base_name}"

    def match(self, step, screenshot, scale_x, scale_y, use_drag=False):
        """
        Match using fullscreen search with cascading filters.

        Args:
            step: DesignerStep
            screenshot: numpy array (BGR)
            scale_x: float
            scale_y: float
            use_drag: bool - if True, use BBox_drag instead of BBox

        Returns:
            MatchResult (from perfect_matcher_module)
        """
        from .perfect_matcher import MatchResult

        try:
            # Parse bbox (use BBox_drag if use_drag=True)
            bbox_field = step.BBox_drag if use_drag else step.BBox
            bbox_dict = json.loads(bbox_field) if bbox_field else None
            if not bbox_dict:
                bbox_type = "BBox_drag" if use_drag else "BBox"
                logger.warning(f"[SMART MATCH] No {bbox_type} found in step")
                return MatchResult(found=False, attempt=2, bbox_detected={}, score=None, crop_bytes=b'')

            scaled_w = int(bbox_dict['w'] * scale_x)
            scaled_h = int(bbox_dict['h'] * scale_y)

            if scaled_w <= 0 or scaled_h <= 0:
                logger.warning(f"[SMART MATCH] Invalid scaled dimensions: w={scaled_w}, h={scaled_h}")
                return MatchResult(found=False, attempt=2, bbox_detected={}, score=None, crop_bytes=b'')

            # Get template reference (drag-specific if use_drag=True)
            template_field = step.BBox_drag_Template if use_drag else step.BBox_Template
            template_bytes = template_field
            if not template_bytes:
                template_type = "BBox_drag_Template" if use_drag else "BBox_Template"
                logger.warning(f"[SMART MATCH] No {template_type} found")
                return MatchResult(found=False, attempt=2, bbox_detected={}, score=None, crop_bytes=b'')

            template = cv2.imdecode(np.frombuffer(template_bytes, np.uint8), cv2.IMREAD_COLOR)
            if template is None or template.size == 0:
                logger.warning("[SMART MATCH] Could not decode template")
                return MatchResult(found=False, attempt=2, bbox_detected={}, score=None, crop_bytes=b'')

            # Resize template to scaled dimensions
            template_resized = cv2.resize(template, (scaled_w, scaled_h))

            # Step 0: Fullscreen template matching to gather candidates
            logger.info("[SMART MATCH] Step 0: Template matching on fullscreen")
            candidates = self._template_matching_fullscreen(screenshot, template_resized, scaled_w, scaled_h)

            if not candidates:
                logger.info("[SMART MATCH] No candidates from template matching")
                return MatchResult(found=False, attempt=2, bbox_detected={}, score=None, crop_bytes=b'')

            logger.info(f"[SMART MATCH] Found {len(candidates)} candidates from template matching")

            # Cascading filter stages from settings
            filter_stages = self.settings.get('execution', {}).get('smart_match_filter_stages', [])

            for stage_idx, stage in enumerate(filter_stages):
                model_name = stage.get('model')
                threshold = stage.get('threshold', 0.90)

                logger.info(f"[SMART MATCH] Stage {stage_idx + 1}: {model_name} (threshold={threshold:.2f})")

                if model_name == 'template':
                    # Template already done in step 0, just filter by threshold
                    candidates = [c for c in candidates if c.scores.get('template', 0.0) >= threshold]

                elif model_name == 'ocr':
                    # Skip if no OCR reference
                    ocr_text = getattr(step, self._get_field_name('OCR_text', use_drag), None)
                    if not ocr_text or ocr_text.strip() == "":
                        logger.debug(f"[SMART MATCH] Skipping {model_name} (no reference)")
                        continue

                    # Score OCR on each candidate crop
                    for candidate in candidates:
                        crop = self._extract_crop(screenshot, candidate)
                        if crop.size == 0:
                            candidate.scores['ocr'] = 0.0
                            continue
                        score, _ = self.model_scorer.score_ocr(crop, ocr_text)
                        candidate.scores['ocr'] = score

                    candidates = [c for c in candidates if c.scores.get('ocr', 0.0) >= threshold]

                elif model_name == 'efficientnet':
                    # Skip if no EfficientNet reference
                    enet_features = getattr(step, self._get_field_name('EfficientNet_Features', use_drag), None)
                    if not enet_features:
                        logger.debug(f"[SMART MATCH] Skipping {model_name} (no reference)")
                        continue

                    # Score EfficientNet on each candidate crop
                    for candidate in candidates:
                        crop = self._extract_crop(screenshot, candidate)
                        if crop.size == 0:
                            candidate.scores['efficientnet'] = 0.0
                            continue
                        score, _ = self.model_scorer.score_efficientnet(crop, enet_features)
                        candidate.scores['efficientnet'] = score

                    candidates = [c for c in candidates if c.scores.get('efficientnet', 0.0) >= threshold]

                elif model_name == 'layoutlm':
                    # Skip if no LayoutLM reference
                    lm_type = getattr(step, self._get_field_name('LayoutLM_Type', use_drag), None)
                    if not lm_type:
                        logger.debug(f"[SMART MATCH] Skipping {model_name} (no reference)")
                        continue

                    # Score LayoutLM on each candidate crop
                    ocr_text = getattr(step, self._get_field_name('OCR_text', use_drag), None)
                    for candidate in candidates:
                        crop = self._extract_crop(screenshot, candidate)
                        if crop.size == 0:
                            candidate.scores['layoutlm'] = 0.0
                            continue
                        score, _, _ = self.model_scorer.score_layoutlm(crop, lm_type, ocr_text)
                        candidate.scores['layoutlm'] = score

                    candidates = [c for c in candidates if c.scores.get('layoutlm', 0.0) >= threshold]

                elif model_name == 'clip':
                    # Skip if no CLIP reference
                    clip_features = getattr(step, self._get_field_name('CLIP_Features', use_drag), None)
                    if not clip_features:
                        logger.debug(f"[SMART MATCH] Skipping {model_name} (no reference)")
                        continue

                    # Score CLIP on each candidate crop
                    for candidate in candidates:
                        crop = self._extract_crop(screenshot, candidate)
                        if crop.size == 0:
                            candidate.scores['clip'] = 0.0
                            continue
                        score, _ = self.model_scorer.score_clip(crop, clip_features)
                        candidate.scores['clip'] = score

                    candidates = [c for c in candidates if c.scores.get('clip', 0.0) >= threshold]

                elif model_name == 'sam':
                    # Skip if no SAM reference
                    sam_contours = getattr(step, self._get_field_name('SAM_Contours', use_drag), None)
                    if not sam_contours:
                        logger.debug(f"[SMART MATCH] Skipping {model_name} (no reference)")
                        continue

                    # Get click point from appropriate field
                    click_x, click_y = 0, 0
                    rel_coords_field = self._get_field_name('rel_coordinates', use_drag)
                    rel_coords_str = getattr(step, rel_coords_field, None)
                    if rel_coords_str:
                        try:
                            rel_coords = json.loads(rel_coords_str)
                            click_x = int(rel_coords.get('x', 0) * scale_x)
                            click_y = int(rel_coords.get('y', 0) * scale_y)
                        except (json.JSONDecodeError, ValueError, TypeError):
                            pass

                    # Score SAM on each candidate crop
                    for candidate in candidates:
                        crop = self._extract_crop(screenshot, candidate)
                        if crop.size == 0:
                            candidate.scores['sam'] = 0.0
                            continue
                        score, _, _ = self.model_scorer.score_sam(crop, sam_contours, click_x, click_y)
                        candidate.scores['sam'] = score

                    candidates = [c for c in candidates if c.scores.get('sam', 0.0) >= threshold]

                logger.info(f"[SMART MATCH] Candidates remaining after {model_name}: {len(candidates)}")

                if not candidates:
                    logger.info(f"[SMART MATCH] ✗ No candidates after {model_name} filter")
                    return MatchResult(found=False, attempt=2, bbox_detected={}, score=None, crop_bytes=b'')

            # Select best candidate by weighted score
            best_candidate = None
            best_score = -1.0

            weights_dict = self.settings.get('execution', {}).get('model_weights', {})

            for candidate in candidates:
                weighted_score = self.model_scorer.compute_weighted_score(candidate.scores, weights_dict)
                if weighted_score > best_score:
                    best_score = weighted_score
                    best_candidate = candidate

            if best_candidate is None:
                logger.info("[SMART MATCH] ✗ No best candidate found")
                return MatchResult(found=False, attempt=2, bbox_detected={}, score=None, crop_bytes=b'')

            # Extract final crop and create score result
            crop_final = self._extract_crop(screenshot, best_candidate)
            _, crop_png = cv2.imencode('.png', crop_final)

            # Build score result for final candidate
            final_score_result = self.model_scorer.score_crop(crop_final, step, use_drag=use_drag)
            final_score_result.match_score = best_score

            logger.info(f"[SMART MATCH] ✓ FOUND at ({best_candidate.x}, {best_candidate.y}) with score {best_score:.3f}")

            return MatchResult(
                found=True,
                attempt=2,
                bbox_detected={'x': best_candidate.x, 'y': best_candidate.y, 'w': best_candidate.w, 'h': best_candidate.h},
                score=final_score_result,
                crop_bytes=crop_png.tobytes()
            )

        except Exception as e:
            logger.error(f"[SMART MATCH] Error: {e}")
            import traceback
            traceback.print_exc()
            return MatchResult(found=False, attempt=2, bbox_detected={}, score=None, crop_bytes=b'')

    def _template_matching_fullscreen(self, screenshot, template_resized, scaled_w, scaled_h):
        """
        Perform template matching on fullscreen and collect all candidates.

        Args:
            screenshot: numpy array (BGR)
            template_resized: numpy array (BGR) resized to target dimensions
            scaled_w: int
            scaled_h: int

        Returns:
            list of Candidate objects, sorted by template_score descending
        """
        try:
            result = cv2.matchTemplate(screenshot, template_resized, cv2.TM_CCOEFF_NORMED)
            if result.size == 0:
                return []

            # Collect all candidates above 0
            candidates = []
            h, w = template_resized.shape[:2]

            for y in range(result.shape[0]):
                for x in range(result.shape[1]):
                    score = float(result[y, x])
                    if score > 0.0:
                        # Candidate position is where the template's top-left corner aligns
                        candidates.append(Candidate(
                            x=x,
                            y=y,
                            w=scaled_w,
                            h=scaled_h,
                            scores={'template': max(0.0, min(1.0, score))}
                        ))

            # Sort by template score descending
            candidates.sort(key=lambda c: c.scores['template'], reverse=True)

            return candidates

        except Exception as e:
            logger.warning(f"Template matching failed: {e}")
            return []

    def _extract_crop(self, screenshot, candidate):
        """
        Extract crop from screenshot at candidate location.

        Args:
            screenshot: numpy array (BGR)
            candidate: Candidate object

        Returns:
            numpy array (BGR) or empty array if out of bounds
        """
        x, y, w, h = candidate.x, candidate.y, candidate.w, candidate.h

        # Bounds check
        if y < 0 or y + h > screenshot.shape[0]:
            return np.array([], dtype=np.uint8)
        if x < 0 or x + w > screenshot.shape[1]:
            return np.array([], dtype=np.uint8)

        crop = screenshot[y:y+h, x:x+w]
        return crop
