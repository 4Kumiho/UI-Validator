"""Screenshot capture."""

import cv2
import numpy as np
from PIL import ImageGrab


class ScreenshotHandler:
    def __init__(self, monitor_info=None):
        """
        monitor_info: dict con left, top, width, height (da mss)
                     Se None, cattura lo schermo primario
        """
        self.monitor_info = monitor_info

    def capture_full_screen(self) -> np.ndarray:
        """Cattura screenshot full-screen come BGR numpy array."""
        if self.monitor_info:
            try:
                from mss import mss
                with mss() as sct:
                    screenshot = sct.grab(self.monitor_info)
                    h, w = screenshot.height, screenshot.width
                    img_rgb = np.frombuffer(screenshot.rgb, dtype=np.uint8).reshape((h, w, 3))
                    img_bgr = img_rgb[:, :, ::-1]
                    return img_bgr
            except Exception:
                img = ImageGrab.grab()
                return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        else:
            img = ImageGrab.grab()
            return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
