"""ABC Security Camera Optimizer - 2D Geometric Core, Optical Models, Objective Evaluator & Sequential ABC."""

from camera_optimizer.camera.pose import CameraPose, wrap_pi
from camera_optimizer.camera.profile import CameraProfile
from camera_optimizer.coverage.evaluator import (
    calculate_point_probability,
    evaluate_camera_grid,
    evaluate_camera_grid_visibility_and_probabilities,
    evaluate_multicamera_coverage,
    is_point_geometrically_covered,
)
from camera_optimizer.coverage.metrics import CoverageMetrics
from camera_optimizer.domain.floorplan import FloorPlan
from camera_optimizer.domain.grid import DEFAULT_MAX_GRID_CELLS, GridNode, SamplingGrid
from camera_optimizer.domain.obstacle import ObstaclePolygon
from camera_optimizer.domain.risk_zone import RiskZone
from camera_optimizer.domain.wall import WallSegment
from camera_optimizer.geometry.bounding_box import BoundingBox
from camera_optimizer.geometry.intersections import (
    DEFAULT_ANGULAR_TOLERANCE,
    DEFAULT_SPATIAL_TOLERANCE,
    DEFAULT_TOLERANCE,
    IntersectionType,
    SegmentIntersection,
    blocks_line_of_sight,
    intersect_segments,
)
from camera_optimizer.geometry.point import Point2D
from camera_optimizer.geometry.polygon import Polygon2D
from camera_optimizer.geometry.segment import Segment2D
from camera_optimizer.objective.config import ObjectiveConfig
from camera_optimizer.objective.evaluator import (
    ConfigurationEvaluator,
    EvaluationResult,
)
from camera_optimizer.optimizer.bounds import (
    Bounds,
    DimensionSpec,
    VariableType,
)
from camera_optimizer.optimizer.camera_problem import CameraOptimizationProblem
from camera_optimizer.optimizer.config import ABCConfig
from camera_optimizer.optimizer.food_source import (
    FoodSource,
    calculate_fitness,
)
from camera_optimizer.optimizer.problem import (
    OptimizationProblem,
    RastriginProblem,
    SphereProblem,
)
from camera_optimizer.optimizer.sequential_abc import SequentialABC
from camera_optimizer.optimizer.tracking import (
    ABCOutput,
    ABCTracker,
    CycleRecord,
    TraceEvent,
)
from camera_optimizer.api.app import app, create_app

__version__ = "0.4.0"

__all__ = [
    # Tolerances
    "DEFAULT_ANGULAR_TOLERANCE",
    "DEFAULT_MAX_GRID_CELLS",
    "DEFAULT_SPATIAL_TOLERANCE",
    "DEFAULT_TOLERANCE",
    # Geometry
    "BoundingBox",
    "IntersectionType",
    "Point2D",
    "Polygon2D",
    "Segment2D",
    "SegmentIntersection",
    "blocks_line_of_sight",
    "intersect_segments",
    # Domain
    "FloorPlan",
    "GridNode",
    "ObstaclePolygon",
    "RiskZone",
    "SamplingGrid",
    "WallSegment",
    # Camera
    "CameraPose",
    "CameraProfile",
    "wrap_pi",
    # Coverage
    "CoverageMetrics",
    "calculate_point_probability",
    "evaluate_camera_grid",
    "evaluate_camera_grid_visibility_and_probabilities",
    "evaluate_multicamera_coverage",
    "is_point_geometrically_covered",
    # Objective
    "ConfigurationEvaluator",
    "EvaluationResult",
    "ObjectiveConfig",
    # Optimizer (Phase 3)
    "ABCConfig",
    "ABCOutput",
    "ABCTracker",
    "Bounds",
    "CameraOptimizationProblem",
    "CycleRecord",
    "DimensionSpec",
    "FoodSource",
    "OptimizationProblem",
    "RastriginProblem",
    "SequentialABC",
    "SphereProblem",
    "TraceEvent",
    "VariableType",
    "calculate_fitness",
    # API
    "app",
    "create_app",
]
