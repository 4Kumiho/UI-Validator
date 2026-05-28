import os
import sys
import shutil
from kivy.uix.screenmanager import Screen
from kivy.properties import NumericProperty, StringProperty
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.clock import Clock
from threading import Thread
import json

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Models.model_registry import set_model

Builder.load_file(os.path.join(os.path.dirname(__file__), "loading_screen.kv"))

# Marker files for individual models
MODELS_CACHE_DIR = os.path.normpath(os.path.expanduser("~/.cache/ui_validator"))

OCR_MARKER = os.path.join(MODELS_CACHE_DIR, "ocr_loaded.json")
EFFICIENTNET_MARKER = os.path.join(MODELS_CACHE_DIR, "efficientnet_loaded.json")
LAYOUTLM_MARKER = os.path.join(MODELS_CACHE_DIR, "layoutlm_loaded.json")
SAM_MARKER = os.path.join(MODELS_CACHE_DIR, "sam_loaded.json")
CLIP_MARKER = os.path.join(MODELS_CACHE_DIR, "clip_loaded.json")


class LoadingScreen(Screen):
    SCREEN_NAME = "loading"
    progress = NumericProperty(0)
    status_text = StringProperty("Initializing...")

    def on_enter(self):
        Thread(target=self._load_models, daemon=True).start()

    def _load_models(self):
        # TODO: Models disabled - corporate network blocks external downloads
        # Uncomment when network access is available
        """
        try:
            # Disable SSL verification for downloads (required in some network environments)
            import ssl
            ssl._create_default_https_context = ssl._create_unverified_context
            from paddleocr import PaddleOCR
            from torchvision import models as tv_models
            import warnings

            os.makedirs(MODELS_CACHE_DIR, exist_ok=True)

            # OCR Loading (PaddleOCR)
            if not os.path.exists(OCR_MARKER):
                self._smooth_progress(0.0, 0.2, "Loading PaddleOCR...", 3)
                print("[*] Loading PaddleOCR from scratch...")
                ocr = PaddleOCR(use_angle_cls=True, lang='en')
                set_model('ocr', ocr)
                print("[OK] PaddleOCR loaded and registered")
                with open(OCR_MARKER, 'w') as f:
                    json.dump({'loaded': True}, f)
            else:
                print("[OK] PaddleOCR cached")
                self._smooth_progress(0.0, 0.2, "PaddleOCR cached", 0.4)
                ocr = PaddleOCR(use_angle_cls=True, lang='en')
                set_model('ocr', ocr)

            # EfficientNetV2-L Loading (superior accuracy)
            if not os.path.exists(EFFICIENTNET_MARKER):
                self._smooth_progress(0.2, 0.4, "Loading EfficientNetV2...", 5)
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore")
                    efficientnet_model = tv_models.efficientnet_v2_l(weights=tv_models.EfficientNet_V2_L_Weights.DEFAULT)
                set_model('efficientnet', efficientnet_model)
                print("[OK] EfficientNetV2-L loaded")
                with open(EFFICIENTNET_MARKER, 'w') as f:
                    json.dump({'loaded': True}, f)
            else:
                print("[OK] EfficientNetV2-L cached")
                self._smooth_progress(0.2, 0.4, "EfficientNetV2 cached", 0.4)
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore")
                    efficientnet_model = tv_models.efficientnet_v2_l(weights=tv_models.EfficientNet_V2_L_Weights.DEFAULT)
                set_model('efficientnet', efficientnet_model)

            # LayoutLMv3 Loading (UI Layout Understanding)
            if not os.path.exists(LAYOUTLM_MARKER):
                self._smooth_progress(0.4, 0.6, "Loading LayoutLMv3...", 5)
                print("[*] Loading LayoutLMv3 from HuggingFace...")
                from transformers import AutoProcessor, AutoModelForTokenClassification
                processor = AutoProcessor.from_pretrained("microsoft/layoutlmv3-base")
                model = AutoModelForTokenClassification.from_pretrained("microsoft/layoutlmv3-base")
                set_model('layoutlm', (model, processor))
                print("[OK] LayoutLMv3 loaded")
                with open(LAYOUTLM_MARKER, 'w') as f:
                    json.dump({'loaded': True}, f)
            else:
                print("[OK] LayoutLMv3 cached")
                self._smooth_progress(0.4, 0.6, "LayoutLMv3 cached", 0.4)
                from transformers import AutoProcessor, AutoModelForTokenClassification
                processor = AutoProcessor.from_pretrained("microsoft/layoutlmv3-base")
                model = AutoModelForTokenClassification.from_pretrained("microsoft/layoutlmv3-base")
                set_model('layoutlm', (model, processor))

            # SAM Loading (Segment Anything - precise edge and corner detection)
            if not os.path.exists(SAM_MARKER):
                self._smooth_progress(0.6, 0.8, "Loading SAM...", 8)
                print("[*] Loading SAM from scratch...")
                from segment_anything import sam_model_registry, SamPredictor
                sam = sam_model_registry["vit_l"](checkpoint=None)
                sam_predictor = SamPredictor(sam)
                set_model('sam', sam_predictor)
                print("[OK] SAM loaded and registered")
                with open(SAM_MARKER, 'w') as f:
                    json.dump({'loaded': True}, f)
            else:
                print("[OK] SAM cached")
                self._smooth_progress(0.6, 0.8, "SAM cached", 0.4)
                from segment_anything import sam_model_registry, SamPredictor
                sam = sam_model_registry["vit_l"](checkpoint=None)
                sam_predictor = SamPredictor(sam)
                set_model('sam', sam_predictor)

            # CLIP Loading (ViT-L/14@336px - MAXIMUM semantic understanding available)
            if not os.path.exists(CLIP_MARKER):
                self._smooth_progress(0.8, 1.0, "Loading CLIP...", 6)
                import clip
                clip_model, clip_preprocess = clip.load("ViT-L/14@336px", device="cpu")
                set_model('clip', (clip_model, clip_preprocess))
                print("[OK] CLIP (ViT-L/14@336px) loaded")
                with open(CLIP_MARKER, 'w') as f:
                    json.dump({'loaded': True}, f)
            else:
                print("[OK] CLIP (ViT-L/14@336px) cached")
                self._smooth_progress(0.8, 1.0, "CLIP cached", 0.4)
                import clip
                clip_model, clip_preprocess = clip.load("ViT-L/14@336px", device="cpu")
                set_model('clip', (clip_model, clip_preprocess))

            self._update(1.0, "Ready!")
            Clock.schedule_once(lambda dt: self._transition_to_menu(), 0.3)

        except Exception as e:
            import traceback
            error_msg = f"Error: {str(e)}"
            print(f"\n{'='*60}")
            print(f"LOADING ERROR: {error_msg}")
            print(f"{'='*60}")
            traceback.print_exc()
            print(f"{'='*60}\n")
            self._update(1.0, error_msg)
            Clock.schedule_once(lambda dt: self._transition_to_menu(), 3.0)
        """
        # Go directly to menu
        self._update(1.0, "Ready!")
        Clock.schedule_once(lambda dt: self._transition_to_menu(), 0.3)

    def _update(self, value, text):
        Clock.schedule_once(lambda dt: self._apply(value, text))

    def _apply(self, value, text):
        self.progress = value
        self.status_text = text

    def _smooth_progress(self, start, end, text, duration_seconds):
        """Smoothly animate progress bar from start to end over duration_seconds"""
        import time
        steps = int(duration_seconds * 10)  # 10 updates per second
        step_size = (end - start) / max(steps, 1)
        step_delay = duration_seconds / max(steps, 1)

        for i in range(steps + 1):
            current = start + (step_size * i)
            self._update(min(current, end), text)
            time.sleep(step_delay)

    def _transition_to_menu(self):
        if self.manager:
            self.manager.current = "menu"
