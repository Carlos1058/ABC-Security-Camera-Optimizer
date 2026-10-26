"""Camera pose representation and circular angle normalization."""

from __future__ import annotations

import math
from dataclasses import dataclass

from camera_optimizer.geometry.point import Point2D


def wrap_pi(angle: float) -> float:
    """Wrap an angle in radians to the half-open interval [-pi, pi).

    Parameters
    ----------
    angle : float
        Angle in radians.

    Returns
    -------
    float
        Normalized angle strictly within [-pi, pi).
    """
    if not math.isfinite(angle):
        raise ValueError(f"Angle must be a finite real number, got {angle}")

    # Standard two-pi modulo wrapping into [0, 2*pi)
    wrapped = (angle + math.pi) % (2.0 * math.pi) - math.pi
    # Handle floating point boundary rounding edge
    if wrapped < -math.pi:
        wrapped += 2.0 * math.pi
    elif wrapped >= math.pi:
        wrapped -= 2.0 * math.pi
    return wrapped


@dataclass(frozen=True, slots=True)
class CameraPose:
    """Represents the 2D position and optical heading of a ceiling-mounted camera.

    Attributes
    ----------
    x : float
        X-coordinate in meters.
    y : float
        Y-coordinate in meters.
    theta : float
        Optical heading in radians, normalized to [-pi, pi).
        theta = 0 corresponds to facing toward +X (East).
        theta = pi/2 corresponds to facing toward +Y (North).
    """

    x: float
    y: float
    theta: float

    def __post_init__(self) -> None:
        """Validate coordinates and normalize orientation."""
        try:
            fx = float(self.x)
            fy = float(self.y)
            ftheta = float(self.theta)
        except (TypeError, ValueError) as err:
            raise TypeError(f"CameraPose coordinates and theta must be numbers, got ({self.x!r}, {self.y!r}, {self.theta!r})") from err

        if not (math.isfinite(fx) and math.isfinite(fy) and math.isfinite(ftheta)):
            raise ValueError(
                f"CameraPose coordinates and theta must be finite real numbers, got ({fx}, {fy}, {ftheta})"
            )

        normalized_theta = wrap_pi(ftheta)
        object.__setattr__(self, "x", fx)
        object.__setattr__(self, "y", fy)
        object.__setattr__(self, "theta", normalized_theta)

    @property
    def point(self) -> Point2D:
        """Return camera location as a Point2D."""
        return Point2D(self.x, self.y)

    def as_tuple(self) -> tuple[float, float, float]:
        """Return camera pose as a tuple (x, y, theta)."""
        return (self.x, self.y, self.theta)

    def distance_to(self, target: Point2D) -> float:
        """Compute Euclidean distance from camera to a 2D target point."""
        return math.hypot(target.x - self.x, target.y - self.y)

    def angle_to(self, target: Point2D) -> float:
        """Compute absolute bearing angle phi from camera to a 2D target point in [-pi, pi)."""
        return math.atan2(target.y - self.y, target.x - self.x)

    def angular_deviation_to(self, target: Point2D) -> float:
        """Compute circular angular deviation delta from camera optical axis to target point in [-pi, pi)."""
        phi = self.angle_to(target)
        return wrap_pi(phi - self.theta)
