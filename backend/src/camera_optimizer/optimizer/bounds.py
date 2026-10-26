"""Dimension specification and boundary handling for continuous and circular variables."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

import numpy as np

from camera_optimizer.camera.pose import wrap_pi


class VariableType(Enum):
    """Classification of variable domains for metaheuristic perturbations."""

    LINEAR = "linear"
    CIRCULAR_ANGLE = "circular_angle"


@dataclass(frozen=True, slots=True)
class DimensionSpec:
    """Specification of a single optimization dimension.

    Attributes
    ----------
    lower : float
        Lower bound. For circular angles, typically -pi.
    upper : float
        Upper bound. For circular angles, typically pi.
    var_type : VariableType
        Domain topology (LINEAR or CIRCULAR_ANGLE).
    """

    lower: float
    upper: float
    var_type: VariableType = VariableType.LINEAR

    def __post_init__(self) -> None:
        """Validate dimension bounds."""
        try:
            l_val = float(self.lower)
            u_val = float(self.upper)
        except (TypeError, ValueError) as err:
            raise TypeError(f"Bounds must be numbers, got ({self.lower!r}, {self.upper!r})") from err

        if not (math.isfinite(l_val) and math.isfinite(u_val)):
            raise ValueError(f"Bounds must be finite, got ({l_val}, {u_val})")

        if l_val >= u_val:
            raise ValueError(f"Lower bound must be strictly less than upper bound: {l_val} >= {u_val}")

        if self.var_type == VariableType.CIRCULAR_ANGLE:
            if not (math.isclose(l_val, -math.pi, abs_tol=1e-7) and math.isclose(u_val, math.pi, abs_tol=1e-7)):
                raise ValueError(
                    f"CIRCULAR_ANGLE dimensions must declare the canonical domain [-pi, pi), "
                    f"got [{l_val}, {u_val})"
                )
            l_val = -math.pi
            u_val = math.pi

        object.__setattr__(self, "lower", l_val)
        object.__setattr__(self, "upper", u_val)

    def wrap_difference(self, val_i: float, val_k: float) -> float:
        """Calculate directed perturbation step (val_i - val_k).

        For LINEAR variables: standard algebraic subtraction (val_i - val_k).
        For CIRCULAR_ANGLE variables: minimal circular distance wrap_pi(val_i - val_k),
        preventing artificial jumps across the +/-pi discontinuity.
        """
        if self.var_type == VariableType.CIRCULAR_ANGLE:
            return wrap_pi(val_i - val_k)
        return val_i - val_k

    def apply_perturbation(self, base: float, delta: float, phi: float) -> float:
        """Apply neighbor perturbation v = base + phi * delta and enforce boundaries.

        For LINEAR variables: v = clamp(base + phi * delta, lower, upper).
        For CIRCULAR_ANGLE variables: v = wrap_pi(base + phi * delta) in [-pi, pi).
        """
        raw = base + phi * delta
        if self.var_type == VariableType.CIRCULAR_ANGLE:
            return wrap_pi(raw)
        return max(self.lower, min(self.upper, raw))

    def sample(self, rng: np.random.Generator) -> float:
        """Sample a single random value within the dimension's domain."""
        if self.var_type == VariableType.CIRCULAR_ANGLE:
            # Uniform angle in [-pi, pi)
            return float(rng.uniform(-math.pi, math.pi))
        return float(rng.uniform(self.lower, self.upper))


@dataclass(frozen=True, slots=True)
class Bounds:
    """Ordered collection of dimension specifications for a D-dimensional problem.

    Attributes
    ----------
    specs : tuple[DimensionSpec, ...]
        Sequence of dimension specifications.
    """

    specs: tuple[DimensionSpec, ...]

    def __init__(self, specs: Sequence[DimensionSpec]) -> None:
        """Initialize problem bounds from a sequence of DimensionSpec instances."""
        if len(specs) == 0:
            raise ValueError("Bounds must contain at least 1 DimensionSpec.")
        for idx, spec in enumerate(specs):
            if not isinstance(spec, DimensionSpec):
                raise TypeError(f"Item at index {idx} is not a DimensionSpec: {type(spec).__name__}")
        object.__setattr__(self, "specs", tuple(specs))

    @property
    def dim(self) -> int:
        """Dimension D of the search space."""
        return len(self.specs)

    def __len__(self) -> int:
        return len(self.specs)

    def __getitem__(self, index: int) -> DimensionSpec:
        return self.specs[index]

    @classmethod
    def uniform_linear(cls, dim: int, lower: float, upper: float) -> Bounds:
        """Create uniform linear bounds for all dimensions [lower, upper]."""
        if dim <= 0:
            raise ValueError(f"Dimension must be positive, got {dim}")
        specs = [DimensionSpec(lower=lower, upper=upper, var_type=VariableType.LINEAR) for _ in range(dim)]
        return cls(specs)

    def sample_vector(self, rng: np.random.Generator) -> np.ndarray:
        """Sample a D-dimensional vector uniformly within the bounds."""
        arr = np.empty(self.dim, dtype=np.float64)
        for j, spec in enumerate(self.specs):
            arr[j] = spec.sample(rng)
        return arr

    def perturb_dimension(
        self,
        x_i: np.ndarray,
        x_k: np.ndarray,
        dim_index: int,
        phi: float,
    ) -> np.ndarray:
        """Generate a neighbor candidate v by perturbing exactly one dimension dim_index.

        v_j = x_ij + phi * delta_j
        All other dimensions m != dim_index remain identical to x_i.
        """
        candidate = np.copy(x_i)
        spec = self.specs[dim_index]
        delta = spec.wrap_difference(float(x_i[dim_index]), float(x_k[dim_index]))
        candidate[dim_index] = spec.apply_perturbation(float(x_i[dim_index]), delta, phi)
        return candidate
