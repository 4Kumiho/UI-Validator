"""BBox generation - 100x100 square centered at click."""

import numpy as np
import logging

logger = logging.getLogger(__name__)


class BBoxGenerator:
    @staticmethod
    def generate_bbox(screenshot: np.ndarray, click_x: int, click_y: int) -> dict:
        """Generate a fixed 100x100 square bbox centered at click, clamped to screen."""
        h, w = screenshot.shape[:2]
        box_size = 100

        # Create 100x100 square box centered at click
        x_min = click_x - box_size // 2
        y_min = click_y - box_size // 2
        x_max = x_min + box_size
        y_max = y_min + box_size

        # Clamp to image bounds while maintaining 100x100 size
        if x_min < 0:
            x_min = 0
            x_max = box_size
        elif x_max > w:
            x_max = w
            x_min = max(0, w - box_size)

        if y_min < 0:
            y_min = 0
            y_max = box_size
        elif y_max > h:
            y_max = h
            y_min = max(0, h - box_size)

        logger.info(f"[BBOX] Generated 100x100 square at ({x_min}, {y_min})")
        return {
            "x": x_min,
            "y": y_min,
            "w": x_max - x_min,
            "h": y_max - y_min
        }

    @staticmethod
    def crop_image(screenshot: np.ndarray, bbox: dict) -> np.ndarray:
        """Ritorna il crop dell'immagine secondo il bbox."""
        x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
        return screenshot[y:y+h, x:x+w]
