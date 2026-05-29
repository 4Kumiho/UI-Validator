"""Smart BBox generation - OCR + SAM merge (multi-stage)."""

import numpy as np
import logging

logger = logging.getLogger(__name__)


class BBoxGenerator:
    @staticmethod
    def generate_smart_bbox_with_ai(screenshot: np.ndarray, click_x: int, click_y: int,
                                    ocr_model=None, sam_model=None) -> dict:
        """
        Multi-stage bbox generation:
        1. OCR text localization (finds text/name)
        2. SAM element detection (finds visual element/icon)
        3. MERGE both bbox (includes both icon and text)
        4. Fallback to default bbox
        """
        ocr_bbox = None
        ocr_text = None

        # Stage 1: EasyOCR text localization
        if ocr_model:
            logger.debug("[OCR] Searching for text elements...")
            try:
                ocr_results = ocr_model.readtext(screenshot)
                if ocr_results:
                    for bbox_points, text, confidence in ocr_results:
                        x_coords = [p[0] for p in bbox_points]
                        y_coords = [p[1] for p in bbox_points]
                        x_min, x_max = int(min(x_coords)), int(max(x_coords))
                        y_min, y_max = int(min(y_coords)), int(max(y_coords))

                        # Check if click is inside text bbox
                        if x_min <= click_x <= x_max and y_min <= click_y <= y_max:
                            w = x_max - x_min
                            h = y_max - y_min
                            if w * h > 0:
                                ocr_bbox = {"x": x_min, "y": y_min, "w": w, "h": h}
                                ocr_text = text
                                logger.info(f"[OCR] Found text '{text}' at click position")
                                break
            except Exception as e:
                logger.debug(f"[OCR] Error: {e}")

        # Stage 2: SAM element visual detection (refine with icon/visual element)
        sam_bbox = None
        if sam_model and ocr_bbox:
            logger.debug("[SAM] Refining bbox with visual element detection...")
            try:
                # Use SAM to find precise boundaries of visual element
                from segment_anything import SamPredictor
                if isinstance(sam_model, SamPredictor):
                    sam_model.set_image(screenshot)

                    # Create prompt points from click location
                    points = np.array([[click_x, click_y]])
                    labels = np.array([1])  # 1 = foreground point

                    masks, scores, logits = sam_model.predict(
                        point_coords=points,
                        point_labels=labels,
                        multimask_output=False
                    )

                    if masks is not None and len(masks) > 0:
                        mask = masks[0]
                        y_indices, x_indices = np.where(mask)
                        if len(y_indices) > 0:
                            sam_bbox = {
                                "x": int(np.min(x_indices)),
                                "y": int(np.min(y_indices)),
                                "w": int(np.max(x_indices) - np.min(x_indices)),
                                "h": int(np.max(y_indices) - np.min(y_indices))
                            }
                            logger.info(f"[SAM] Detected visual element")
            except Exception as e:
                logger.debug(f"[SAM] Error: {e}")

        # Stage 3: MERGE OCR text + SAM visual element
        if ocr_bbox and sam_bbox:
            merged = BBoxGenerator._merge_bboxes(ocr_bbox, sam_bbox)
            logger.info(f"[BBOX] Merged OCR + SAM: icon + '{ocr_text}'")
            return merged
        elif ocr_bbox:
            logger.info(f"[BBOX] Using OCR bbox: '{ocr_text}'")
            return ocr_bbox

        # Stage 4: Fallback to default bbox (100x100 square around click)
        logger.debug("[BBOX] No AI candidates, using default 100x100 square")
        h, w = screenshot.shape[:2]
        size = 50  # 50px on each side = 100x100 total

        # Center on click, constrained to screen bounds
        x = max(0, min(click_x - size, w - (size * 2)))
        y = max(0, min(click_y - size, h - (size * 2)))
        bbox_w = size * 2
        bbox_h = size * 2

        return {
            "x": int(x),
            "y": int(y),
            "w": int(bbox_w),
            "h": int(bbox_h)
        }

    @staticmethod
    def _merge_bboxes(bbox1: dict, bbox2: dict) -> dict:
        """Merge two bboxes by taking the outer boundary of both."""
        x1_min = bbox1["x"]
        y1_min = bbox1["y"]
        x1_max = bbox1["x"] + bbox1["w"]
        y1_max = bbox1["y"] + bbox1["h"]

        x2_min = bbox2["x"]
        y2_min = bbox2["y"]
        x2_max = bbox2["x"] + bbox2["w"]
        y2_max = bbox2["y"] + bbox2["h"]

        # Outer boundary
        x_min = min(x1_min, x2_min)
        y_min = min(y1_min, y2_min)
        x_max = max(x1_max, x2_max)
        y_max = max(y1_max, y2_max)

        return {
            "x": int(x_min),
            "y": int(y_min),
            "w": int(x_max - x_min),
            "h": int(y_max - y_min)
        }

    @staticmethod
    def crop_image(screenshot: np.ndarray, bbox: dict) -> np.ndarray:
        """Ritorna il crop dell'immagine secondo il bbox."""
        x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
        return screenshot[y:y+h, x:x+w]
