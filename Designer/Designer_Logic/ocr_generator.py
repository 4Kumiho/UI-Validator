"""OCR via EasyOCR."""

import logging

logger = logging.getLogger(__name__)


class OCRGenerator:
    @staticmethod
    def extract(ocr_model, bbox_image) -> str:
        """Estrae testo da immagine usando EasyOCR."""
        try:
            logger.debug("[OCR] Extracting text with EasyOCR")
            results = ocr_model.readtext(bbox_image)

            # EasyOCR returns: [([bbox_points], 'text', confidence), ...]
            if not results:
                logger.debug("[OCR] No text detected")
                return ""

            texts = []
            for bbox_points, text, confidence in results:
                if text and text.strip():
                    texts.append(text)

            combined_text = " ".join(texts).strip()
            logger.debug(f"[OCR] Extracted {len(combined_text)} chars")
            return combined_text
        except Exception as e:
            logger.error(f"[OCR] Extract error: {e}")
            import traceback
            logger.debug(f"[OCR] Traceback: {traceback.format_exc()}")
            return ""
