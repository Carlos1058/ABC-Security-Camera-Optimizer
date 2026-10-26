"""Domain model for solid interior obstacles."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from camera_optimizer.domain.wall import WallSegment
from camera_optimizer.geometry.intersections import DEFAULT_TOLERANCE
from camera_optimizer.geometry.point import Point2D
from camera_optimizer.geometry.polygon import Polygon2D


@dataclass(frozen=True, slots=True)
class ObstaclePolygon:
    """Represents a solid impenetrable obstacle inside the facility."""

    polygon: Polygon2D

    def __init__(self, vertices: Sequence[Point2D], tol: float = DEFAULT_TOLERANCE) -> None:
        """Initialize and validate a solid obstacle from a sequence of vertices."""
        poly = Polygon2D(vertices, tol=tol)
        object.__setattr__(self, "polygon", poly)

    @classmethod
    def from_rectangle(
        cls, xmin: float, xmax: float, ymin: float, ymax: float, tol: float = DEFAULT_TOLERANCE
    ) -> ObstaclePolygon:
        """Construct an obstacle from a rectangular bounding box."""
        if xmin >= xmax or ymin >= ymax:
            raise ValueError(f"Invalid rectangle bounds: xmin={xmin}, xmax={xmax}, ymin={ymin}, ymax={ymax}")
        vertices = [
            Point2D(xmin, ymin),
            Point2D(xmax, ymin),
            Point2D(xmax, ymax),
            Point2D(xmin, ymax),
        ]
        return cls(vertices, tol=tol)

    @property
    def vertices(self) -> tuple[Point2D, ...]:
        """Ordered vertices of the obstacle polygon."""
        return self.polygon.vertices

    @property
    def area(self) -> float:
        """Area occupied by the obstacle in square meters."""
        return self.polygon.area

    @property
    def boundary_segments(self) -> list[WallSegment]:
        """Opaque boundary wall segments forming the perimeter of the obstacle."""
        n = len(self.vertices)
        return [
            WallSegment(self.vertices[i], self.vertices[(i + 1) % n], is_opaque=True)
            for i in range(n)
        ]

    def contains_point(self, point: Point2D, include_boundary: bool = True, tol: float = DEFAULT_TOLERANCE) -> bool:
        """Check if a point is inside the solid obstacle."""
        return self.polygon.contains_point(point, include_boundary=include_boundary, tol=tol)
