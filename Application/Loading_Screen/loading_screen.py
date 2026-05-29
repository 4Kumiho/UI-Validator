import os
import sys
import shutil
from kivy.uix.screenmanager import Screen
from kivy.properties import NumericProperty, StringProperty
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.clock import Clock
from threading import Thread
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Models.model_registry import set_model

Builder.load_file(os.path.join(os.path.dirname(__file__), "loading_screen.kv"))

MODELS_DIR = Path(__file__).parent.parent.parent / "Models"
MODELS_DIR.mkdir(exist_ok=True)


class LoadingScreen(Screen):
    SCREEN_NAME = "loading"
    progress = NumericProperty(0)
    status_text = StringProperty("Initializing...")

    def on_enter(self):
        Thread(target=self._load_models, daemon=True).start()

    def _setup_ssl_and_env(self):
        os.environ['TORCH_HOME'] = str(MODELS_DIR / "efficientnet")
        os.environ['HF_HOME'] = str(MODELS_DIR / "layoutlmv3")
        os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
        os.environ['REQUESTS_CA_BUNDLE'] = ''
        os.environ['CURL_CA_BUNDLE'] = ''
        os.environ['HTTPX_VERIFY'] = 'False'

        import ssl
        import urllib3
        import requests

        ssl._create_default_https_context = ssl._create_unverified_context
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        try:
            import httpx
            import inspect
            original_request = httpx.Client.request
            sig = inspect.signature(original_request)
            valid_params = set(sig.parameters.keys())

            def patched_request(self, method, url, **kwargs):
                kwargs['verify'] = False
                filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_params}
                return original_request(self, method, url, **filtered_kwargs)
            httpx.Client.request = patched_request
        except:
            pass

        try:
            import ssl as ssl_module
            def create_unverified_context(*args, **kwargs):
                return ssl_module._create_unverified_context()
            ssl_module.create_default_context = create_unverified_context
        except:
            pass

        try:
            import huggingface_hub
            huggingface_hub.configure(cache_dir=str(MODELS_DIR / "layoutlmv3"))
        except:
            pass

        original_request = requests.adapters.HTTPAdapter.send

        def send_no_timeout(self, request, *args, **kwargs):
            kwargs['timeout'] = None
            try:
                return original_request(self, request, *args, **kwargs)
            except TypeError as e:
                if 'headers' in str(e):
                    kwargs.pop('headers', None)
                    try:
                        return original_request(self, request, *args, **kwargs)
                    except TypeError:
                        kwargs.clear()
                        return original_request(self, request)
                raise
        requests.adapters.HTTPAdapter.send = send_no_timeout

    def _load_ocr(self):
        import easyocr
        easyocr_dir = str(MODELS_DIR / "easyocr")
        (MODELS_DIR / "easyocr").mkdir(exist_ok=True)
        reader = easyocr.Reader(['en'], model_storage_directory=easyocr_dir)
        set_model('ocr', reader)
        return 'ocr'

    def _load_efficientnet(self):
        import os
        from torchvision import models as tv_models
        import warnings

        # Force torch to use Models/efficientnet/ as cache
        os.environ['TORCH_HOME'] = str(MODELS_DIR / "efficientnet")

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            model = tv_models.efficientnet_v2_l(weights=tv_models.EfficientNet_V2_L_Weights.DEFAULT)
        set_model('efficientnet', model)
        return 'efficientnet'

    def _load_layoutlm(self):
        import warnings
        import urllib.request
        import ssl
        from transformers import AutoProcessor, AutoModelForTokenClassification

        layoutlm_dir = MODELS_DIR / "layoutlmv3"
        layoutlm_dir.mkdir(exist_ok=True)

        # Pre-download essential files using urllib (bypass requests/httpx issues)
        ssl._create_default_https_context = ssl._create_unverified_context
        base_url = "https://huggingface.co/microsoft/layoutlmv3-base/resolve/main/"
        files_to_download = [
            "config.json",
            "preprocessor_config.json",
            "pytorch_model.bin"
        ]

        for filename in files_to_download:
            filepath = layoutlm_dir / filename
            if not filepath.exists():
                try:
                    print(f"[DEBUG] Downloading {filename}...")
                    urllib.request.urlretrieve(base_url + filename, str(filepath))
                    print(f"[DEBUG] Downloaded {filename}")
                except Exception as e:
                    print(f"[DEBUG] Failed to download {filename}: {str(e)[:60]}")

        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore")
                processor = AutoProcessor.from_pretrained(
                    str(layoutlm_dir),
                    local_files_only=True,
                    apply_ocr=False  # Disable OCR, we use EasyOCR instead
                )
                model = AutoModelForTokenClassification.from_pretrained(
                    str(layoutlm_dir),
                    local_files_only=True,
                    num_labels=11  # FUNSD has 11 token classes
                )
            print(f"[DEBUG] LayoutLMv3 loaded with num_labels={model.config.num_labels if hasattr(model.config, 'num_labels') else 'UNKNOWN'}")
            set_model('layoutlm', (model, processor))
            return 'layoutlm'
        except Exception as e:
            set_model('layoutlm', (None, None))
            return 'layoutlm'

    def _load_sam(self):
        from segment_anything import sam_model_registry, SamPredictor

        sam_checkpoint = str(MODELS_DIR / "sam" / "sam_vit_b_01ec64.pth")
        (MODELS_DIR / "sam").mkdir(exist_ok=True)

        if not Path(sam_checkpoint).exists():
            try:
                url = "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth"
                import urllib.request
                urllib.request.urlretrieve(url, sam_checkpoint)
            except:
                pass

        if Path(sam_checkpoint).exists():
            sam = sam_model_registry["vit_b"](checkpoint=sam_checkpoint)
        else:
            sam = sam_model_registry["vit_b"](checkpoint=None)

        sam_predictor = SamPredictor(sam)
        set_model('sam', sam_predictor)
        return 'sam'

    def _load_clip(self):
        import clip
        clip_model, clip_preprocess = clip.load("ViT-L/14@336px", device="cpu")
        set_model('clip', (clip_model, clip_preprocess))
        return 'clip'

    def _load_models(self):
        try:
            self._update(0.0, "Initializing...")
            self._setup_ssl_and_env()

            self._update(0.1, "Loading models in parallel...")

            model_tasks = {
                'ocr': ('EasyOCR', self._load_ocr),
                'efficientnet': ('EfficientNetV2-L', self._load_efficientnet),
                'layoutlm': ('LayoutLMv3', self._load_layoutlm),
                'sam': ('SAM', self._load_sam),
                'clip': ('CLIP', self._load_clip),
            }

            completed = 0
            total_models = len(model_tasks)
            current_progress = [0.1]
            target_progress = [0.1]

            def smooth_progress_tick(dt):
                if current_progress[0] < target_progress[0]:
                    current_progress[0] += 0.01
                    if current_progress[0] > target_progress[0]:
                        current_progress[0] = target_progress[0]
                    self.progress = current_progress[0]

            progress_ticker = Clock.schedule_interval(smooth_progress_tick, 0.05)

            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(func): (name, display_name) for name, (display_name, func) in model_tasks.items()}

                for future in as_completed(futures):
                    completed += 1
                    model_name, display_name = futures[future]
                    try:
                        result = future.result()
                        progress = 0.1 + (completed / total_models) * 0.85
                        target_progress[0] = progress
                        self.status_text = f"Loading models... {completed}/{total_models}"
                        print(f"[OK] {display_name} loaded")
                    except Exception as e:
                        print(f"[ERROR] {display_name} failed: {str(e)[:100]}")

            progress_ticker.cancel()
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

    def _update(self, value, text):
        Clock.schedule_once(lambda dt: self._apply(value, text))

    def _apply(self, value, text):
        self.progress = value
        self.status_text = text

    def _transition_to_menu(self):
        if self.manager:
            self.manager.current = "menu"
