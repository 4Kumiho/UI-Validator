"""CLIP feature extraction."""

import logging
import numpy as np
import cv2
import torch
from PIL import Image

logger = logging.getLogger(__name__)


class CLIPGenerator:
    @staticmethod
    def extract(clip_model, clip_preprocess, bbox_image) -> bytes:
        """Estrae feature CLIP (768-dim) da immagine."""
        try:
            # Converti BGR a RGB per PIL
            image_rgb = cv2.cvtColor(bbox_image, cv2.COLOR_BGR2RGB)
            image_pil = Image.fromarray(image_rgb)

            # Prepara con preprocess di CLIP
            image_tensor = clip_preprocess(image_pil).unsqueeze(0)

            # GPU se disponibile
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            image_tensor = image_tensor.to(device)
            clip_model = clip_model.to(device)

            # Forward pass - estrai solo feature visive
            with torch.no_grad():
                image_features = clip_model.encode_image(image_tensor)

            # Normalizza feature (standard per CLIP)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

            # Converte a bytes (768 float32 = 3072 bytes)
            features_np = image_features[0].cpu().numpy().astype(np.float32)
            return features_np.tobytes()
        except Exception as e:
            logger.error(f"CLIP error: {e}")
            raise
