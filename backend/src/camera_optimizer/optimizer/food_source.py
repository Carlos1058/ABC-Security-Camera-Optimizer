"""Food source representation and ABC fitness transformation."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


def calculate_fitness(cost: float) -> float:
    """Calculate the standard Artificial Bee Colony fitness metric from objective cost.

    Standard ABC minimization formulation (Karaboga & Basturk, 2007):
        fitness = 1.0 / (1.0 + cost)  if cost >= 0.0
        fitness = 1.0 + abs(cost)     if cost < 0.0

    This transformation ensures that:
    1. Minimizing cost f(x) corresponds to maximizing fitness(f(x)).
    2. Fitness is strictly positive (> 0.0) and finite for all finite costs.
    3. Selection probabilities in the onlooker phase are always well-defined.

    Parameters
    ----------
    cost : float
        Objective function scalar cost to be minimized.

    Returns
    -------
    float
        Strictly positive fitness value.
    """
    if not math.isfinite(cost):
        raise ValueError(f"Objective cost must be a finite real number, got {cost}")

    if cost >= 0.0:
        return 1.0 / (1.0 + cost)
    return 1.0 + abs(cost)


@dataclass(slots=True)
class FoodSource:
    """Represents a food source (candidate solution) in the Artificial Bee Colony algorithm.

    Attributes
    ----------
    position : np.ndarray
        1D coordinate vector of length D (float64).
    cost : float
        Scalar evaluation of the objective function (lower is better).
    fitness : float
        Transformed positive fitness metric used for onlooker roulette selection.
    trial : int
        Abandonment counter tracking consecutive unsuccessful search attempts.
    """

    position: np.ndarray
    cost: float
    fitness: float
    trial: int = 0

    def __post_init__(self) -> None:
        """Validate food source properties."""
        if not isinstance(self.position, np.ndarray):
            raise TypeError(f"Position must be a numpy ndarray, got {type(self.position).__name__}")
        if self.position.ndim != 1:
            raise ValueError(f"Position must be 1-dimensional, got shape {self.position.shape}")
        if not np.all(np.isfinite(self.position)):
            raise ValueError("Position vector contains non-finite values (NaN or Inf)")

        f_cost = float(self.cost)
        if not math.isfinite(f_cost):
            raise ValueError(f"FoodSource cost must be finite, got {f_cost}")

        f_fit = float(self.fitness)
        if not math.isfinite(f_fit) or f_fit <= 0.0:
            raise ValueError(f"FoodSource fitness must be finite and positive, got {f_fit}")

        if self.trial < 0:
            raise ValueError(f"Trial counter cannot be negative, got {self.trial}")

    def copy(self) -> FoodSource:
        """Create an independent deep copy of this food source."""
        return FoodSource(
            position=np.copy(self.position),
            cost=float(self.cost),
            fitness=float(self.fitness),
            trial=int(self.trial),
        )

    def reset_trial(self) -> None:
        """Reset trial counter upon successful improvement."""
        self.trial = 0

    def increment_trial(self) -> None:
        """Increment trial counter when neighbor candidate does not improve."""
        self.trial += 1

    def set_trial(self, val: int) -> None:
        """Explicitly set trial counter."""
        if val < 0:
            raise ValueError(f"Trial counter cannot be negative, got {val}")
        self.trial = int(val)

    def with_incremented_trial(self) -> FoodSource:
        """Return a copy of this FoodSource with trial incremented by 1."""
        return FoodSource(
            position=np.copy(self.position),
            cost=float(self.cost),
            fitness=float(self.fitness),
            trial=self.trial + 1,
        )
