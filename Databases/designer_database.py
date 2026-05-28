"""Database handler for Designer."""

import os
import sys

# Add project root to path for absolute imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from .models import DesignerBase, DesignerSession, DesignerStep


class DesignerDatabase:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._engine = create_engine(f"sqlite:///{db_path}", echo=False)
        DesignerBase.metadata.create_all(self._engine)
        self._Session = sessionmaker(bind=self._engine)

    # ========== DesignerSession Methods ==========

    def create_session(self, screen_resolution: str, screen_zoom: str) -> DesignerSession:
        """Create the designer session (only one per database).

        Raises:
            ValueError: If a session already exists in this database
        """
        with self._Session() as session:
            # Check if session already exists
            existing = session.query(DesignerSession).first()
            if existing:
                raise ValueError("Session already exists in this database. Each database can contain only one session (ID=1).")

            try:
                new_session = DesignerSession(
                    Screen_resolution=screen_resolution,
                    Screen_zoom=screen_zoom,
                    Session_created_at=datetime.now()
                )
                session.add(new_session)
                session.commit()
                session.refresh(new_session)
                return new_session
            except Exception as e:
                session.rollback()
                raise RuntimeError(f"Failed to create session: {e}")

    def get_session(self) -> DesignerSession:
        """Get the designer session (only one exists per database)."""
        with self._Session() as session:
            s = session.query(DesignerSession).first()
            if s:
                session.expunge(s)
            return s

    # ========== DesignerStep Methods ==========

    def add_step(self, step: DesignerStep) -> DesignerStep:
        """Create a step in the database."""
        with self._Session() as session:
            session.add(step)
            session.commit()
            session.refresh(step)
            return step

    def update_step(self, step: DesignerStep) -> DesignerStep:
        """Update an existing step in the database."""
        with self._Session() as session:
            existing = session.query(DesignerStep).filter_by(ID=step.ID).first()
            if existing:
                # Update all fields explicitly (including None values)
                existing.Step_number = step.Step_number
                existing.Action_type = step.Action_type
                existing.Step_testcase = step.Step_testcase
                existing.Screenshot = step.Screenshot
                
                existing.BBox = step.BBox
                existing.BBox_Template = step.BBox_Template
                existing.BBox_rel_coordinates = step.BBox_rel_coordinates
                existing.BBox_OCR_text = step.BBox_OCR_text
                existing.BBox_EfficientNet_Features = step.BBox_EfficientNet_Features
                existing.BBox_LayoutLM_Type = step.BBox_LayoutLM_Type
                existing.BBox_LayoutLM_Confidence = step.BBox_LayoutLM_Confidence
                existing.BBox_CLIP_Features = step.BBox_CLIP_Features
                existing.BBox_SAM_Mask = step.BBox_SAM_Mask
                existing.BBox_SAM_Contours = step.BBox_SAM_Contours
                existing.Modifier_keys = step.Modifier_keys
                existing.BBox_drag = step.BBox_drag
                existing.BBox_drag_Template = step.BBox_drag_Template
                existing.BBox_drag_rel_coordinates = step.BBox_drag_rel_coordinates
                existing.BBox_drag_OCR_text = step.BBox_drag_OCR_text
                existing.BBox_drag_EfficientNet_Features = step.BBox_drag_EfficientNet_Features
                existing.BBox_drag_LayoutLM_Type = step.BBox_drag_LayoutLM_Type
                existing.BBox_drag_LayoutLM_Confidence = step.BBox_drag_LayoutLM_Confidence
                existing.BBox_drag_CLIP_Features = step.BBox_drag_CLIP_Features
                existing.BBox_drag_SAM_Mask = step.BBox_drag_SAM_Mask
                existing.BBox_drag_SAM_Contours = step.BBox_drag_SAM_Contours
                existing.Input_text = step.Input_text
                existing.Enter_After_Input_text = step.Enter_After_Input_text
                existing.Scroll_DX = step.Scroll_DX
                existing.Scroll_DY = step.Scroll_DY
                session.commit()
            return step

    def get_steps(self) -> list:
        """Get all steps from the database."""
        with self._Session() as session:
            steps = session.query(DesignerStep).order_by(DesignerStep.Step_number).all()
            for step in steps:
                session.expunge(step)
            return steps

    def get_step_by_id(self, step_id: int) -> DesignerStep:
        """Get a single step by ID (detached from session)."""
        with self._Session() as session:
            step = session.query(DesignerStep).filter_by(ID=step_id).first()
            if step:
                session.expunge(step)
            return step

    def delete_step(self, step_id: int):
        """Delete a step by ID."""
        with self._Session() as session:
            step = session.get(DesignerStep, step_id)
            if step:
                session.delete(step)
                session.commit()

    def reorder_steps(self):
        """Reorder Step_number 1,2,3... after a deletion.

        Uses row-level locking to prevent race conditions if multiple
        threads/processes call this simultaneously.
        """
        with self._Session() as session:
            try:
                # Use FOR UPDATE to lock rows and prevent race conditions
                steps = session.query(DesignerStep)\
                    .order_by(DesignerStep.ID)\
                    .with_for_update()\
                    .all()

                for i, step in enumerate(steps, 1):
                    step.Step_number = i

                session.commit()
            except Exception as e:
                session.rollback()
                raise RuntimeError(f"Failed to reorder steps: {e}")

    def get_last_step(self) -> DesignerStep:
        """Get the most recent step (for INPUT reuse)."""
        with self._Session() as session:
            step = session.query(DesignerStep)\
                .order_by(DesignerStep.Step_number.desc())\
                .first()
            if step:
                session.expunge(step)
            return step

    # ========== Utility ==========

    def close(self):
        """Close the database connection."""
        self._engine.dispose()
