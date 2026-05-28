"""OCR via PaddleOCR."""

import logging

logger = logging.getLogger(__name__)


class OCRGenerator:
    @staticmethod
    def extract(ocr_model, bbox_image) -> str:
        """Estrae testo da immagine usando PaddleOCR."""
        try:
            logger.debug("[OCR] Extracting text with PaddleOCR")
            result = ocr_model.ocr(bbox_image, cls=True)

            # PaddleOCR returns: [[[x1,y1], [x2,y2], [x3,y3], [x4,y4]], (text, confidence)], ...]
            if not result or not result[0]:
                logger.debug("[OCR] No text detected")
                return ""

            texts = []
            for line in result:
                for detection in line:
                    if detection and len(detection) >= 2:
                        text_info = detection[1]
                        text = text_info[0] if isinstance(text_info, tuple) else text_info
                        texts.append(text)

            combined_text = " ".join(texts).strip()
            logger.debug(f"[OCR] Extracted {len(combined_text)} chars")
            return combined_text
        except Exception as e:
            logger.error(f"[OCR] Extract error: {e}")
            import traceback
            logger.debug(f"[OCR] Traceback: {traceback.format_exc()}")
            return ""
