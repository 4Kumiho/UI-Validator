# Database Schema Documentation

This document describes the complete schema for Designer and Execution databases used in UI-Validator.

---

## Overview

- **Designer Database** (`designer.db`) - Records user actions during the Design phase
  - Table: `designer_session` - Metadata about the recording session
  - Table: `designer_step` - Individual user actions (clicks, inputs, drags, scrolls)

- **Execution Database** (`execution.db`) - Records results from automated playback
  - Table: `execution_session` - Metadata about the execution run
  - Table: `execution_step` - Results of each executed step with match scores

Each database contains exactly **ONE session** (ID = 1) due to CHECK constraint.

---

## Table 1: designer_session

**Purpose:** Records metadata about a single Designer recording session.

**Key Constraint:** Exactly one session per database (ID = 1)

| Column                  | Type         | Description |
|-------------------------|--------------|-------------|
| `ID`                    | Integer (PK) | Always 1 - Single session per database |
| `Screen_resolution`     | String (JSON) | Screen dimensions when recording. Format: `{"width": 1920, "height": 1080}` |
| `Screen_zoom`           | String (JSON) | Browser/app zoom level. Format: `{"zoom_level": 100, "unit": "percent"}` |
| `Session_created_at`    | DateTime     | Timestamp when recording started |

**Usage:**
- Screen resolution and zoom are critical for calculating coordinate scaling during Execution
- Example: If Designer recorded at 1920×1080 but Execution runs at 1280×720, coordinates must be scaled

---

## Table 2: designer_step

**Purpose:** Records individual user actions during Design phase (clicks, inputs, drags, scrolls).

**Step Types:** SINGLE_CLICK, DOUBLE_CLICK, RIGHT_CLICK, INPUT, DRAG_AND_DROP, SCROLL

| Column                              | Type            | Notes |
|-------------------------------------|-----------------|-------|
| **Primary Key**
| `ID`                                | Integer (PK)    | Auto-incrementing step ID |
| **Metadata**
| `Step_number`                       | Integer         | Sequential order (1, 2, 3, ...) - reordered after deletions |
| `Step_testcase`                     | Integer         | Optional user-assigned test case ID for mapping |
| **Action Data**
| `Action_type`                       | String          | Type of action performed |
| `Screenshot`                        | Binary          | Full-screen PNG capture (numpy array bytes) |
| `Modifier_keys`                     | String (JSON)   | Keyboard modifiers. Example: `["shift", "ctrl"]` or `[]` |
| **Main BBox**
| `BBox`                              | String (JSON)   | Absolute screen position. Format: `{"x": 100, "y": 50, "w": 300, "h": 40}` |
| `BBox_rel_coordinates`              | String (JSON)   | Click position relative to BBox origin. Format: `{"x": 150, "y": 20}` |
| `BBox_Template`                     | Binary          | PNG crop of detected element (for template matching) |
| `BBox_OCR_text`                     | String          | Text extracted via PaddleOCR |
| `BBox_EfficientNet_Features`        | Binary          | 1280-dim feature vector (5120 bytes = 1280 × float32) |
| `BBox_LayoutLM_Type`                | String          | UI element type: button, input, text, image, etc. |
| `BBox_LayoutLM_Confidence`          | String (JSON)   | Confidence scores for each element type |
| `BBox_CLIP_Features`                | Binary          | 512-dim feature vector (2048 bytes = 512 × float32) |
| `BBox_SAM_Mask`                     | Binary          | SAM segmentation mask (binary array of element boundaries) |
| `BBox_SAM_Contours`                 | String (JSON)   | Precise edge/corner coordinates. Format: `[[x1,y1], [x2,y2], ...]` |
| **Drag-Specific**
| `BBox_drag`                         | String (JSON)   | Target position of drag operation |
| `BBox_drag_rel_coordinates`         | String (JSON)   | Relative coords at drag target |
| `BBox_drag_Template`                | Binary          | PNG crop of drag target |
| `BBox_drag_OCR_text`                | String          | Text at drag target |
| `BBox_drag_EfficientNet_Features`   | Binary          | Features at drag target |
| `BBox_drag_LayoutLM_Type`           | String          | UI element type for drag target |
| `BBox_drag_LayoutLM_Confidence`     | String (JSON)   | Confidence scores for drag target |
| `BBox_drag_CLIP_Features`           | Binary          | CLIP features at drag target |
| `BBox_drag_SAM_Mask`                | Binary          | SAM segmentation mask for drag target |
| `BBox_drag_SAM_Contours`            | String (JSON)   | Precise edges/corners of drag target |
| **Input-Specific**
| `Input_text`                        | String          | The text typed (may include spaces/newlines) |
| `Enter_After_Input_text`            | Integer         | 1 if Enter was pressed after text, 0 otherwise |
| **Scroll-Specific**
| `Scroll_DX`                         | Integer         | Horizontal scroll amount (0 for vertical scroll) |
| `Scroll_DY`                         | Integer         | Vertical scroll amount (negative = up, positive = down) |

