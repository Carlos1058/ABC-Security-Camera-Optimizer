"""2D Axis-aligned Bounding Box representation and queries."""

from __future__ import annotations

import math
from dataclasses import dataclass

from camera_optimizer.geometry.point import Point2D


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Represents an axis-aligned bounding box [xmin, xmax] x [ymin, ymax]."""

    xmin: float
    xmax: float
    ymin: float
    ymax: float

    def __post_init__(self) -> None:
        """Validate box dimensions and finiteness."""
        try:
            x_min = float(self.xmin)
            x_max = float(self.xmax)
            y_min = float(self.ymin)
            y_max = float(self.ymax)
        except (TypeError, ValueError) as err:
            raise TypeError("BoundingBox coordinates must be real numbers") from err

        if not (math.isfinite(x_min) and math.isfinite(x_max) and math.isfinite(y_min) and math.isfinite(y_max)):
            raise ValueError(f"BoundingBox coordinates must be finite: ({x_min}, {x_max}, {y_min}, {y_max})")

        if x_min >= x_max:
            raise ValueError(f"BoundingBox xmin ({x_min}) must be strictly less than xmax ({x_max})")

        if y_min >= y_max:
            raise ValueError(f"BoundingBox ymin ({y_min}) must be strictly less than ymax ({y_max})")

        object.__setattr__(self, "xmin", x_min)
        object.__setattr__(self, "xmax", x_max)
        object.__setattr__(self, "ymin", y_min)
        object.__setattr__(self, "ymax", y_max)

    @property
    def width(self) -> float:
        """Width along the X axis in meters."""
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        """Height along the Y axis in meters."""
        return self.ymax - self.ymin

    @property
    def area(self) -> float:
        """Enclosed area in square meters."""
        return self.width * self.height

    @property
    def center(self) -> Point2D:
        """Geometric center of the bounding box."""
        return Point2D((self.xmin + self.xmax) / 2.0, (self.ymin + self.ymax) / 2.0)

    def contains(self, point: Point2D, inclusive: bool = True) -> bool:
        """Check if a Point2D is located within the box bounds."""
        if not isinstance(point, Point2D):
            raise TypeError(f"Expected Point2D instance, got {type(point).__name__}")

        if inclusive:
            return (self.xmin <= point.x <= self.xmax) and (self.ymin <= point.y <= self.ymax)
        return (self.xmin < point.x < self.xmax) and (self.ymin < point.y < self.ymax)

    def intersects(self, other: BoundingBox) -> bool:
        """Check if this bounding box intersects another bounding box."""
        if not isinstance(other, BoundingBox):
            raise TypeError(f"Expected BoundingBox instance, got {type(other).__name__}")
        return not (
            self.xmax < other.xmin
            or self.xmin > other.xmax
            or self.ymax < other.ymin
            or self.ymin > other.ymax
        )
