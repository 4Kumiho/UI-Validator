"""Database handler for Execution."""

import os
import sys
from datetime import datetime

# Add project root to path for absolute imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import ExecutionBase, ExecutionSession, ExecutionStep


class ExecutionDatabase:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._engine = create_engine(f"sqlite:///{db_path}", echo=False)
        ExecutionBase.metadata.create_all(self._engine)
        self._Session = sessionmaker(bind=self._engine)

    # ========== ExecutionSession Methods ==========

    def create_session(self, designer_session_id: int, designer_db_path: str) -> ExecutionSession:
        """Create the execution session (only one per database)."""
        with self._Session() as session:
            new_session = ExecutionSession(
                Designer_Session_ID=designer_session_id,
                Designer_DB_path=designer_db_path,
                Execution_start_timestamp=datetime.now()
            )
            session.add(new_session)
            session.commit()
            session.refresh(new_session)
            return new_session

    def get_session(self) -> ExecutionSession:
        """Get the execution session (only one exists per database)."""
        with self._Session() as session:
            s = session.query(ExecutionSession).first()
            if s:
                session.expunge(s)
            return s

    def update_session_status(self, session_id: int, result: str, error: str = None):
        """Update execution session result and error."""
        with self._Session() as session:
            s = session.query(ExecutionSession).filter_by(ID=session_id).first()
            if s:
                s.Execution_end_timestamp = datetime.now()
                s.Execution_result = result
                s.Execution_error = error
                session.commit()

    # ========== ExecutionStep Methods ==========

    def add_step(self, step: ExecutionStep) -> ExecutionStep:
        """Create a step in the database."""
        with self._Session() as session:
            session.add(step)
            session.commit()
            session.refresh(step)
            return step

    def update_step(self, step: ExecutionStep) -> ExecutionStep:
        """Update an existing step in the database."""
        with self._Session() as session:
            existing = session.query(ExecutionStep).filter_by(ID=step.ID).first()
            if existing:
                # Update all fields explicitly (including None values)
                existing.Step_number = step.Step_number
                existing.Step_testcase = step.Step_testcase
                existing.Action_type = step.Action_type
                existing.Screenshot = step.Screenshot
                existing.Modifier_keys = step.Modifier_keys
                existing.Status = step.Status
                existing.Matched_Attempt = step.Matched_Attempt
                existing.Matched_Stage = step.Matched_Stage
                existing.Matched_drag_Attempt = step.Matched_drag_Attempt
                existing.Matched_drag_Stage = step.Matched_drag_Stage
                existing.BBox = step.BBox
                existing.BBox_Template = step.BBox_Template
                existing.BBox_OCR_text = step.BBox_OCR_text
                existing.BBox_EfficientNet_Features = step.BBox_EfficientNet_Features
                existing.BBox_LayoutLM_Type = step.BBox_LayoutLM_Type
                existing.BBox_LayoutLM_Confidence = step.BBox_LayoutLM_Confidence
                existing.BBox_CLIP_Features = step.BBox_CLIP_Features
                existing.BBox_SAM_Mask = step.BBox_SAM_Mask
                existing.BBox_SAM_Contours = step.BBox_SAM_Contours
                existing.BBox_rel_coordinates = step.BBox_rel_coordinates
                existing.BBox_Exec_Detected = step.BBox_Exec_Detected
                existing.BBox_Exec_Template_Detected = step.BBox_Exec_Template_Detected
                existing.BBox_Exec_OCR_text_Detected = step.BBox_Exec_OCR_text_Detected
                existing.BBox_Exec_EfficientNet_Features_Detected = step.BBox_Exec_EfficientNet_Features_Detected
                existing.BBox_Exec_LayoutLM_Type_Detected = step.BBox_Exec_LayoutLM_Type_Detected
                existing.BBox_Exec_LayoutLM_Confidence_Detected = step.BBox_Exec_LayoutLM_Confidence_Detected
                existing.BBox_Exec_CLIP_Features_Detected = step.BBox_Exec_CLIP_Features_Detected
                existing.BBox_Exec_SAM_Mask_Detected = step.BBox_Exec_SAM_Mask_Detected
                existing.BBox_Exec_SAM_Contours_Detected = step.BBox_Exec_SAM_Contours_Detected
                existing.BBox_Match_Score = step.BBox_Match_Score
                existing.BBox_Template_Score = step.BBox_Template_Score
                existing.BBox_OCR_Score = step.BBox_OCR_Score
                existing.BBox_EfficientNet_Score = step.BBox_EfficientNet_Score
                existing.BBox_LayoutLM_Score = step.BBox_LayoutLM_Score
                existing.BBox_CLIP_Score = step.BBox_CLIP_Score
                existing.BBox_SAM_Score = step.BBox_SAM_Score
                existing.Video_timestamp = step.Video_timestamp
                existing.BBox_drag = step.BBox_drag
                existing.BBox_drag_Template = step.BBox_drag_Template
                existing.BBox_drag_OCR_text = step.BBox_drag_OCR_text
                existing.BBox_drag_EfficientNet_Features = step.BBox_drag_EfficientNet_Features
                existing.BBox_drag_LayoutLM_Type = step.BBox_drag_LayoutLM_Type
                existing.BBox_drag_LayoutLM_Confidence = step.BBox_drag_LayoutLM_Confidence
                existing.BBox_drag_CLIP_Features = step.BBox_drag_CLIP_Features
                existing.BBox_drag_SAM_Mask = step.BBox_drag_SAM_Mask
                existing.BBox_drag_SAM_Contours = step.BBox_drag_SAM_Contours
                existing.BBox_drag_rel_coordinates = step.BBox_drag_rel_coordinates
                existing.BBox_drag_Exec_Detected = step.BBox_drag_Exec_Detected
                existing.BBox_drag_Exec_Template_Detected = step.BBox_drag_Exec_Template_Detected
                existing.BBox_drag_Exec_OCR_text_Detected = step.BBox_drag_Exec_OCR_text_Detected
                existing.BBox_drag_Exec_EfficientNet_Features_Detected = step.BBox_drag_Exec_EfficientNet_Features_Detected
                existing.BBox_drag_Exec_LayoutLM_Type_Detected = step.BBox_drag_Exec_LayoutLM_Type_Detected
                existing.BBox_drag_Exec_LayoutLM_Confidence_Detected = step.BBox_drag_Exec_LayoutLM_Confidence_Detected
                existing.BBox_drag_Exec_CLIP_Features_Detected = step.BBox_drag_Exec_CLIP_Features_Detected
                existing.BBox_drag_Exec_SAM_Mask_Detected = step.BBox_drag_Exec_SAM_Mask_Detected
                existing.BBox_drag_Exec_SAM_Contours_Detected = step.BBox_drag_Exec_SAM_Contours_Detected
                existing.BBox_drag_Match_Score = step.BBox_drag_Match_Score
                existing.BBox_drag_Template_Score = step.BBox_drag_Template_Score
                existing.BBox_drag_OCR_Score = step.BBox_drag_OCR_Score
                existing.BBox_drag_EfficientNet_Score = step.BBox_drag_EfficientNet_Score
                existing.BBox_drag_LayoutLM_Score = step.BBox_drag_LayoutLM_Score
                existing.BBox_drag_CLIP_Score = step.BBox_drag_CLIP_Score
                existing.BBox_drag_SAM_Score = step.BBox_drag_SAM_Score
                existing.Input_text = step.Input_text
                existing.Enter_After_Input_text = step.Enter_After_Input_text
                existing.Scroll_DX = step.Scroll_DX
                existing.Scroll_DY = step.Scroll_DY
                session.commit()
            return step

    def get_steps(self) -> list:
        """Get all steps from the database."""
        with self._Session() as session:
            steps = session.query(ExecutionStep).order_by(ExecutionStep.Step_number).all()
            for step in steps:
                session.expunge(step)
            return steps

    def get_step_by_id(self, step_id: int) -> ExecutionStep:
        """Get a single step by ID (detached from session)."""
        with self._Session() as session:
            step = session.query(ExecutionStep).filter_by(ID=step_id).first()
            if step:
                session.expunge(step)
            return step

    def delete_step(self, step_id: int):
        """Delete a step by ID."""
        with self._Session() as session:
            step = session.get(ExecutionStep, step_id)
            if step:
                session.delete(step)
                session.commit()

    # ========== Utility ==========

    def close(self):
        """Close the database connection."""
        self._engine.dispose()