**Important Notes:**
- `BBox_rel_coordinates` is NULL for INPUT actions (no click on input field)
- EfficientNet features are 1280-dimensional vectors at 4 bytes each = 5120 bytes
- LayoutLMv3 element types stored as JSON for flexibility
- After step deletion, `reorder_steps()` must be called to maintain sequential Step_number

---

## Table 3: execution_session

**Purpose:** Records metadata about a single Execution run (automated playback).

**Key Constraint:** Exactly one session per database (ID = 1)

| Column                       | Type         | Description |
|------------------------------|--------------|-------------|
| `ID`                         | Integer (PK) | Always 1 - Single session per database |
| `Designer_Session_ID`        | Integer      | ID from source Designer database (always 1) |
| `Designer_DB_path`           | String       | Full path to source Designer database file |
| `Execution_start_timestamp`  | DateTime     | When playback started |
| `Execution_end_timestamp`    | DateTime     | When playback finished (NULL until complete) |
| `Execution_result`           | String       | Overall result: PASSED, FAILED, or STOPPED |
| `Execution_error`            | String       | Error message if execution failed (NULL if PASSED) |

**Usage:**
- Links execution back to the original Designer recording
- Tracks overall success/failure of the entire playback
- Individual step results stored in `execution_step` table

---

## Table 4: execution_step

**Purpose:** Records results from executing each Designer step.

Stores original Designer data alongside detected data and match scores for comparison.

| Column                                          | Type            | Notes |
|-------------------------------------------------|-----------------|-------|
| **Primary Key**
| `ID`                                            | Integer (PK)    | Auto-incrementing |
| **Metadata**
| `Step_number`                                   | Integer         | Matches Designer step number |
| `Step_testcase`                                 | Integer         | Optional test case ID |
| **Action Data**
| `Action_type`                                   | String          | Type of action (same as Designer) |
| `Screenshot`                                    | Binary          | Full-screen screenshot taken during execution |
| `Modifier_keys`                                 | String (JSON)   | Keyboard modifiers used |
| **Status & Matching**
| `Status`                                        | String          | PASSED, FAILED, STOPPED, or SKIPPED |
| `Video_timestamp`                               | Float           | Seconds in video when step was executed |
| `Matched_Attempt`                               | Integer         | Which attempt succeeded: 1, 2, or 3 |
| `Matched_Stage`                                 | Integer         | Which retry stage: 1 (initial), 2+ (after wait) |
| `Matched_drag_Attempt`                          | Integer         | For DRAG_AND_DROP: which attempt for target |
| `Matched_drag_Stage`                            | Integer         | For DRAG_AND_DROP: which stage for target |

