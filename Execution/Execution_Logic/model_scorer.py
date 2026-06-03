"""Model scorer - computes 0-1 scores for all 6 models on a crop."""

import json
import logging
import numpy as np
import cv2
from dataclasses import dataclass
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


@dataclass
class ScoreResult:
    """Result from scoring all 6 models on a crop."""
    match_score: float
    template_score: float
    ocr_score: float
    efficientnet_score: float
    layoutlm_score: float
    clip_score: float
    sam_score: float
    ocr_text_detected: str = ""
    efficientnet_features: bytes = b''
    layoutlm_type_detected: str = ""
    layoutlm_confidence: str = "{}"
    clip_features: bytes = b''
    sam_mask: bytes = b''
    sam_contours: str = "[]"


class ModelScorer:
    """Scores a crop against reference data using 6 different models."""

    def __init__(self, ocr_model, efficientnet_model, layoutlm_model, layoutlm_processor,
                 clip_model, clip_preprocess, sam_model):
        """
        Initialize scorer with pre-loaded models.

        Args:
            ocr_model: EasyOCR model instance
            efficientnet_model: PyTorch EfficientNetV2-L model
            layoutlm_model: LayoutLMv3 model
            layoutlm_processor: LayoutLMv3 processor
            clip_model: CLIP model
            clip_preprocess: CLIP preprocess function
            sam_model: Segment Anything model
        """
        self.ocr_model = ocr_model
        self.efficientnet_model = efficientnet_model
        self.layoutlm_model = layoutlm_model
        self.layoutlm_processor = layoutlm_processor
        self.clip_model = clip_model
        self.clip_preprocess = clip_preprocess
        self.sam_model = sam_model

    def score_template(self, crop_bgr, reference_template_bytes):
        """
        Score template matching on crop.

        Args:
            crop_bgr: numpy array (BGR)
            reference_template_bytes: PNG-encoded bytes

        Returns:
            float: score in [0, 1]
        """
        if reference_template_bytes is None or len(reference_template_bytes) == 0:
            return 0.0

        try:
            template = cv2.imdecode(np.frombuffer(reference_template_bytes, np.uint8), cv2.IMREAD_COLOR)
            if template is None:
                return 0.0

            # Resize crop to template dimensions if needed
            if crop_bgr.shape != template.shape:
                crop_resized = cv2.resize(crop_bgr, (template.shape[1], template.shape[0]))
            else:
                crop_resized = crop_bgr

            # Normalized cross-correlation template matching
            result = cv2.matchTemplate(crop_resized, template, cv2.TM_CCOEFF_NORMED)
            if result.size == 0:
                return 0.0

            score = float(np.max(result))
            score = max(0.0, min(1.0, score))  # Clamp to [0, 1]
            return score

        except Exception as e:
            logger.warning(f"Template scoring failed: {e}")
            return 0.0

    def score_ocr(self, crop_bgr, reference_ocr_text):
        """
        Score OCR text matching.

        Args:
            crop_bgr: numpy array (BGR)
            reference_ocr_text: string or None

        Returns:
            tuple (score, detected_text)
        """
        if reference_ocr_text is None or reference_ocr_text.strip() == "":
            return 0.0, ""

        try:
            from Designer.Designer_Logic.ocr_generator import OCRGenerator
            detected_text = OCRGenerator.extract(self.ocr_model, crop_bgr)

            if not detected_text:
                return 0.0, ""

            # String similarity ratio
            score = SequenceMatcher(None, detected_text.lower(), reference_ocr_text.lower()).ratio()
            return score, detected_text

        except Exception as e:
            logger.warning(f"OCR scoring failed: {e}")
            return 0.0, ""

    def score_efficientnet(self, crop_bgr, reference_features_bytes):
        """
        Score EfficientNet feature matching.

        Args:
            crop_bgr: numpy array (BGR)
            reference_features_bytes: 5120 bytes (1280 × float32) or None

        Returns:
            tuple (score, detected_features)
        """
        if reference_features_bytes is None or len(reference_features_bytes) == 0:
            return 0.0, b''

        try:
            from Designer.Designer_Logic.efficientnet_generator import EfficientNetGenerator
            detected_features_bytes = EfficientNetGenerator.extract(self.efficientnet_model, crop_bgr)

            if not detected_features_bytes:
                return 0.0, b''

            # Cosine similarity
            ref_features = np.frombuffer(reference_features_bytes, dtype=np.float32)
            det_features = np.frombuffer(detected_features_bytes, dtype=np.float32)

            if len(ref_features) != len(det_features):
                return 0.0, detected_features_bytes

            norm_ref = np.linalg.norm(ref_features)
            norm_det = np.linalg.norm(det_features)
            if norm_ref == 0 or norm_det == 0:
                return 0.0, detected_features_bytes

            score = float(np.dot(ref_features, det_features) / (norm_ref * norm_det + 1e-8))
            score = max(0.0, min(1.0, score))
            return score, detected_features_bytes

        except Exception as e:
            logger.warning(f"EfficientNet scoring failed: {e}")
            return 0.0, b''

    def score_layoutlm(self, crop_bgr, reference_layoutlm_type, reference_ocr_text):
        """
        Score LayoutLM element type matching.

        Args:
            crop_bgr: numpy array (BGR)
            reference_layoutlm_type: string or None (e.g., 'button', 'input', etc.)
            reference_ocr_text: string for OCR context

        Returns:
            tuple (score, detected_type, detected_confidence_json)
        """
        if reference_layoutlm_type is None or reference_layoutlm_type.strip() == "":
            return 0.0, "", "{}"

        try:
            from Designer.Designer_Logic.layoutlm_generator import LayoutLMGenerator
            detected_type, confidence_json = LayoutLMGenerator.extract(
                self.layoutlm_model,
                self.layoutlm_processor,
                crop_bgr,
                reference_ocr_text,
                self.ocr_model
            )

            # If types match exactly
            if detected_type and detected_type.lower() == reference_layoutlm_type.lower():
                return 1.0, detected_type, confidence_json

            # Otherwise, extract confidence score for reference type from confidence_json
            try:
                conf_data = json.loads(confidence_json) if confidence_json else {}
                score = conf_data.get(reference_layoutlm_type, 0.0)
                score = max(0.0, min(1.0, float(score)))
            except (json.JSONDecodeError, ValueError, TypeError):
                score = 0.0

            return score, detected_type, confidence_json

        except Exception as e:
            logger.warning(f"LayoutLM scoring failed: {e}")
            return 0.0, "", "{}"

    def score_clip(self, crop_bgr, reference_clip_features_bytes):
        """
        Score CLIP multimodal feature matching.

        Args:
            crop_bgr: numpy array (BGR)
            reference_clip_features_bytes: 3072 bytes (768 × float32) or None

        Returns:
            tuple (score, detected_features)
        """
        if reference_clip_features_bytes is None or len(reference_clip_features_bytes) == 0:
            return 0.0, b''

        try:
            from Designer.Designer_Logic.clip_generator import CLIPGenerator
            detected_features_bytes = CLIPGenerator.extract(self.clip_model, self.clip_preprocess, crop_bgr)

            if not detected_features_bytes:
                return 0.0, b''

            # Cosine similarity
            ref_features = np.frombuffer(reference_clip_features_bytes, dtype=np.float32)
            det_features = np.frombuffer(detected_features_bytes, dtype=np.float32)

            if len(ref_features) != len(det_features):
                return 0.0, detected_features_bytes

            norm_ref = np.linalg.norm(ref_features)
            norm_det = np.linalg.norm(det_features)
            if norm_ref == 0 or norm_det == 0:
                return 0.0, detected_features_bytes

            score = float(np.dot(ref_features, det_features) / (norm_ref * norm_det + 1e-8))
            score = max(0.0, min(1.0, score))
            return score, detected_features_bytes

        except Exception as e:
            logger.warning(f"CLIP scoring failed: {e}")
            return 0.0, b''

    def score_sam(self, crop_bgr, reference_sam_contours_json, click_x, click_y):
        """
        Score SAM segmentation contour matching.

        Args:
            crop_bgr: numpy array (BGR)
            reference_sam_contours_json: JSON string with contour points or None
            click_x: int (relative to crop)
            click_y: int (relative to crop)

        Returns:
            tuple (score, detected_mask_bytes, detected_contours_json)
        """
        if reference_sam_contours_json is None or reference_sam_contours_json.strip() in ["", "[]"]:
            return 0.0, b'', "[]"

        try:
            from Designer.Designer_Logic.sam_generator import SAMGenerator
            mask_bytes, contours_json = SAMGenerator.extract(self.sam_model, crop_bgr, click_x, click_y)

            if not mask_bytes:
                return 0.0, b'', "[]"

            # Shape-based similarity using cv2.matchShapes
            try:
                # Decode masks to contours
                mask_array = cv2.imdecode(np.frombuffer(mask_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
                if mask_array is None:
                    return 0.0, mask_bytes, contours_json

                det_contours, _ = cv2.findContours(mask_array, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if not det_contours:
                    return 0.0, mask_bytes, contours_json

                # Parse reference contours
                try:
                    ref_contour_list = json.loads(reference_sam_contours_json)
                    if ref_contour_list:
                        ref_contour = np.array(ref_contour_list, dtype=np.float32)
                        # Shape matching score: lower is better, convert to similarity (1 - normalized_score)
                        shape_distance = cv2.matchShapes(ref_contour, det_contours[0], cv2.CONTOURS_MATCH_I3, 0)
                        # Normalize: typical distances range 0-1, above that clip to 1
                        normalized_distance = min(1.0, shape_distance)
                        score = 1.0 - normalized_distance
                    else:
                        score = 0.0
                except (json.JSONDecodeError, ValueError, TypeError):
                    score = 0.0

            except Exception as shape_e:
                logger.debug(f"SAM shape matching fallback: {shape_e}")
                score = 0.0

            return score, mask_bytes, contours_json

        except Exception as e:
            logger.warning(f"SAM scoring failed: {e}")
            return 0.0, b'', "[]"

    def compute_weighted_score(self, scores_dict, weights_dict):
        """
        Compute weighted composite score, normalizing weights for active models.

        Args:
            scores_dict: {'template': 0.9, 'ocr': 0.0, ...} where 0.0 means model was skipped
            weights_dict: {'template': 0.167, 'ocr': 0.167, ...}

        Returns:
            float: weighted composite score in [0, 1]
        """
        active_models = []
        active_weight_sum = 0.0
        weighted_sum = 0.0

        for model_name, score in scores_dict.items():
            if score > 0.0 or (model_name in scores_dict and scores_dict.get(model_name, 0.0) >= 0.0):
                # Include model if it has a non-zero score or if it was calculated
                weight = weights_dict.get(model_name, 0.0)
                active_models.append((model_name, score, weight))
                active_weight_sum += weight
                weighted_sum += score * weight

        if active_weight_sum == 0.0:
            return 0.0

        composite_score = weighted_sum / active_weight_sum
        return max(0.0, min(1.0, composite_score))

    def _get_field_name(self, base_name: str, use_drag: bool = False) -> str:
        """Get the field name for a reference (e.g., BBox_OCR_text or BBox_drag_OCR_text)."""
        if use_drag:
            return f"BBox_drag_{base_name}"
        return f"BBox_{base_name}"

    def score_crop(self, crop_bgr, designer_step, use_drag=False):
        """
        Score a crop against all reference data from a designer step.

        Args:
            crop_bgr: numpy array (BGR)
            designer_step: DesignerStep object
            use_drag: bool - if True, use BBox_drag_* fields instead of BBox_*

        Returns:
            ScoreResult with all scores and detected data
        """
        # Extract reference data (use drag-specific fields if use_drag=True)
        ref_template_bytes = getattr(designer_step, self._get_field_name('Template', use_drag), None)
        ref_ocr_text = getattr(designer_step, self._get_field_name('OCR_text', use_drag), None)
        ref_efficientnet_features = getattr(designer_step, self._get_field_name('EfficientNet_Features', use_drag), None)
        ref_layoutlm_type = getattr(designer_step, self._get_field_name('LayoutLM_Type', use_drag), None)
        ref_clip_features = getattr(designer_step, self._get_field_name('CLIP_Features', use_drag), None)
        ref_sam_contours = getattr(designer_step, self._get_field_name('SAM_Contours', use_drag), None)

        # Get click point for SAM
        click_x, click_y = 0, 0
        rel_coords_field = self._get_field_name('rel_coordinates', use_drag)
        rel_coords_str = getattr(designer_step, rel_coords_field, None)
        if rel_coords_str:
            try:
                rel_coords = json.loads(rel_coords_str)
                click_x = int(rel_coords.get('x', 0))
                click_y = int(rel_coords.get('y', 0))
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        # Score all models
        template_score = self.score_template(crop_bgr, ref_template_bytes)
        ocr_score, ocr_text = self.score_ocr(crop_bgr, ref_ocr_text)
        efficientnet_score, efficientnet_features = self.score_efficientnet(crop_bgr, ref_efficientnet_features)
        layoutlm_score, layoutlm_type, layoutlm_confidence = self.score_layoutlm(
            crop_bgr, ref_layoutlm_type, ref_ocr_text
        )
        clip_score, clip_features = self.score_clip(crop_bgr, ref_clip_features)
        sam_score, sam_mask, sam_contours = self.score_sam(crop_bgr, ref_sam_contours, click_x, click_y)

        # Compute weighted score
        scores_dict = {
            'template': template_score,
            'ocr': ocr_score,
            'efficientnet': efficientnet_score,
            'layoutlm': layoutlm_score,
            'clip': clip_score,
            'sam': sam_score
        }
        # Weights will be passed from settings at matching time
        # For now, just return all scores

        return ScoreResult(
            match_score=0.0,  # Will be computed by matcher with weights from settings
            template_score=template_score,
            ocr_score=ocr_score,
            efficientnet_score=efficientnet_score,
            layoutlm_score=layoutlm_score,
            clip_score=clip_score,
            sam_score=sam_score,
            ocr_text_detected=ocr_text,
            efficientnet_features=efficientnet_features,
            layoutlm_type_detected=layoutlm_type,
            layoutlm_confidence=layoutlm_confidence,
            clip_features=clip_features,
            sam_mask=sam_mask,
            sam_contours=sam_contours
        )
