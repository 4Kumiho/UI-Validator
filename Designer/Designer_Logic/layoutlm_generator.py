"""LayoutLMv3 token classification for UI element type."""

import logging
import numpy as np
import cv2
import torch
from PIL import Image

logger = logging.getLogger(__name__)


class LayoutLMGenerator:
    @staticmethod
    def extract(model, processor, bbox_image) -> tuple:
        """Classifica il tipo di elemento UI e confidenza usando LayoutLMv3."""
        try:
            # Converti BGR a RGB per PIL
            image_rgb = cv2.cvtColor(bbox_image, cv2.COLOR_BGR2RGB)
            image_pil = Image.fromarray(image_rgb)

            # Prepara input con processor LayoutLMv3
            encoding = processor(image_pil, return_tensors="pt")

            # GPU se disponibile
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            for key in encoding:
                encoding[key] = encoding[key].to(device)
            model = model.to(device)

            # Forward pass
            with torch.no_grad():
                outputs = model(**encoding)
                logits = outputs.logits

            # Estrai classe predetta e confidenza
            # Media dei logit per tutti i token (tranne CLS e SEP)
            mean_logits = logits[0, 1:-1].mean(dim=0)
            class_id = mean_logits.argmax(dim=-1).item()

            # Confidenza come softmax del logit medio
            probs = torch.softmax(mean_logits, dim=-1)
            confidence = probs[class_id].item()

            # Mappa class_id a nome tipo
            element_types = ["O", "B-HEADER", "B-QUESTION", "B-INSTRUCTION",
                           "B-ANSWER", "B-OTHERS", "B-PAGE-FOOTER", "B-PAGE-HEADER",
                           "B-SIGNATURE", "B-PICTURE", "B-CAPTION"]
            element_type = element_types[class_id] if class_id < len(element_types) else "O"

            logger.debug(f"[LayoutLM] Detected type={element_type}, confidence={confidence:.2f}")
            return element_type, confidence

        except Exception as e:
            logger.error(f"[LayoutLM] Error: {e}")
            return "O", 0.0