| **Original Data (from Designer)**
| `BBox`                                          | String (JSON)   | Original BBox from Designer |
| `BBox_Template`                                 | Binary          | Original template from Designer |
| `BBox_OCR_text`                                 | String          | Original OCR text from Designer |
| `BBox_EfficientNet_Features`                    | Binary          | Original EfficientNet features |
| `BBox_LayoutLM_Type`                            | String          | Original UI element type |
| `BBox_LayoutLM_Confidence`                      | String (JSON)   | Original confidence scores |
| `BBox_CLIP_Features`                            | Binary          | Original CLIP features |
| `BBox_SAM_Mask`                                 | Binary          | Original SAM segmentation mask |
| `BBox_SAM_Contours`                             | String (JSON)   | Original precise edges/corners |
| `BBox_rel_coordinates`                          | String (JSON)   | Original relative coordinates |
| **Detected Data (from Executor)**
| `BBox_Exec_Detected`                            | String (JSON)   | Where element was actually found |
| `BBox_Exec_Template_Detected`                   | Binary          | Template crop of detected element |
| `BBox_Exec_OCR_text_Detected`                   | String          | Text detected in matched region |
| `BBox_Exec_EfficientNet_Features_Detected`      | Binary          | Features extracted from matched region |
| `BBox_Exec_LayoutLM_Type_Detected`              | String          | Detected UI element type in matched region |
| `BBox_Exec_LayoutLM_Confidence_Detected`        | String (JSON)   | Detected confidence scores in matched region |
| `BBox_Exec_CLIP_Features_Detected`              | Binary          | CLIP features detected in matched region |
| `BBox_Exec_SAM_Mask_Detected`                   | Binary          | SAM segmentation mask detected in matched region |
| `BBox_Exec_SAM_Contours_Detected`               | String (JSON)   | Precise edges/corners detected in matched region |
| **Match Scores (0.0 to 1.0)**
| `BBox_Match_Score`                              | Float           | Combined voting score (weighted average) |
| `BBox_Template_Score`                           | Float           | Template matching confidence |
| `BBox_OCR_Score`                                | Float           | OCR text similarity (0 = no match, 1 = identical) |
| `BBox_EfficientNet_Score`                       | Float           | Feature cosine similarity (0 = different, 1 = identical) |
| `BBox_LayoutLM_Score`                           | Float           | UI element type matching (0 = different, 1 = identical) |
| `BBox_CLIP_Score`                               | Float           | CLIP multimodal similarity (0 = different, 1 = identical) |
| `BBox_SAM_Score`                                | Float           | SAM contour matching score (0 = different, 1 = identical edges) |

| **Drag Data (from Designer)** 
| `BBox_drag`                                     | String (JSON)   | Original drag target position |
| `BBox_drag_Template`                            | Binary          | Template of drag target |
| `BBox_drag_OCR_text`                            | String          | Text at drag target |
| `BBox_drag_EfficientNet_Features`               | Binary          | Features at drag target |
| `BBox_drag_LayoutLM_Type`                       | String          | UI element type for drag target |
| `BBox_drag_LayoutLM_Confidence`                 | String (JSON)   | Confidence scores for drag target |
| `BBox_drag_CLIP_Features`                       | Binary          | CLIP features at drag target |
| `BBox_drag_SAM_Mask`                            | Binary          | SAM segmentation mask for drag target |
| `BBox_drag_SAM_Contours`                        | String (JSON)   | Precise edges/corners of drag target |
| `BBox_drag_rel_coordinates`                     | String (JSON)   | Relative coords at drag target |
| **Drag detected Data (from Executor)**
| `BBox_drag_Exec_Detected`                       | String (JSON)   | Where drag target was found |
| `BBox_drag_Exec_Template_Detected`              | Binary          | Template of detected drag target |
| `BBox_drag_Exec_OCR_text_Detected`              | String          | Text detected at drag target |
| `BBox_drag_Exec_EfficientNet_Features_Detected` | Binary          | Features detected at drag target |
| `BBox_drag_Exec_LayoutLM_Type_Detected`         | String          | Detected UI element type at drag target |
| `BBox_drag_Exec_LayoutLM_Confidence_Detected`   | String (JSON)   | Detected confidence scores at drag target |
| `BBox_drag_Exec_CLIP_Features_Detected`         | Binary          | CLIP features detected at drag target |
| `BBox_drag_Exec_SAM_Mask_Detected`              | Binary          | SAM mask detected at drag target |
| `BBox_drag_Exec_SAM_Contours_Detected`          | String (JSON)   | Edges/corners detected at drag target |
| **Drag Match Scores (0.0 to 1.0)**
| `BBox_drag_Match_Score`                         | Float           | Combined score for drag target |
| `BBox_drag_Template_Score`                      | Float           | Template score for drag target |
| `BBox_drag_OCR_Score`                           | Float           | OCR score for drag target |
| `BBox_drag_EfficientNet_Score`                  | Float           | EfficientNet score for drag target |
| `BBox_drag_LayoutLM_Score`                      | Float           | UI element type matching score for drag target |
| `BBox_drag_CLIP_Score`                          | Float           | CLIP score for drag target |
| `BBox_drag_SAM_Score`                           | Float           | SAM contour matching score for drag target |

