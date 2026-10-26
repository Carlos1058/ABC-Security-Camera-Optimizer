"""Domain model for interior walls and opaque partitions."""

from __future__ import annotations

from dataclasses import dataclass

from camera_optimizer.geometry.intersections import DEFAULT_TOLERANCE
from camera_optimizer.geometry.point import Point2D
from camera_optimizer.geometry.segment import Segment2D


@dataclass(frozen=True, slots=True)
class WallSegment:
    """Represents an opaque wall partition in a floor plan."""

    start: Point2D
    end: Point2D
    is_opaque: bool = True

    def __post_init__(self) -> None:
        """Validate endpoints and non-degeneracy."""
        if not isinstance(self.start, Point2D) or not isinstance(self.end, Point2D):
            raise TypeError("WallSegment endpoints must be Point2D instances")

        if self.start.distance_to(self.end) < DEFAULT_TOLERANCE:
            raise ValueError(
                f"Degenerate WallSegment: start {self.start} and end {self.end} are identical within tolerance"
            )

    @property
    def length(self) -> float:
        """Length of the wall segment in meters."""
        return self.start.distance_to(self.end)

    def as_segment(self) -> Segment2D:
        """Convert to geometric Segment2D."""
        return Segment2D(self.start, self.end)

    def contains_point(self, point: Point2D, tol: float = DEFAULT_TOLERANCE) -> bool:
        """Check if a point lies directly on this wall segment."""
        return self.as_segment().contains_point(point, tol=tol)

    def blocks_ray(self, ray_start: Point2D, ray_end: Point2D, tol: float = DEFAULT_TOLERANCE) -> bool:
        """Check if this wall segment obstructs line of sight between two points."""
        if not self.is_opaque:
            return False
        return self.as_segment().blocks_ray(ray_start, ray_end, tol=tol)
