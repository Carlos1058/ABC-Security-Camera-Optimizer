"""Coverage evaluation, optical ray-casting, and multi-camera combination."""

from camera_optimizer.coverage.evaluator import (
    calculate_point_probability,
    evaluate_camera_grid,
    evaluate_camera_grid_visibility_and_probabilities,
    evaluate_multicamera_coverage,
    is_point_geometrically_covered,
)
from camera_optimizer.coverage.metrics import CoverageMetrics

__all__ = [
    "CoverageMetrics",
    "calculate_point_probability",
    "evaluate_camera_grid",
    "evaluate_camera_grid_visibility_and_probabilities",
    "evaluate_multicamera_coverage",
    "is_point_geometrically_covered",
]
