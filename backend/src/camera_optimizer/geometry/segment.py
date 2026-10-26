"""2D Line Segment representation and operations."""

from __future__ import annotations

import math
from dataclasses import dataclass

from camera_optimizer.geometry.intersections import (
    DEFAULT_ANGULAR_TOLERANCE,
    DEFAULT_TOLERANCE,
    SegmentIntersection,
    blocks_line_of_sight,
    intersect_segments,
)
from camera_optimizer.geometry.point import Point2D


@dataclass(frozen=True, slots=True)
class Segment2D:
    """Represents a finite 2D line segment between two distinct points."""

    start: Point2D
    end: Point2D

    def __post_init__(self) -> None:
        """Validate that endpoints are valid Point2D instances and non-degenerate."""
        if not isinstance(self.start, Point2D) or not isinstance(self.end, Point2D):
            raise TypeError("Segment2D endpoints must be Point2D instances")

        if self.start.distance_to(self.end) < DEFAULT_TOLERANCE:
            raise ValueError(
                f"Degenerate segment: start {self.start} and end {self.end} are identical within tolerance"
            )

    @property
    def length(self) -> float:
        """Euclidean length of the segment in meters."""
        return self.start.distance_to(self.end)

    def contains_point(self, point: Point2D, tol: float = DEFAULT_TOLERANCE) -> bool:
        """Check if a point lies on this closed segment within spatial tolerance."""
        if not isinstance(point, Point2D):
            raise TypeError(f"Expected Point2D instance, got {type(point).__name__}")

        vx = self.end.x - self.start.x
        vy = self.end.y - self.start.y
        wx = point.x - self.start.x
        wy = point.y - self.start.y

        # Cross product magnitude: perpendicular distance * length
        cross = abs(vx * wy - vy * wx)
        seg_len = self.length

        if cross > tol * seg_len:
            return False

        # Dot product projection along segment vector
        dot = wx * vx + wy * vy
        if dot < -tol * seg_len or dot > (seg_len * seg_len) + (tol * seg_len):
            return False

        return True

    def intersect_with(
        self,
        other: Segment2D,
        tol: float = DEFAULT_TOLERANCE,
        angular_tol: float = DEFAULT_ANGULAR_TOLERANCE,
    ) -> SegmentIntersection:
        """Compute the intersection with another Segment2D."""
        if not isinstance(other, Segment2D):
            raise TypeError(f"Expected Segment2D instance, got {type(other).__name__}")
        return intersect_segments(
            self.start, self.end, other.start, other.end, tol=tol, angular_tol=angular_tol
        )

    def blocks_ray(
        self,
        ray_start: Point2D,
        ray_end: Point2D,
        tol: float = DEFAULT_TOLERANCE,
        angular_tol: float = DEFAULT_ANGULAR_TOLERANCE,
    ) -> bool:
        """Determine if this segment blocks line of sight between ray_start and ray_end."""
        return blocks_line_of_sight(
            ray_start, ray_end, self.start, self.end, tol=tol, angular_tol=angular_tol
        )
