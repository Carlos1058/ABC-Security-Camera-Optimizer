"""Abstract optimization problem definition and benchmark test functions."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

import numpy as np

from camera_optimizer.optimizer.bounds import Bounds, DimensionSpec, VariableType


class OptimizationProblem(ABC):
    """Abstract base class for problems solvable by SequentialABC."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Dimensionality D of the problem search space."""
        ...

    @property
    @abstractmethod
    def bounds(self) -> Bounds:
        """Search space boundary specifications for all D dimensions."""
        ...

    @abstractmethod
    def evaluate(self, x: np.ndarray) -> float:
        """Evaluate the objective cost to be minimized for a candidate vector x.

        Parameters
        ----------
        x : np.ndarray
            1D candidate vector of length D.

        Returns
        -------
        float
            Scalar cost (lower is better).
        """
        ...

    @abstractmethod
    def is_valid(self, x: np.ndarray) -> bool:
        """Check whether candidate vector x satisfies all domain-specific constraints."""
        ...

    @abstractmethod
    def sample_valid(self, rng: np.random.Generator) -> np.ndarray:
        """Generate a valid, feasible candidate solution vector."""
        ...


class SphereProblem(OptimizationProblem):
    """Classic continuous Sphere benchmark function: f(x) = sum(x_i^2).

    Global minimum: f(0, ..., 0) = 0.0.
    """

    def __init__(self, dimension: int = 5, lower: float = -5.12, upper: float = 5.12) -> None:
        if dimension <= 0:
            raise ValueError(f"Dimension must be positive, got {dimension}")
        self._dim = dimension
        self._bounds = Bounds.uniform_linear(dimension, lower, upper)

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def bounds(self) -> Bounds:
        return self._bounds

    def evaluate(self, x: np.ndarray) -> float:
        if len(x) != self._dim:
            raise ValueError(f"Expected vector of length {self._dim}, got {len(x)}")
        return float(np.sum(x ** 2))

    def is_valid(self, x: np.ndarray) -> bool:
        if len(x) != self._dim or not np.all(np.isfinite(x)):
            return False
        for j in range(self._dim):
            if not (self._bounds[j].lower <= x[j] <= self._bounds[j].upper):
                return False
        return True

    def sample_valid(self, rng: np.random.Generator) -> np.ndarray:
        return self._bounds.sample_vector(rng)


class RastriginProblem(OptimizationProblem):
    """Highly multimodal Rastrigin benchmark function:
    f(x) = 10 * D + sum(x_i^2 - 10 * cos(2 * pi * x_i)).

    Global minimum: f(0, ..., 0) = 0.0.
    """

    def __init__(self, dimension: int = 5, lower: float = -5.12, upper: float = 5.12) -> None:
        if dimension <= 0:
            raise ValueError(f"Dimension must be positive, got {dimension}")
        self._dim = dimension
        self._bounds = Bounds.uniform_linear(dimension, lower, upper)

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def bounds(self) -> Bounds:
        return self._bounds

    def evaluate(self, x: np.ndarray) -> float:
        if len(x) != self._dim:
            raise ValueError(f"Expected vector of length {self._dim}, got {len(x)}")
        d = self._dim
        cost = 10.0 * d + float(np.sum(x ** 2 - 10.0 * np.cos(2.0 * math.pi * x)))
        return float(cost)

    def is_valid(self, x: np.ndarray) -> bool:
        if len(x) != self._dim or not np.all(np.isfinite(x)):
            return False
        for j in range(self._dim):
            if not (self._bounds[j].lower <= x[j] <= self._bounds[j].upper):
                return False
        return True

    def sample_valid(self, rng: np.random.Generator) -> np.ndarray:
        return self._bounds.sample_vector(rng)
