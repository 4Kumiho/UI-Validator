# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start

**Install dependencies:**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Run the application:**
```powershell
python __main__.py
```

The app requires a modern GPU (CUDA/Metal) for acceptable performance of AI models (YOLO, CLIP, EfficientNet).

## Architecture Overview

UI-Validator is a Kivy-based desktop application that records, replays, and validates UI interactions using multiple AI models for element detection and matching.

### Two-Phase Workflow

1. **Designer Phase** - User records interactions against a target application
   - Captures full-screen screenshots at each step
   - Extracts element bounding boxes and features
   - Runs OCR, template matching, EfficientNet, YOLO, CLIP on each element
   - Stores steps in `designer.db` SQLite database

2. **Execution Phase** - Automated playback validates the recorded steps
   - Replays each step (clicks, text input, drags, scrolls)
   - For each step, detects the element again using the same AI models
   - Compares detected element to original using multiple scoring methods
   - Records match scores and execution results in `execution.db`
   - Supports up to 3 retry attempts per step with configurable wait times

### Project Structure

```
UI-Validator/
├── Application/              # Kivy screens and UI logic
│   ├── Loading_Screen/       # Model initialization and caching
│   ├── Menu_Screen/          # Main menu
│   ├── Create_Designer_Screen/
│   ├── Open_Designer_Screen/
│   ├── Aggregate_Designer_Screen/
│   ├── Create_Execution_Screen/
│   ├── Open_Execution_Screen/
│   ├── _Icons/               # App icons
│   └── model_registry.py     # Global AI model cache
├── Databases/                # SQLAlchemy ORM models and handlers
│   ├── models.py             # DesignerSession, DesignerStep, ExecutionSession, ExecutionStep
│   ├── designer_database.py  # DesignerDatabase class
│   ├── execution_database.py # ExecutionDatabase class
│   └── Databases.md          # Complete schema documentation
├── Designer/                 # Designer phase logic (recording)
├── Execution/                # Execution phase logic (playback & validation)
├── __main__.py               # App entry point
└── requirements.txt          # Dependencies
```

## Key Design Patterns

### Model Registry
`Application/model_registry.py` maintains a global cache of loaded AI models to avoid reloading them. Models (OCR, YOLO, EfficientNet, CLIP) are expensive to load and should be cached in memory across screens.

```python
from Application.model_registry import set_model, get_model
set_model("yolo", yolo_instance)
detector = get_model("yolo")
```

### Screen Architecture
The app uses Kivy's `ScreenManager` to navigate between screens. Each screen is a separate Python module with a corresponding `.kv` file for UI layout.

```python
# In __main__.py
sm = ScreenManager(transition=FadeTransition(duration=0.3))
sm.add_widget(LoadingScreen(name=LoadingScreen.SCREEN_NAME))
sm.add_widget(MenuScreen(name=MenuScreen.SCREEN_NAME))
# ... more screens
sm.current = "loading"  # Switch to loading screen
```

### Database Models
SQLAlchemy ORM with separate declarative bases for Designer and Execution databases:
- `DesignerBase` - Designer database tables
- `ExecutionBase` - Execution database tables

Each database has exactly ONE session (ID = 1) enforced by CHECK constraint. This simplifies the design: you don't query for session ID, you just use ID=1.

## AI Model Details

Four models run on each UI element (stored in database):

| Model | Purpose | Output | Storage |
|-------|---------|--------|---------|
| **OCR** (Tesseract) | Text extraction | Text string | BBox_OCR_text |
| **EfficientNet-V2-L** | Visual features | 1280-dim vector (5120 bytes) | BBox_EfficientNet_Features |
| **YOLOv8x** | Object detection | Class + confidence + bbox | BBox_YOLO_Detections (JSON) |
| **CLIP** (ViT-L/14) | Multimodal matching | 768-dim vector (3072 bytes) | BBox_CLIP_Features |

During execution, each detected element is scored against the original using all four models. A weighted voting scheme combines scores (0.0–1.0) into a final `BBox_Match_Score`.

## Database Schema Highlights

**Designer Database (`designer.db`)**
- `designer_session` - Metadata: screen resolution, zoom level, creation timestamp
- `designer_step` - User actions: type (SINGLE_CLICK, INPUT, DRAG_AND_DROP, SCROLL, etc.), screenshot, extracted features, BBox

**Execution Database (`execution.db`)**
- `execution_session` - Metadata: link to source Designer DB, start/end timestamps, overall result (PASSED/FAILED/STOPPED)
- `execution_step` - Execution results: original Designer data + detected data + match scores for each model

Both databases store full-screen PNG screenshots and feature vectors (binary blobs), making databases large (5GB+ for 1000+ steps is common).

See `Databases/Databases.md` for complete schema with all columns and JSON field formats.

## Important Implementation Notes

### Coordinate System
All coordinates are **absolute screen positions** from top-left:
```json
{"x": 100, "y": 50, "w": 300, "h": 40}  // BBox
{"x": 150, "y": 20}  // Relative coords within BBox
```

During execution, if screen resolution differs from Designer recording, coordinates are scaled:
```
scale_x = execution_width / designer_width
scale_y = execution_height / designer_height
```

### Step Reordering
After deleting a step, call `db.reorder_steps()` to maintain sequential `Step_number` values. This is critical because the Execution phase depends on matching step numbers between databases.

### Model Caching
Models are cached in `~/.cache/ui_validator/` with marker files (`*_loaded.json`) to track completion. The LoadingScreen checks these markers to avoid reloading. When debugging model loading issues, delete the cache directory to force a full reload.

### Modifier Keys
Stored as JSON array: `[]` (none), `["shift"]`, `["ctrl", "shift"]`, etc.

### Drag and Drop
Has a "drag source" BBox and "drag target" BBox. Both have separate feature vectors and match scores. The database schema mirrors BBox fields with a `_drag` suffix.

### Input and Scroll Actions
- **INPUT**: Stores typed text and whether Enter was pressed after
- **SCROLL**: Stores DX (horizontal) and DY (vertical) deltas

## Testing Guidance

The application is primarily tested through manual UI interaction. Test databases can be created by:
1. Running the application and using the Designer screens to record steps
2. Using the Create_Execution_Screen to load a Designer DB and play back steps
3. Inspecting `execution.db` to verify match scores and detected elements

For debugging, the `.cache/ui_validator/` directory contains marker files that can be cleared to force model reloads, and databases are SQLite so they can be inspected with any SQLite browser.

## Performance Considerations

- **AI Model Inference**: 400–2000ms per step (depends on hardware and number of models)
- **Database**: 1000+ steps can exceed 5GB due to PNG screenshots and feature vectors
- **GPU Acceleration**: Models run significantly faster with CUDA/Metal; CPU-only is very slow
- **Model Loading**: First run takes 2-5 minutes; subsequent runs use cache
