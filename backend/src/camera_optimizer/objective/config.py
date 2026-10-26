"""Configuration parameters for the optimization objective function."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ObjectiveConfig:
    """Hyperparameters governing the mathematical cost and penalty formulation.

    Attributes
    ----------
    lambda_def : float
        Non-negative penalty weight multiplying the critical zone coverage deficit, >= 0.0.
        When lambda_def = 0.0, the objective depends solely on facility-wide risk-weighted coverage.
    t_crit : float
        Critical detection probability threshold in (0.0, 1.0], determining the baseline
        acceptable detection level for nodes in high-risk zones (weight > 1.0).
    """

    lambda_def: float = 1.0
    t_crit: float = 0.8

    def __post_init__(self) -> None:
        """Validate objective hyperparameters."""
        try:
            f_lambda = float(self.lambda_def)
            f_tcrit = float(self.t_crit)
        except (TypeError, ValueError) as err:
            raise TypeError(f"ObjectiveConfig parameters must be numbers, got ({self.lambda_def!r}, {self.t_crit!r})") from err

        if not (math.isfinite(f_lambda) and math.isfinite(f_tcrit)):
            raise ValueError(
                f"ObjectiveConfig parameters must be finite real numbers, got lambda_def={f_lambda}, t_crit={f_tcrit}"
            )

        if f_lambda < 0.0:
            raise ValueError(f"lambda_def must be non-negative (>= 0.0), got {f_lambda}")
        if not (0.0 < f_tcrit <= 1.0):
            raise ValueError(f"t_crit must be in the open-closed interval (0.0, 1.0], got {f_tcrit}")

        object.__setattr__(self, "lambda_def", f_lambda)
        object.__setattr__(self, "t_crit", f_tcrit)