| **Input-Specific**
| `Input_text`                                    | String          | Text that was typed |
| `Enter_After_Input_text`                        | Integer         | 1 if Enter pressed, 0 otherwise |
| **Scroll-Specific**
| `Scroll_DX`                                     | Integer         | Horizontal scroll amount |
| `Scroll_DY`                                     | Integer         | Vertical scroll amount |

---

## AI Models & Matching Methods Used

The system uses four AI models and one traditional matching method:

### 0. **Template Matching**
- Traditional image matching (not ML-based)
- Compares pixel-level similarity between template crop and detected region
- Uses normalized cross-correlation or similar metrics
- Fast and reliable for pixel-perfect matches
- Stored in: `BBox_Template`, `BBox_drag_Template`, `BBox_Exec_Template_Detected`, `BBox_drag_Exec_Template_Detected`
- Score: 0.0 (no match) to 1.0 (perfect pixel match)

### 1. **OCR (EasyOCR)**
- Extracts text from detected regions
- Language: English
- Stored in: `BBox_OCR_text`, `BBox_drag_OCR_text`
- Score: 0.0 (no match) to 1.0 (identical text)

### 2. **EfficientNet-B7 (PyTorchVision)**
- Extracts visual features from element crops
- Output: 1280-dimensional feature vector (5120 bytes)
- Similarity measured via cosine distance
- Stored in: `BBox_EfficientNet_Features`, `BBox_drag_EfficientNet_Features`
- Score: 0.0 (different) to 1.0 (identical)

### 3. **LayoutLMv3 (Microsoft)**
- Specialized layout and UI understanding model
- Classifies UI element types (button, input, text, image, etc.)
- Understands hierarchical UI structure and layout
- Returns: element type, confidence scores
- Stored in: `BBox_LayoutLM_Type`, `BBox_LayoutLM_Confidence`, `BBox_drag_LayoutLM_Type`, `BBox_drag_LayoutLM_Confidence`
- Score: 0.0 to 1.0 (type matching confidence)
- Superior to YOLO for UI-specific detection and classification

### 4. **CLIP (OpenAI)**
- Multimodal model (vision + language)
- Matches UI elements using both image and text descriptions
- Output: 512-dimensional feature vector (2048 bytes)
- Excellent for UI elements without OCR text
- Stored in: `BBox_CLIP_Features`, `BBox_drag_CLIP_Features`, `BBox_Exec_CLIP_Features_Detected`, `BBox_drag_Exec_CLIP_Features_Detected`
- Score: 0.0 (different) to 1.0 (identical)

### 5. **SAM (Meta - Segment Anything Model)**
- Precise edge and corner detection for UI elements
- Segments UI boundaries with pixel-level accuracy
- Output: Binary segmentation mask + precise contour coordinates
- Stored in: `BBox_SAM_Mask`, `BBox_SAM_Contours`, `BBox_drag_SAM_Mask`, `BBox_drag_SAM_Contours`
- Detected data: `BBox_Exec_SAM_Mask_Detected`, `BBox_Exec_SAM_Contours_Detected`, etc.
- Score: 0.0 (different edges) to 1.0 (identical edges/corners)
- Uses ViT-L architecture for maximum accuracy on UI shapes

---


## Performance Considerations

- **Screenshot storage:** Full-screen PNGs can be 1-5 MB each
- **Binary features:** EfficientNet (5120 bytes) per BBox + drag BBox
- **Large databases:** Designer with 1000+ steps can exceed 5 GB
- **Indexes:** Use on `Step_number` and `Status` for faster queries
- **Cleanup:** Implement retention policy to archive old databases

---

## Relationships

```
designer.db
├── designer_session (1 record)
│   └── designer_step (many records - 1:many)

execution.db
├── execution_session (1 record, references designer_session.ID)
│   └── execution_step (many records - 1:many)
```

Each execution step contains both original Designer data and detected execution data for comparison.
