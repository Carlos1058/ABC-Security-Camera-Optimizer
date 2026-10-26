"""Domain adapter binding camera deployment optimization to the SequentialABC engine."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from camera_optimizer.camera.pose import CameraPose, wrap_pi
from camera_optimizer.camera.profile import CameraProfile
from camera_optimizer.domain.floorplan import FloorPlan
from camera_optimizer.domain.grid import SamplingGrid
from camera_optimizer.geometry.point import Point2D
from camera_optimizer.objective.config import ObjectiveConfig
from camera_optimizer.objective.evaluator import (
    ConfigurationEvaluator,
    EvaluationResult,
)
from camera_optimizer.optimizer.bounds import Bounds, DimensionSpec, VariableType
from camera_optimizer.optimizer.problem import OptimizationProblem


class CameraOptimizationProblem(OptimizationProblem):
    """Optimization problem adapter for multi-camera placement in a 2D floor plan facility.

    This adapter bridges the generic, domain-agnostic `SequentialABC` metaheuristic engine
    with the physical simulation layer (`FloorPlan`, `SamplingGrid`, `ConfigurationEvaluator`).

    Search Space Formulation
    ------------------------
    Given K cameras, each candidate solution vector X has dimension D = 3K:
        X = [x_1, y_1, theta_1, x_2, y_2, theta_2, ..., x_K, y_K, theta_K]

    For each camera c in {0, ..., K-1}:
    - x_c in [xmin, xmax] (LINEAR continuous spatial dimension)
    - y_c in [ymin, ymax] (LINEAR continuous spatial dimension)
    - theta_c in [-pi, pi) (CIRCULAR_ANGLE dimension with minimal wrapped difference)

    Feasible Search Policy
    ----------------------
    As `ConfigurationEvaluator` returns `objective_cost = None` for infeasible poses, this
    adapter enforces a strict feasible-search policy:
    1. Initial population and scout reinitializations are generated via rejection sampling
       within the admissible interior space (guaranteeing valid camera positions).
    2. Candidate perturbations falling into walls, obstacles, or outer boundaries are
       detected by `is_valid(x)` and rejected by the ABC engine, which preserves the previous
       food source and increments its trial counter without evaluating the objective function.
    3. No artificial fitness penalty is needed, maintaining objective function purity.
    """

    def __init__(
        self,
        floorplan: FloorPlan,
        grid: SamplingGrid,
        num_cameras: int,
        profile: CameraProfile | None = None,
        config: ObjectiveConfig | None = None,
        max_sampling_attempts: int = 1000,
    ) -> None:
        """Initialize camera optimization problem adapter.

        Parameters
        ----------
        floorplan : FloorPlan
            Facility environment specifying boundary, walls, and obstacles.
        grid : SamplingGrid
            Discrete evaluation nodes with risk weights.
        num_cameras : int
            Exact number of cameras K to place (must be integer >= 1).
        profile : CameraProfile | None
            Camera sensor profile. Defaults to standard 90 deg, 10m profile if None.
        config : ObjectiveConfig | None
            Objective function weights and thresholds. Defaults to ObjectiveConfig() if None.
        max_sampling_attempts : int
            Maximum attempts allowed when sampling a feasible camera location before error.
        """
        if not isinstance(floorplan, FloorPlan):
            raise TypeError(f"Expected FloorPlan instance, got {type(floorplan).__name__}")
        if not isinstance(grid, SamplingGrid):
            raise TypeError(f"Expected SamplingGrid instance, got {type(grid).__name__}")

        if isinstance(num_cameras, bool) or not isinstance(num_cameras, int):
            raise TypeError(f"num_cameras must be an integer, got {type(num_cameras).__name__}")
        if num_cameras <= 0:
            raise ValueError(f"num_cameras must be a strictly positive integer (K >= 1), got {num_cameras}")

        if max_sampling_attempts <= 0:
            raise ValueError(f"max_sampling_attempts must be positive, got {max_sampling_attempts}")

        self._floorplan = floorplan
        self._grid = grid
        self._num_cameras = num_cameras
        self._profile = profile if profile is not None else CameraProfile()
        self._config = config if config is not None else ObjectiveConfig()
        self._max_sampling_attempts = max_sampling_attempts

        # Construct configuration evaluator
        self._evaluator = ConfigurationEvaluator(
            floorplan=self._floorplan,
            grid=self._grid,
            profile=self._profile,
            config=self._config,
        )

        # Build bounds for D = 3 * K dimensions
        specs: list[DimensionSpec] = []
        b = self._floorplan.boundary
        for _ in range(self._num_cameras):
            # x dimension
            specs.append(DimensionSpec(lower=b.xmin, upper=b.xmax, var_type=VariableType.LINEAR))
            # y dimension
            specs.append(DimensionSpec(lower=b.ymin, upper=b.ymax, var_type=VariableType.LINEAR))
            # theta dimension
            specs.append(DimensionSpec(lower=-math.pi, upper=math.pi, var_type=VariableType.CIRCULAR_ANGLE))

        self._bounds = Bounds(specs)

    @property
    def dimension(self) -> int:
        """Total dimensionality D = 3K of the problem search space."""
        return 3 * self._num_cameras

    @property
    def bounds(self) -> Bounds:
        """Search space boundary specifications for all 3K dimensions."""
        return self._bounds

    @property
    def num_cameras(self) -> int:
        """The fixed number of cameras K."""
        return self._num_cameras

    @property
    def floorplan(self) -> FloorPlan:
        """Physical facility floor plan."""
        return self._floorplan

    @property
    def grid(self) -> SamplingGrid:
        """Evaluation grid."""
        return self._grid

    @property
    def profile(self) -> CameraProfile:
        """Camera sensor profile."""
        return self._profile

    @property
    def evaluator(self) -> ConfigurationEvaluator:
        """The underlying configuration evaluator."""
        return self._evaluator

    @property
    def max_sampling_attempts(self) -> int:
        """Maximum attempts permitted for sampling feasible camera positions."""
        return self._max_sampling_attempts

    def vector_to_poses(self, x: np.ndarray) -> tuple[CameraPose, ...]:
        """Convert a 3K continuous vector into a tuple of K CameraPose objects.

        Parameters
        ----------
        x : np.ndarray
            1D numpy array of length 3K.

        Returns
        -------
        tuple[CameraPose, ...]
            Tuple containing exactly K CameraPose instances.
        """
        if not isinstance(x, np.ndarray):
            raise TypeError(f"Expected numpy.ndarray, got {type(x).__name__}")
        if x.ndim != 1 or len(x) != self.dimension:
            raise ValueError(
                f"Candidate vector must be 1D of length {self.dimension} (for K={self._num_cameras} cameras), "
                f"got shape {x.shape} (length {len(x)})"
            )
        if not np.all(np.isfinite(x)):
            raise ValueError("Candidate vector contains NaN or infinite values.")

        poses: list[CameraPose] = []
        for c in range(self._num_cameras):
            base = 3 * c
            px = float(x[base])
            py = float(x[base + 1])
            theta = wrap_pi(float(x[base + 2]))
            poses.append(CameraPose(px, py, theta))

        return tuple(poses)

    def poses_to_vector(self, poses: Sequence[CameraPose]) -> np.ndarray:
        """Convert a sequence of exactly K CameraPose objects into a 3K numpy array.

        Parameters
        ----------
        poses : Sequence[CameraPose]
            Sequence of K CameraPose instances.

        Returns
        -------
        np.ndarray
            1D array of shape (3K,).
        """
        if len(poses) != self._num_cameras:
            raise ValueError(
                f"Expected exactly {self._num_cameras} camera poses, got {len(poses)}"
            )

        vec = np.empty(self.dimension, dtype=np.float64)
        for c, pose in enumerate(poses):
            if not isinstance(pose, CameraPose):
                raise TypeError(f"Item at index {c} must be a CameraPose, got {type(pose).__name__}")
            base = 3 * c
            vec[base] = pose.x
            vec[base + 1] = pose.y
            vec[base + 2] = wrap_pi(pose.theta)

        return vec

    def is_valid(self, x: np.ndarray) -> bool:
        """Check whether candidate vector x satisfies all domain-specific constraints.

        Constraints checked:
        1. Correct shape (1D, length 3K).
        2. All entries are finite numbers.
        3. For every camera c in {0, ..., K-1}, its position (x_c, y_c) is strictly valid
           within the floor plan (interior space, not on perimeter, walls, or inside obstacles).
        """
        if not isinstance(x, np.ndarray):
            return False
        if x.ndim != 1 or len(x) != self.dimension:
            return False
        if not np.all(np.isfinite(x)):
            return False

        for c in range(self._num_cameras):
            base = 3 * c
            pt = Point2D(float(x[base]), float(x[base + 1]))
            if not self._floorplan.is_valid_camera_position(pt):
                return False

        return True

    def evaluate(self, x: np.ndarray) -> float:
        """Evaluate the objective cost f(X) for candidate vector x using ConfigurationEvaluator.

        Parameters
        ----------
        x : np.ndarray
            1D candidate vector of length 3K.

        Returns
        -------
        float
            Objective cost value in [0.0, 1.0 + lambda_def].
        """
        poses = self.vector_to_poses(x)
        result = self._evaluator.evaluate(poses)

        if not result.is_feasible:
            reasons = "; ".join(result.infeasibility_reasons)
            raise ValueError(f"Cannot evaluate infeasible configuration: {reasons}")

        if result.objective_cost is None:
            raise ValueError("ConfigurationEvaluator returned None objective cost for feasible configuration")

        return float(result.objective_cost)

    def sample_valid(self, rng: np.random.Generator) -> np.ndarray:
        """Generate a valid, feasible candidate solution vector with K cameras.

        Uses rejection sampling within the floor plan's bounding box. For each camera,
        random (x, y) coordinates are generated until `floorplan.is_valid_camera_position`
        returns True, up to `max_sampling_attempts`.

        Orientation theta is sampled uniformly in [-pi, pi).

        Returns
        -------
        np.ndarray
            Feasible candidate solution vector of length 3K.

        Raises
        ------
        RuntimeError
            If a feasible position cannot be found within `max_sampling_attempts` tries.
        """
        vec = np.empty(self.dimension, dtype=np.float64)
        b = self._floorplan.boundary

        for c in range(self._num_cameras):
            base = 3 * c
            found = False

            for _ in range(self._max_sampling_attempts):
                px = float(rng.uniform(b.xmin, b.xmax))
                py = float(rng.uniform(b.ymin, b.ymax))
                pt = Point2D(px, py)

                if self._floorplan.is_valid_camera_position(pt):
                    theta = float(rng.uniform(-math.pi, math.pi))
                    vec[base] = px
                    vec[base + 1] = py
                    vec[base + 2] = wrap_pi(theta)
                    found = True
                    break

            if not found:
                raise RuntimeError(
                    f"Failed to sample a feasible position for camera {c} after "
                    f"{self._max_sampling_attempts} attempts. Check floor plan obstacles and boundaries."
                )

        return vec

    def get_detailed_evaluation(self, x: np.ndarray) -> EvaluationResult:
        """Obtain complete EvaluationResult with CoverageMetrics for candidate vector x.

        Parameters
        ----------
        x : np.ndarray
            1D candidate vector of length 3K.

        Returns
        -------
        EvaluationResult
            Full evaluation report including geometric and probabilistic coverage.
        """
        poses = self.vector_to_poses(x)
        return self._evaluator.evaluate(poses)
