"""Domain module re-exports."""

from camera_optimizer.domain.floorplan import FloorPlan
from camera_optimizer.domain.grid import DEFAULT_MAX_GRID_CELLS, GridNode, SamplingGrid
from camera_optimizer.domain.obstacle import ObstaclePolygon
from camera_optimizer.domain.risk_zone import RiskZone
from camera_optimizer.domain.wall import WallSegment

__all__ = [
    "DEFAULT_MAX_GRID_CELLS",
    "FloorPlan",
    "GridNode",
    "ObstaclePolygon",
    "RiskZone",
    "SamplingGrid",
    "WallSegment",
]
