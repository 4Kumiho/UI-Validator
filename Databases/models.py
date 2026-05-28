"""
SQLAlchemy models for Designer, Execution, and Models databases.

Reference: See Databases.md for complete schema documentation.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, LargeBinary, DateTime, Boolean, ForeignKey, Float, CheckConstraint
from sqlalchemy.orm import declarative_base, relationship

# Separate bases for Designer and Execution databases
DesignerBase = declarative_base()
ExecutionBase = declarative_base()

# For backward compatibility
Base = ExecutionBase


class DesignerSession(DesignerBase):
    """
    Designer database table: records metadata about each recording session.

    A session represents a single recording instance where a user captures a sequence of interactions.
    Screen_resolution and Screen_zoom are critical for calculating scaling factors during execution.

    **Important**: Each Designer database contains exactly ONE session record (ID = 1).

    """
    __tablename__ = "designer_session"

    ID = Column(Integer, primary_key=True, autoincrement=True)
    Screen_resolution = Column(String, nullable=False)              # JSON: {width: 1920, height: 1080}
    Screen_zoom = Column(String, nullable=False)                    # JSON: {zoom_level: 100, unit: "percent"}
    Session_created_at = Column(DateTime, nullable=False)           # Timestamp when session was created

    __table_args__ = (
        CheckConstraint('ID = 1', name='check_single_session'),
    )


class DesignerStep(DesignerBase):
    """
    Designer database table: records user actions during the Design phase.

    Captures screenshots, BBox data, OCR text, EfficientNet features, and CLIP features for each step.
    Action types: SINGLE_CLICK, DOUBLE_CLICK, RIGHT_CLICK, INPUT, DRAG_AND_DROP, SCROLL

    Common fields (all action types):
    - ID: Primary key
    - Step_number: Sequential step identifier (1, 2, 3, ...)
    - Step_testcase: Optional user-assigned step name for test mapping
    - Action_type: Type of action performed
    - Screenshot: Full-screen PNG capture (BLOB) as numpy array bytes
    - Modifier_keys: JSON array of active modifiers (e.g., ["shift", "ctrl"], empty [] if none)

    BBox fields (all action types):
    - BBox: JSON {x, y, w, h} - absolute screen position of detected element
    - BBox_Template: PNG crop of the element for template matching
    - BBox_OCR_text: Extracted text via PaddleOCR
    - BBox_EfficientNet_Features: 1280-dim EfficientNetV2-L features (5120 bytes = 1280 × float32)
    - BBox_LayoutLM_Type: UI element type classification (button, input, text, image, etc.)
    - BBox_LayoutLM_Confidence: Confidence scores for element type classification
    - BBox_CLIP_Features: 512-dim CLIP ViT-L/14@336px features (2048 bytes = 512 × float32)
    - BBox_SAM_Mask: Segmentation mask for precise element boundaries
    - BBox_SAM_Contours: Precise edge/corner coordinates of detected element

    Click point (SINGLE_CLICK, DOUBLE_CLICK, RIGHT_CLICK, SCROLL, DRAG_AND_DROP only):
    - BBox_rel_coordinates: JSON {x, y} - click position relative to BBox origin
    - NOTE: INPUT actions do NOT have BBox_rel_coordinates (no click on input field)

    Drag-specific fields (DRAG_AND_DROP only):
    - BBox_drag: JSON {x, y, w, h} - absolute position of drag target
    - BBox_drag_Template: PNG crop of drag target
    - BBox_drag_OCR_text: Text at drag target
    - BBox_drag_EfficientNet_Features: Features at drag target
    - BBox_drag_LayoutLM_Type: UI element type for drag target
    - BBox_drag_LayoutLM_Confidence: Confidence scores for drag target type
    - BBox_drag_CLIP_Features: CLIP features at drag target
    - BBox_drag_SAM_Mask: SAM segmentation mask for drag target
    - BBox_drag_SAM_Contours: Precise edges/corners of drag target
    - BBox_drag_rel_coordinates: JSON {x, y} - relative coordinates at drag target

    Input-specific fields (INPUT only):
    - Input_text: The typed text (may include spaces and newlines)

    Scroll-specific fields (SCROLL only):
    - Scroll_DX: Horizontal scroll delta (0 for vertical scroll)
    - Scroll_DY: Vertical scroll delta (negative = up, positive = down)
    """
    __tablename__ = "designer_step"

    # Primary key
    ID = Column(Integer, primary_key=True, autoincrement=True)

    # Metadata
    Step_number = Column(Integer, nullable=False)
    Step_testcase = Column(Integer, nullable=True)

    # Action and screenshot
    Action_type = Column(String, nullable=False)
    Screenshot = Column(LargeBinary, nullable=True)
    Modifier_keys = Column(String, nullable=True)  # JSON array: ["shift", "ctrl"] (empty [] if none)

    # Main BBox (all action types)
    BBox = Column(String, nullable=True)  # JSON: {x, y, w, h}
    BBox_rel_coordinates = Column(String, nullable=True)  # JSON: {x, y} - NOT for INPUT
    BBox_Template = Column(LargeBinary, nullable=True)  # PNG crop
    BBox_OCR_text = Column(String, nullable=True)
    BBox_EfficientNet_Features = Column(LargeBinary, nullable=True)  # 5120 bytes (1280 features)
    BBox_LayoutLM_Type = Column(String, nullable=True)  # UI element type: button, input, text, image, etc.
    BBox_LayoutLM_Confidence = Column(String, nullable=True)  # Confidence scores for each type
    BBox_CLIP_Features = Column(LargeBinary, nullable=True)  # 768-dim CLIP ViT-L/14@336px feature vector (3072 bytes = 768 × float32)
    BBox_SAM_Mask = Column(LargeBinary, nullable=True)  # SAM segmentation mask (binary array)
    BBox_SAM_Contours = Column(String, nullable=True)  # JSON: [[x1,y1], [x2,y2], ...] - precise edges/corners

    # Drag end BBox (DRAG_AND_DROP only)
    BBox_drag = Column(String, nullable=True)  # JSON: {x, y, w, h}
    BBox_drag_rel_coordinates = Column(String, nullable=True)  # JSON: {x, y}
    BBox_drag_Template = Column(LargeBinary, nullable=True)  # PNG crop
    BBox_drag_OCR_text = Column(String, nullable=True)
    BBox_drag_EfficientNet_Features = Column(LargeBinary, nullable=True)  # 5120 bytes
    BBox_drag_LayoutLM_Type = Column(String, nullable=True)  # UI element type for drag target
    BBox_drag_LayoutLM_Confidence = Column(String, nullable=True)  # Confidence scores for drag target
    BBox_drag_CLIP_Features = Column(LargeBinary, nullable=True)  # 768-dim CLIP ViT-L/14@336px features (3072 bytes)
    BBox_drag_SAM_Mask = Column(LargeBinary, nullable=True)  # SAM segmentation mask for drag target
    BBox_drag_SAM_Contours = Column(String, nullable=True)  # JSON: precise edges/corners of drag target

    # Input-specific fields (INPUT only)
    Input_text = Column(String, nullable=True)
    Enter_After_Input_text = Column(Integer, nullable=True)  # 1 if user pressed Enter after text, 0 otherwise

    # Scroll-specific fields (SCROLL only)
    Scroll_DX = Column(Integer, nullable=True)
    Scroll_DY = Column(Integer, nullable=True)


class ExecutionSession(ExecutionBase):
    """
    Execution database table: records metadata about each execution session.

    An execution session represents a single automated playback of a Designer session.
    It links to the original Designer database and records the overall outcome.

    **Important**: Each Execution database contains exactly ONE session record (ID = 1).
    """
    __tablename__ = "execution_session"

    ID = Column(Integer, primary_key=True, autoincrement=True)
    Designer_Session_ID = Column(Integer, nullable=False)
    Designer_DB_path = Column(String, nullable=False)
    Execution_start_timestamp = Column(DateTime, nullable=False)
    Execution_end_timestamp = Column(DateTime, nullable=True)
    Execution_result = Column(String, nullable=True)  # PASSED, FAILED, STOPPED
    Execution_error = Column(String, nullable=True)

    __table_args__ = (
        CheckConstraint('ID = 1', name='check_single_execution_session'),
    )


class ExecutionStep(ExecutionBase):
    """
    Execution database table: records execution results after replaying Designer session.

    Stores match scores, detected positions, and video timestamps for each step.
    Compares original Designer data against what was detected during execution.

    Status & Matching:
    - Status: Result of execution (PASSED, FAILED, STOPPED, SKIPPED)
    - Matched_Attempt: Which attempt (1, 2, or 3) succeeded in matching
    - Matched_Stage: Which stage found match (1 = initial search, 2+ = retry after wait)
    - Matched_drag_Attempt: Which attempt for drag destination (DRAG_AND_DROP only)
    - Matched_drag_Stage: Which stage for drag destination (DRAG_AND_DROP only)

    Original data (from Designer):
    - BBox, BBox_Template, BBox_OCR_text, BBox_EfficientNet_Features, BBox_LayoutLM_Type, BBox_CLIP_Features, BBox_SAM_Mask, BBox_rel_coordinates

    Detected data (from Executor):
    - BBox_Exec_Detected: Actual position where element was found
    - BBox_Exec_Template_Detected: PNG crop of detected element
    - BBox_Exec_OCR_text_Detected: Text detected in matched region
    - BBox_Exec_EfficientNet_Features_Detected: Features extracted from matched region
    - BBox_Exec_LayoutLM_Type_Detected: Detected UI element type
    - BBox_Exec_CLIP_Features_Detected: CLIP features detected in matched region
    - BBox_Exec_SAM_Mask_Detected: SAM segmentation mask detected

    Match scores (SINGLE_CLICK, DOUBLE_CLICK, RIGHT_CLICK, DRAG_AND_DROP, SCROLL only):
    - BBox_Match_Score: Combined voting score (0.0–1.0)
    - BBox_Template_Score: Template matching confidence
    - BBox_OCR_Score: OCR similarity (0–1)
    - BBox_EfficientNet_Score: EfficientNet feature cosine similarity (0–1)
    - BBox_LayoutLM_Score: UI element type matching score (0–1)
    - BBox_CLIP_Score: CLIP multimodal similarity (0–1)
    - BBox_SAM_Score: SAM contour matching score (0–1)

    Special cases:
    - INPUT actions: No click coordinates (BBox_rel_coordinates is NULL); has all match scores and Matched_Attempt/Stage (element must be found via matching, then text typed)
    - SCROLL actions: Match scores reflect scrollable element, not deltas
    - DRAG_AND_DROP: Separate matched/detected data for drag target (BBox_drag_*)

    Timing:
    - Video_timestamp: Seconds in video when this step was executed
    """
    __tablename__ = "execution_step"

    # Primary key
    ID = Column(Integer, primary_key=True, autoincrement=True)

    # Metadata
    Step_number = Column(Integer, nullable=False)
    Step_testcase = Column(Integer, nullable=True)

    # Action and screenshot
    Action_type = Column(String, nullable=False)
    Screenshot = Column(LargeBinary, nullable=True)
    Modifier_keys = Column(String, nullable=True)  # JSON array: ["shift", "ctrl"] (empty [] if none)

    # Status & matching info
    Status = Column(String, nullable=True)  # PASSED, FAILED, STOPPED, SKIPPED
    Matched_Attempt = Column(Integer, nullable=True)  # 1, 2, or 3
    Matched_Stage = Column(Integer, nullable=True)  # 1, 2, 3, ...
    Matched_drag_Attempt = Column(Integer, nullable=True)  # 1, 2, or 3 (DRAG_AND_DROP only)
    Matched_drag_Stage = Column(Integer, nullable=True)  # 1, 2, 3, ... (DRAG_AND_DROP only)

    # Main BBox - Original (from Designer)
    BBox = Column(String, nullable=True)  # JSON: {x, y, w, h}
    BBox_Template = Column(LargeBinary, nullable=True)  # PNG crop
    BBox_OCR_text = Column(String, nullable=True)
    BBox_EfficientNet_Features = Column(LargeBinary, nullable=True)  # 5120 bytes
    BBox_LayoutLM_Type = Column(String, nullable=True)  # Original UI element type
    BBox_LayoutLM_Confidence = Column(String, nullable=True)  # Original confidence scores
    BBox_CLIP_Features = Column(LargeBinary, nullable=True)  # 2048 bytes
    BBox_SAM_Mask = Column(LargeBinary, nullable=True)  # SAM segmentation mask
    BBox_SAM_Contours = Column(String, nullable=True)  # JSON: precise edges
    BBox_rel_coordinates = Column(String, nullable=True)  # JSON: {x, y} - NOT for INPUT

    # Main BBox - Detected (from Executor)
    BBox_Exec_Detected = Column(String, nullable=True)  # JSON: {x, y, w, h} - actual found position
    BBox_Exec_Template_Detected = Column(LargeBinary, nullable=True)  # PNG crop of detected
    BBox_Exec_OCR_text_Detected = Column(String, nullable=True)
    BBox_Exec_EfficientNet_Features_Detected = Column(LargeBinary, nullable=True)  # 5120 bytes
    BBox_Exec_LayoutLM_Type_Detected = Column(String, nullable=True)  # Detected UI element type
    BBox_Exec_LayoutLM_Confidence_Detected = Column(String, nullable=True)  # Detected confidence scores
    BBox_Exec_CLIP_Features_Detected = Column(LargeBinary, nullable=True)  # 2048 bytes
    BBox_Exec_SAM_Mask_Detected = Column(LargeBinary, nullable=True)  # SAM mask detected
    BBox_Exec_SAM_Contours_Detected = Column(String, nullable=True)  # JSON: detected edges

    # Match scores
    BBox_Match_Score = Column(Float, nullable=True)  # 0.0–1.0
    BBox_Template_Score = Column(Float, nullable=True)  # 0.0–1.0
    BBox_OCR_Score = Column(Float, nullable=True)  # 0.0–1.0
    BBox_EfficientNet_Score = Column(Float, nullable=True)  # 0.0–1.0
    BBox_LayoutLM_Score = Column(Float, nullable=True)  # 0.0–1.0 - UI element type matching
    BBox_CLIP_Score = Column(Float, nullable=True)  # 0.0–1.0
    BBox_SAM_Score = Column(Float, nullable=True)  # 0.0–1.0 - contour matching score

    # Timing
    Video_timestamp = Column(Float, nullable=True)  # seconds

    # Drag end BBox - Original (DRAG_AND_DROP only)
    BBox_drag = Column(String, nullable=True)  # JSON: {x, y, w, h}
    BBox_drag_Template = Column(LargeBinary, nullable=True)  # PNG crop
    BBox_drag_OCR_text = Column(String, nullable=True)
    BBox_drag_EfficientNet_Features = Column(LargeBinary, nullable=True)  # 5120 bytes
    BBox_drag_LayoutLM_Type = Column(String, nullable=True)  # UI element type for drag target
    BBox_drag_LayoutLM_Confidence = Column(String, nullable=True)  # Confidence for drag target
    BBox_drag_CLIP_Features = Column(LargeBinary, nullable=True)  # 768-dim CLIP ViT-L/14@336px features (3072 bytes)
    BBox_drag_SAM_Mask = Column(LargeBinary, nullable=True)  # SAM segmentation mask for drag target
    BBox_drag_SAM_Contours = Column(String, nullable=True)  # JSON: precise edges for drag target
    BBox_drag_rel_coordinates = Column(String, nullable=True)  # JSON: {x, y}

    # Drag end BBox - Detected (DRAG_AND_DROP only)
    BBox_drag_Exec_Detected = Column(String, nullable=True)  # JSON: {x, y, w, h}
    BBox_drag_Exec_Template_Detected = Column(LargeBinary, nullable=True)  # PNG crop
    BBox_drag_Exec_OCR_text_Detected = Column(String, nullable=True)
    BBox_drag_Exec_EfficientNet_Features_Detected = Column(LargeBinary, nullable=True)  # 5120 bytes
    BBox_drag_Exec_LayoutLM_Type_Detected = Column(String, nullable=True)  # Detected type for drag
    BBox_drag_Exec_LayoutLM_Confidence_Detected = Column(String, nullable=True)  # Detected confidence for drag
    BBox_drag_Exec_CLIP_Features_Detected = Column(LargeBinary, nullable=True)  # 2048 bytes
    BBox_drag_Exec_SAM_Mask_Detected = Column(LargeBinary, nullable=True)  # SAM mask detected for drag
    BBox_drag_Exec_SAM_Contours_Detected = Column(String, nullable=True)  # JSON: detected edges for drag

    # Drag match scores (DRAG_AND_DROP only)
    BBox_drag_Match_Score = Column(Float, nullable=True)  # 0.0–1.0
    BBox_drag_Template_Score = Column(Float, nullable=True)  # 0.0–1.0
    BBox_drag_OCR_Score = Column(Float, nullable=True)  # 0.0–1.0
    BBox_drag_EfficientNet_Score = Column(Float, nullable=True)  # 0.0–1.0
    BBox_drag_LayoutLM_Score = Column(Float, nullable=True)  # 0.0–1.0 - UI element type matching for drag
    BBox_drag_CLIP_Score = Column(Float, nullable=True)  # 0.0–1.0
    BBox_drag_SAM_Score = Column(Float, nullable=True)  # 0.0–1.0 - contour matching for drag

    # Input-specific fields (INPUT only)
    Input_text = Column(String, nullable=True)
    Enter_After_Input_text = Column(Integer, nullable=True)  # 1 if user pressed Enter after text, 0 otherwise

    # Scroll-specific fields (SCROLL only)
    Scroll_DX = Column(Integer, nullable=True)
    Scroll_DY = Column(Integer, nullable=True)
