"""Domain model for high-priority / critical risk zones."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from camera_optimizer.geometry.intersections import DEFAULT_TOLERANCE
from camera_optimizer.geometry.point import Point2D
from camera_optimizer.geometry.polygon import Polygon2D


@dataclass(frozen=True, slots=True)
class RiskZone:
    """Represents a spatial region requiring heightened camera coverage.

    The weight multiplier w >= 1.0 scales the importance of covering points
    within this zone.
    """

    polygon: Polygon2D
    weight: float
    name: str = ""

    def __init__(
        self,
        polygon_or_vertices: Polygon2D | Sequence[Point2D],
        weight: float,
        name: str = "",
        tol: float = DEFAULT_TOLERANCE,
    ) -> None:
        """Initialize a RiskZone with a boundary polygon and risk weight."""
        try:
            w_val = float(weight)
        except (TypeError, ValueError) as err:
            raise TypeError(f"Risk weight must be a real number, got {weight!r}") from err

        if not math.isfinite(w_val) or w_val < 1.0:
            raise ValueError(f"Risk weight must be finite and >= 1.0, got {w_val}")

        if isinstance(polygon_or_vertices, Polygon2D):
            poly = polygon_or_vertices
        elif isinstance(polygon_or_vertices, Sequence):
            poly = Polygon2D(polygon_or_vertices, tol=tol)
        else:
            raise TypeError(f"Expected Polygon2D or Sequence[Point2D], got {type(polygon_or_vertices).__name__}")

        object.__setattr__(self, "polygon", poly)
        object.__setattr__(self, "weight", w_val)
        object.__setattr__(self, "name", str(name))

    @classmethod
    def from_rectangle(
        cls,
        xmin: float,
        xmax: float,
        ymin: float,
        ymax: float,
        weight: float,
        name: str = "",
        tol: float = DEFAULT_TOLERANCE,
    ) -> RiskZone:
        """Create a rectangular RiskZone from coordinates [xmin, xmax] x [ymin, ymax]."""
        if xmin >= xmax or ymin >= ymax:
            raise ValueError(f"Invalid rectangle coordinates: xmin={xmin}, xmax={xmax}, ymin={ymin}, ymax={ymax}")
        vertices = [
            Point2D(xmin, ymin),
            Point2D(xmax, ymin),
            Point2D(xmax, ymax),
            Point2D(xmin, ymax),
        ]
        return cls(vertices, weight=weight, name=name, tol=tol)

    def contains_point(self, point: Point2D, tol: float = DEFAULT_TOLERANCE) -> bool:
        """Check if a point falls within this risk zone (including boundary)."""
        return self.polygon.contains_point(point, include_boundary=True, tol=tol)
