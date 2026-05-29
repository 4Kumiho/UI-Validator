"""LayoutLMv3 token classification for UI element type."""

import logging
import json
import numpy as np
import cv2
import torch
from PIL import Image

logger = logging.getLogger(__name__)


class LayoutLMGenerator:
    # Map FUNSD document-understanding labels to UI element types
    FUNSD_TO_UI = {
        "O": "other",
        "B-HEADER": "header",
        "B-QUESTION": "label",
        "B-ANSWER": "input",
        "B-INSTRUCTION": "text",
        "B-OTHERS": "other",
        "B-PAGE-FOOTER": "footer",
        "B-PAGE-HEADER": "header",
        "B-SIGNATURE": "button",
        "B-PICTURE": "image",
        "B-CAPTION": "text",
    }

    FUNSD_LABELS = ["O", "B-HEADER", "B-QUESTION", "B-INSTRUCTION",
                    "B-ANSWER", "B-OTHERS", "B-PAGE-FOOTER", "B-PAGE-HEADER",
                    "B-SIGNATURE", "B-PICTURE", "B-CAPTION"]

    @staticmethod
    def extract(model, processor, bbox_image, ocr_text="", ocr_model=None) -> tuple:
        """Classifica il tipo di elemento UI e ritorna confidenza JSON con score per ogni tipo."""
        # If model not loaded, return default
        if model is None or processor is None:
            logger.debug("[LayoutLM] Model not loaded, returning default")
            return "other", json.dumps({})

        try:
            # Converti BGR a RGB per PIL
            image_rgb = cv2.cvtColor(bbox_image, cv2.COLOR_BGR2RGB)
            image_pil = Image.fromarray(image_rgb)

            # Extract text and bounding boxes from image using EasyOCR if available
            words = []
            boxes = []

            if ocr_model is not None:
                try:
                    results = ocr_model.readtext(bbox_image)
                    h, w = bbox_image.shape[:2]
                    box_size = 100
                    row = 0
                    col = 0
                    max_cols = w // box_size

                    for bbox_points, text, confidence in results:
                        if text and text.strip():
                            words.append(text)

                            # Generate 100x100 square boxes in grid layout
                            x_min = col * box_size
                            y_min = row * box_size
                            x_max = x_min + box_size
                            y_max = y_min + box_size

                            # Clamp to image bounds
                            x_min = max(0, min(x_min, w - box_size))
                            y_min = max(0, min(y_min, h - box_size))
                            x_max = min(w, x_max)
                            y_max = min(h, y_max)

                            boxes.append([x_min, y_min, x_max, y_max])

                            # Move to next grid position
                            col += 1
                            if col >= max_cols:
                                col = 0
                                row += 1
                except:
                    pass

            # Fallback: use provided ocr_text if no words were extracted
            if not words and ocr_text.strip():
                words = ocr_text.split()
                # Create dummy boxes for words (approximate positions)
                h, w = bbox_image.shape[:2]
                boxes = [[0, 0, w, h] for _ in words]

            # If still no words, return default (no text to classify)
            if not words:
                logger.debug("[LayoutLM] No text detected, returning default")
                return "other", json.dumps({})

            # Prepara input con processor LayoutLMv3
            # Pass image, text, and boxes to processor
            encoding = processor(image_pil, text=words, boxes=boxes,
                               return_tensors="pt", truncation=True)

            # GPU se disponibile
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            for key in encoding:
                encoding[key] = encoding[key].to(device)
            model = model.to(device)

            # Forward pass
            with torch.no_grad():
                outputs = model(**encoding)
                logits = outputs.logits

            # Estrai classe predetta
            # logits ha shape [batch_size, num_tokens, num_labels] = [1, num_tokens, 2]
            # Media dei logit per tutti i token (tranne CLS e SEP) se disponibili
            token_logits = logits[0]  # shape: [num_tokens, num_labels]

            if token_logits.shape[0] > 2:
                # Multi-token: average the logits
                mean_logits = token_logits[1:-1].mean(dim=0)
            else:
                # Single or few tokens: use the first meaningful token
                mean_logits = token_logits[0] if token_logits.shape[0] > 0 else token_logits[0]

            class_id = mean_logits.argmax(dim=-1).item()

            # Probabilità per ogni classe
            probs = torch.softmax(mean_logits, dim=-1)

            # Usa solo le classi disponibili nel modello
            num_classes = probs.shape[-1]

            # Mappa class_id a nome tipo UI
            # Per classificazione binaria (2 classi): 0=other, 1=element
            if num_classes == 2:
                element_type = "element" if class_id == 1 else "other"
            else:
                funsd_label = LayoutLMGenerator.FUNSD_LABELS[class_id] if class_id < len(LayoutLMGenerator.FUNSD_LABELS) else "O"
                element_type = LayoutLMGenerator.FUNSD_TO_UI.get(funsd_label, "other")

            # Confidence come JSON con score per ogni tipo disponibile
            confidence_dict = {}
            for i in range(num_classes):
                if i < len(LayoutLMGenerator.FUNSD_LABELS):
                    label = LayoutLMGenerator.FUNSD_LABELS[i]
                    ui_type = LayoutLMGenerator.FUNSD_TO_UI.get(label, "other")
                else:
                    ui_type = f"class_{i}"
                confidence_dict[ui_type] = round(probs[i].item(), 4)

            confidence_json = json.dumps(confidence_dict)

            logger.debug(f"[LayoutLM] Detected type={element_type}, scores={confidence_dict}")
            return element_type, confidence_json

        except Exception as e:
            logger.error(f"[LayoutLM] Error: {e}")
            return "other", json.dumps({})
