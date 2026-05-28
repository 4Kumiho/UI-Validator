"""EfficientNetV2-L feature extraction."""

import logging
import numpy as np
import cv2
import torch
from torchvision import transforms

logger = logging.getLogger(__name__)


class EfficientNetGenerator:
    @staticmethod
    def extract(model, bbox_image) -> bytes:
        """Estrae feature (1280-dim) da immagine usando EfficientNetV2-L."""
        try:
            # Prepara immagine per il modello
            image_rgb = cv2.cvtColor(bbox_image, cv2.COLOR_BGR2RGB)

            # Transform per EfficientNetV2-L
            transform = transforms.Compose([
                transforms.ToPILImage(),
                transforms.Resize(456),
                transforms.CenterCrop(384),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225]
                )
            ])

            image_tensor = transform(image_rgb).unsqueeze(0)

            # GPU se disponibile
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            image_tensor = image_tensor.to(device)
            model = model.to(device)

            # Forward pass
            with torch.no_grad():
                features = model(image_tensor)

            # Converte a bytes (1280 float32 = 5120 bytes)
            features_np = features[0].cpu().numpy().astype(np.float32)
            return features_np.tobytes()
        except Exception as e:
            logger.error(f"EfficientNet error: {e}")
            raise
