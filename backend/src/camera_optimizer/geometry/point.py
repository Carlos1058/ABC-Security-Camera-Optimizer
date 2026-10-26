"""2D Point representation and fundamental operations."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Point2D:
    """Represents an immutable 2D point with Cartesian coordinates.
    
    Coordinates are assumed to be in meters within floor plan space.
    """
    x: float
    y: float

    def __post_init__(self) -> None:
        """Validate that coordinates are real, finite floating-point numbers."""
        try:
            x_val = float(self.x)
            y_val = float(self.y)
        except (TypeError, ValueError) as err:
            raise TypeError(f"Point2D coordinates must be real numbers, got x={self.x!r}, y={self.y!r}") from err

        if not (math.isfinite(x_val) and math.isfinite(y_val)):
            raise ValueError(f"Point2D coordinates must be finite numbers, got x={x_val}, y={y_val}")

        # Ensure values stored are normalized floats
        object.__setattr__(self, "x", x_val)
        object.__setattr__(self, "y", y_val)

    def distance_to(self, other: Point2D) -> float:
        """Calculate Euclidean distance to another 2D point in meters."""
        if not isinstance(other, Point2D):
            raise TypeError(f"Expected Point2D instance, got {type(other).__name__}")
        return math.hypot(self.x - other.x, self.y - other.y)

    def as_tuple(self) -> tuple[float, float]:
        """Return coordinates as an (x, y) tuple."""
        return (self.x, self.y)

    def __repr__(self) -> str:
        return f"Point2D({self.x:.6g}, {self.y:.6g})"
