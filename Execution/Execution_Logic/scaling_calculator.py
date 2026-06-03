"""Scaling factor calculator for execution resolution/zoom adaptation."""

import json
import logging

logger = logging.getLogger(__name__)


def calculate_scale_factors(designer_session, monitor_info, exec_zoom):
    """
    Calculate scale factors for bbox adaptation from designer to execution.

    Args:
        designer_session: DesignerSession with Screen_resolution and Screen_zoom
        monitor_info: dict with 'width', 'height' of execution monitor
        exec_zoom: float (1.0 = 100%, 1.25 = 125%, etc.)

    Returns:
        tuple (scale_x, scale_y)
    """
    try:
        # Parse designer session resolution and zoom
        design_res = json.loads(designer_session.Screen_resolution)
        design_res_w = design_res.get('width', 1920)
        design_res_h = design_res.get('height', 1080)

        design_zoom_str = designer_session.Screen_zoom
        if isinstance(design_zoom_str, str):
            try:
                design_zoom_data = json.loads(design_zoom_str)
                design_zoom = design_zoom_data.get('zoom_level', 100) / 100.0
            except (json.JSONDecodeError, TypeError):
                design_zoom = 1.0
        else:
            design_zoom = 1.0

        # Execution resolution and zoom
        exec_res_w = monitor_info.get('width', 1920)
        exec_res_h = monitor_info.get('height', 1080)

        # Calculate scale factors separately for X and Y
        scale_x = (exec_res_w / design_res_w) * (exec_zoom / design_zoom) if design_res_w > 0 and design_zoom > 0 else 1.0
        scale_y = (exec_res_h / design_res_h) * (exec_zoom / design_zoom) if design_res_h > 0 and design_zoom > 0 else 1.0

        logger.info(f"[SCALING] Designer: {design_res_w}×{design_res_h} @ {design_zoom:.2f}x")
        logger.info(f"[SCALING] Execution: {exec_res_w}×{exec_res_h} @ {exec_zoom:.2f}x")
        logger.info(f"[SCALING] Scale factors: scale_x={scale_x:.4f}, scale_y={scale_y:.4f}")

        return scale_x, scale_y

    except Exception as e:
        logger.error(f"Error calculating scale factors: {e}")
        return 1.0, 1.0


def is_perfect_match_compatible(scale_x, scale_y, tolerance=0.01):
    """
    Check if scale factors are close enough to 1.0 for PERFECT MATCH.

    Args:
        scale_x: float
        scale_y: float
        tolerance: float (default 0.01 = ±1%)

    Returns:
        bool: True if both scale factors are within tolerance of 1.0
    """
    compatible = abs(scale_x - 1.0) < tolerance and abs(scale_y - 1.0) < tolerance

    if compatible:
        logger.info("[SCALING] ✓ PERFECT MATCH compatible (scale ≈ 1.0)")
    else:
        logger.info(f"[SCALING] ✗ SMART MATCH required (scale_x={scale_x:.4f}, scale_y={scale_y:.4f})")

    return compatible
