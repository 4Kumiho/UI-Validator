"""PERFECT MATCH - exact coordinate matching with all 6 models."""

import json
import logging
import numpy as np
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Result from a matching attempt."""
    found: bool
    attempt: int                    # 1 = PERFECT, 2 = SMART
    bbox_detected: dict             # {x, y, w, h} in execution coordinates
    score: object                   # ScoreResult from model_scorer
    crop_bytes: bytes               # PNG-encoded crop detected


class PerfectMatcher:
    """Matches using exact designer coordinates with all 6 models."""

    def __init__(self, screenshot_handler, model_scorer, settings):
        """
        Initialize perfect matcher.

        Args:
            screenshot_handler: ScreenshotHandler for capturing screenshots
            model_scorer: ModelScorer instance
            settings: settings dict with execution config
        """
        self.screenshot_handler = screenshot_handler
        self.model_scorer = model_scorer
        self.settings = settings

    def match(self, step, screenshot, scale_x, scale_y, use_drag=False):
        """
        Match at exact designer coordinates (scaled).

        Args:
            step: DesignerStep
            screenshot: numpy array (BGR) of current screenshot
            scale_x: float
            scale_y: float
            use_drag: bool - if True, use BBox_drag instead of BBox

        Returns:
            MatchResult
        """
        try:
            # Parse bbox (use BBox_drag if use_drag=True)
            bbox_field = step.BBox_drag if use_drag else step.BBox
            bbox_dict = json.loads(bbox_field) if bbox_field else None
            if not bbox_dict:
                bbox_type = "BBox_drag" if use_drag else "BBox"
                logger.warning(f"[PERFECT MATCH] No {bbox_type} found in step")
                return MatchResult(found=False, attempt=1, bbox_detected={}, score=None, crop_bytes=b'')

            # Scale coordinates
            scaled_x = int(bbox_dict['x'] * scale_x)
            scaled_y = int(bbox_dict['y'] * scale_y)
            scaled_w = int(bbox_dict['w'] * scale_x)
            scaled_h = int(bbox_dict['h'] * scale_y)

            # Validate bounds
            if scaled_y < 0 or scaled_y + scaled_h > screenshot.shape[0]:
                logger.warning(f"[PERFECT MATCH] Y bounds out of range: y={scaled_y}, h={scaled_h}, img_h={screenshot.shape[0]}")
                return MatchResult(found=False, attempt=1, bbox_detected={}, score=None, crop_bytes=b'')

            if scaled_x < 0 or scaled_x + scaled_w > screenshot.shape[1]:
                logger.warning(f"[PERFECT MATCH] X bounds out of range: x={scaled_x}, w={scaled_w}, img_w={screenshot.shape[1]}")
                return MatchResult(found=False, attempt=1, bbox_detected={}, score=None, crop_bytes=b'')

            # Extract crop
            crop = screenshot[scaled_y:scaled_y+scaled_h, scaled_x:scaled_x+scaled_w]

            if crop.size == 0:
                logger.warning("[PERFECT MATCH] Empty crop")
                return MatchResult(found=False, attempt=1, bbox_detected={}, score=None, crop_bytes=b'')

            # Score crop (use drag-specific references if use_drag=True)
            score_result = self.model_scorer.score_crop(crop, step, use_drag=use_drag)

            # Compute weighted score
            scores_dict = {
                'template': score_result.template_score,
                'ocr': score_result.ocr_score,
                'efficientnet': score_result.efficientnet_score,
                'layoutlm': score_result.layoutlm_score,
                'clip': score_result.clip_score,
                'sam': score_result.sam_score
            }
            weights_dict = self.settings.get('execution', {}).get('model_weights', {})
            weighted_score = self.model_scorer.compute_weighted_score(scores_dict, weights_dict)
            score_result.match_score = weighted_score

            threshold = self.settings.get('execution', {}).get('perfect_match_threshold', 0.90)

            # Log scores
            logger.debug(f"[PERFECT MATCH] Scores: template={score_result.template_score:.3f}, "
                        f"ocr={score_result.ocr_score:.3f}, efficientnet={score_result.efficientnet_score:.3f}, "
                        f"layoutlm={score_result.layoutlm_score:.3f}, clip={score_result.clip_score:.3f}, "
                        f"sam={score_result.sam_score:.3f}")
            logger.debug(f"[PERFECT MATCH] Weighted score={weighted_score:.3f}, threshold={threshold:.3f}")

            # Encode crop to PNG bytes
            import cv2
            _, crop_png = cv2.imencode('.png', crop)
            crop_bytes = crop_png.tobytes()

            # Check threshold
            if weighted_score >= threshold:
                logger.info(f"[PERFECT MATCH] ✓ FOUND at ({scaled_x}, {scaled_y}) with score {weighted_score:.3f}")
                return MatchResult(
                    found=True,
                    attempt=1,
                    bbox_detected={'x': scaled_x, 'y': scaled_y, 'w': scaled_w, 'h': scaled_h},
                    score=score_result,
                    crop_bytes=crop_bytes
                )
            else:
                logger.info(f"[PERFECT MATCH] ✗ Score {weighted_score:.3f} below threshold {threshold:.3f}")
                return MatchResult(
                    found=False,
                    attempt=1,
                    bbox_detected={},
                    score=score_result,
                    crop_bytes=crop_bytes
                )

        except Exception as e:
            logger.error(f"[PERFECT MATCH] Error: {e}")
            import traceback
            traceback.print_exc()
            return MatchResult(found=False, attempt=1, bbox_detected={}, score=None, crop_bytes=b'')
