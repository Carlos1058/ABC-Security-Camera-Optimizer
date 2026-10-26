"""Geometry module re-exports."""

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

__all__ = [
    "DEFAULT_ANGULAR_TOLERANCE",
    "DEFAULT_SPATIAL_TOLERANCE",
    "DEFAULT_TOLERANCE",
    "BoundingBox",
    "IntersectionType",
    "Point2D",
    "Polygon2D",
    "Segment2D",
    "SegmentIntersection",
    "blocks_line_of_sight",
    "intersect_segments",
]
