"""Optical sensor profile and physical parameters for security cameras."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CameraProfile:
    """Optical sensing parameters for a security camera.

    Design note:
    The parameters (Rmin, Rmax, fov, p0, beta_d, beta_theta) define a heuristic
    computational simulation model of sensing confidence. They do NOT represent
    an experimentally validated optical camera sensor model.

    Attributes
    ----------
    Rmin : float
        Minimum sensing distance in meters (blind spot threshold near the lens), >= 0.0.
    Rmax : float
        Maximum effective sensing distance in meters, strictly > Rmin.
    fov : float
        Total horizontal field-of-view aperture in radians, strictly in (0, 2*pi].
    p0 : float
        Nominal maximum detection probability at optimal vantage (lens center, distance Rmin), in (0, 1.0].
    beta_d : float
        Non-negative radial distance attenuation coefficient, >= 0.0.
    beta_theta : float
        Non-negative angular deviation attenuation coefficient, >= 0.0.
    """

    Rmin: float = 0.0
    Rmax: float = 10.0
    fov: float = math.pi / 2.0  # 90 degrees
    p0: float = 1.0
    beta_d: float = 0.5
    beta_theta: float = 0.5

    def __post_init__(self) -> None:
        """Validate all optical parameters strictly against physical and mathematical bounds."""
        params = {
            "Rmin": self.Rmin,
            "Rmax": self.Rmax,
            "fov": self.fov,
            "p0": self.p0,
            "beta_d": self.beta_d,
            "beta_theta": self.beta_theta,
        }
        for name, val in params.items():
            try:
                fval = float(val)
            except (TypeError, ValueError) as err:
                raise TypeError(f"CameraProfile parameter '{name}' must be a number, got {val!r}") from err
            if not math.isfinite(fval):
                raise ValueError(f"CameraProfile parameter '{name}' must be a finite number, got {val}")
            object.__setattr__(self, name, fval)

        if self.Rmin < 0.0:
            raise ValueError(f"Rmin must be non-negative (>= 0.0), got {self.Rmin}")
        if self.Rmax <= self.Rmin:
            raise ValueError(f"Rmax must be strictly greater than Rmin, got Rmax={self.Rmax} <= Rmin={self.Rmin}")
        if not (0.0 < self.fov <= 2.0 * math.pi):
            raise ValueError(f"fov must be in the open-closed interval (0, 2*pi], got {self.fov}")
        if not (0.0 < self.p0 <= 1.0):
            raise ValueError(f"p0 must be in the open-closed interval (0, 1.0], got {self.p0}")
        if self.beta_d < 0.0:
            raise ValueError(f"beta_d must be non-negative (>= 0.0), got {self.beta_d}")
        if self.beta_theta < 0.0:
            raise ValueError(f"beta_theta must be non-negative (>= 0.0), got {self.beta_theta}")

    @property
    def half_fov(self) -> float:
        """Half of the total angular aperture in radians."""
        return self.fov / 2.0

    @property
    def range_span(self) -> float:
        """Effective radial depth (Rmax - Rmin) in meters."""
        return self.Rmax - self.Rmin
