"""Data structures for comprehensive coverage and visibility metrics."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True, slots=True)
class CoverageMetrics:
    """Detailed multi-camera coverage and visibility metrics over an evaluation grid.

    Attributes
    ----------
    num_eval_points : int
        Total number of discrete evaluation points in the grid (N).
    num_covered_points : int
        Number of evaluation points observed by at least one camera with non-zero probability.
    geometric_coverage_ratio : float
        Fraction of evaluation points with binary coverage in [0.0, 1.0].
    geometric_coverage_percent : float
        Percentage of evaluation points with binary coverage in [0.0, 100.0].
    mean_probabilistic_coverage : float
        Unweighted arithmetic mean of combined detection probabilities across all points, in [0.0, 1.0].
    risk_weighted_coverage : float
        Risk-weighted probabilistic coverage metric C_risk in [0.0, 1.0].
    num_critical_points : int
        Number of evaluation points located in high-risk zones (weight > 1.0).
    critical_deficit : float
        Normalized critical deficit penalty metric Deficit_crit in [0.0, 1.0].
    point_probabilities : np.ndarray
        1D array of shape (N,) containing combined detection probability P_det for each point.
    point_binary_covered : np.ndarray
        1D boolean array of shape (N,) indicating whether each point is covered by >= 1 camera.
    """

    num_eval_points: int
    num_covered_points: int
    geometric_coverage_ratio: float
    geometric_coverage_percent: float
    mean_probabilistic_coverage: float
    risk_weighted_coverage: float
    num_critical_points: int
    critical_deficit: float
    point_probabilities: np.ndarray
    point_binary_covered: np.ndarray

    def to_dict(self) -> dict[str, float | int]:
        """Convert scalar summary metrics to a serializable dictionary."""
        return {
            "num_eval_points": self.num_eval_points,
            "num_covered_points": self.num_covered_points,
            "geometric_coverage_ratio": self.geometric_coverage_ratio,
            "geometric_coverage_percent": self.geometric_coverage_percent,
            "mean_probabilistic_coverage": self.mean_probabilistic_coverage,
            "risk_weighted_coverage": self.risk_weighted_coverage,
            "num_critical_points": self.num_critical_points,
            "critical_deficit": self.critical_deficit,
        }
