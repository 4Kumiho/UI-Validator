"""SAM (Segment Anything) mask and contour extraction."""

import logging
import json
import numpy as np
import cv2

logger = logging.getLogger(__name__)


class SAMGenerator:
    @staticmethod
    def extract(sam_model, bbox_image, click_x: int, click_y: int) -> tuple:
        """Estrae maschera e contorni da SAM usando click position."""
        try:
            sam_model.set_image(bbox_image)

            # Crea point prompt dalla posizione click (relativa al bbox)
            points = np.array([[click_x, click_y]])
            labels = np.array([1])  # 1 = foreground point

            # Predizione SAM
            masks, scores, logits = sam_model.predict(
                point_coords=points,
                point_labels=labels,
                multimask_output=False
            )

            if masks is None or len(masks) == 0:
                logger.debug("[SAM] No mask detected")
                return None, None

            mask = masks[0]
            score = scores[0]

            # Converti maschera a contorni
            mask_uint8 = (mask * 255).astype(np.uint8)
            contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Serializza contorni come JSON (coordinate punti)
            contour_list = []
            for contour in contours:
                pts = contour.squeeze().tolist()
                if isinstance(pts[0], (int, float)):
                    # Single point
                    pts = [pts]
                contour_list.append(pts)

            # Salva maschera come PNG base64
            _, mask_png = cv2.imencode('.png', mask_uint8)
            mask_bytes = mask_png.tobytes()

            contour_json = json.dumps(contour_list)

            logger.debug(f"[SAM] Extracted mask and {len(contours)} contours, score={score:.2f}")
            return mask_bytes, contour_json

        except Exception as e:
            logger.error(f"[SAM] Error: {e}")
            return None, None
