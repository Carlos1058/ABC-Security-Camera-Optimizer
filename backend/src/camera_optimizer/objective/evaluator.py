"""Evaluation of camera deployment configurations, feasibility, and objective cost."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from camera_optimizer.camera.pose import CameraPose
from camera_optimizer.camera.profile import CameraProfile
from camera_optimizer.coverage.evaluator import evaluate_multicamera_coverage
from camera_optimizer.coverage.metrics import CoverageMetrics
from camera_optimizer.domain.floorplan import FloorPlan
from camera_optimizer.domain.grid import SamplingGrid
from camera_optimizer.geometry.intersections import (
    DEFAULT_ANGULAR_TOLERANCE,
    DEFAULT_TOLERANCE,
)
from camera_optimizer.objective.config import ObjectiveConfig


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """Structured evaluation outcome for a specific camera deployment configuration.

    Attributes
    ----------
    is_feasible : bool
        True if all cameras satisfy physical placement constraints, False otherwise.
    infeasibility_reasons : list[str]
        Detailed diagnostic list of physical constraint violations when is_feasible is False.
    objective_cost : float | None
        Scalar objective cost f(X) to be minimized. Guaranteed to be finite and non-negative
        when is_feasible is True. Defined as None when configuration is infeasible.
    metrics : CoverageMetrics | None
        Detailed coverage metrics when computed; None if infeasible and not evaluated.
    camera_poses : tuple[CameraPose, ...]
        The evaluated camera poses.
    """

    is_feasible: bool
    infeasibility_reasons: list[str] = field(default_factory=list)
    objective_cost: float | None = None
    metrics: CoverageMetrics | None = None
    camera_poses: tuple[CameraPose, ...] = field(default_factory=tuple)

    @property
    def has_coverage_metrics(self) -> bool:
        """Check if detailed coverage metrics are available in this result."""
        return self.metrics is not None


class ConfigurationEvaluator:
    """Evaluates the feasibility, simulated optical coverage, and objective cost of camera layouts.

    Objective formulation:
        f(X) = (1.0 - C_risk) + lambda_def * Deficit_crit

    Where:
        - C_risk is the facility-wide risk-weighted detection coverage in [0.0, 1.0].
        - Deficit_crit is the normalized shortfall under T_crit for high-risk points in [0.0, 1.0].
        - lambda_def >= 0 is a configurable penalty scaling coefficient.
        - Physical feasibility is strictly verified against the facility geometry: a layout is
          feasible only if all cameras lie strictly in valid ceiling-mount free interior space.

    Architectural note for ABC optimization (Phase 3):
    While this general evaluator can evaluate configurations of arbitrary length
    (including 0 cameras to compute an unmonitored facility baseline), the optimization
    problem adapter in Phase 3 must strictly enforce solutions with exactly K cameras,
    rejecting or disallowing candidate vectors with fewer or more cameras.
    """

    def __init__(
        self,
        floorplan: FloorPlan,
        grid: SamplingGrid,
        profile: CameraProfile | None = None,
        config: ObjectiveConfig | None = None,
    ) -> None:
        """Initialize the layout evaluator with environment geometry and configuration.

        Parameters
        ----------
        floorplan : FloorPlan
            Facility environment including perimeter boundary, walls, and obstacles.
        grid : SamplingGrid
            Discrete evaluation nodes with risk weights.
        profile : CameraProfile | None
            Camera optical sensor profile. Defaults to a standard 90-degree 10m profile if None.
        config : ObjectiveConfig | None
            Objective cost weights and thresholds. Defaults to ObjectiveConfig() if None.
        """
        if not isinstance(floorplan, FloorPlan):
            raise TypeError(f"Expected FloorPlan instance, got {type(floorplan).__name__}")
        if not isinstance(grid, SamplingGrid):
            raise TypeError(f"Expected SamplingGrid instance, got {type(grid).__name__}")

        self._floorplan = floorplan
        self._grid = grid
        self._profile = profile if profile is not None else CameraProfile()
        self._config = config if config is not None else ObjectiveConfig()

        if not isinstance(self._profile, CameraProfile):
            raise TypeError(f"Expected CameraProfile, got {type(self._profile).__name__}")
        if not isinstance(self._config, ObjectiveConfig):
            raise TypeError(f"Expected ObjectiveConfig, got {type(self._config).__name__}")

    @property
    def floorplan(self) -> FloorPlan:
        """The underlying floor plan."""
        return self._floorplan

    @property
    def grid(self) -> SamplingGrid:
        """The evaluation sampling grid."""
        return self._grid

    @property
    def profile(self) -> CameraProfile:
        """The camera optical profile."""
        return self._profile

    @property
    def config(self) -> ObjectiveConfig:
        """The objective cost hyperparameters."""
        return self._config

    def check_feasibility(
        self,
        cameras: Sequence[CameraPose],
        tol: float = DEFAULT_TOLERANCE,
    ) -> tuple[bool, list[str]]:
        """Verify whether all camera poses in a configuration occupy valid physical positions.

        Parameters
        ----------
        cameras : Sequence[CameraPose]
            Sequence of camera poses to check.
        tol : float
            Spatial tolerance in meters.

        Returns
        -------
        tuple[bool, list[str]]
            (True, []) if all cameras are valid, or (False, [reason_1, ...]) if any camera fails.
        """
        reasons: list[str] = []

        for idx, cam in enumerate(cameras):
            if not isinstance(cam, CameraPose):
                raise TypeError(f"Camera at index {idx} must be a CameraPose instance, got {type(cam).__name__}")

            pt = cam.point
            if self._floorplan.is_valid_camera_position(pt, tol=tol):
                continue

            # Diagnose specific physical reason for violation
            b = self._floorplan.boundary
            if not (b.xmin + tol < pt.x < b.xmax - tol and b.ymin + tol < pt.y < b.ymax - tol):
                reasons.append(
                    f"Camera {idx} at ({pt.x:.4f}, {pt.y:.4f}) is outside or on perimeter boundary "
                    f"[{b.xmin}, {b.xmax}] x [{b.ymin}, {b.ymax}]"
                )
                continue

            # Check obstacle containment
            in_obstacle = False
            for o_idx, obs in enumerate(self._floorplan.obstacles):
                if obs.contains_point(pt, include_boundary=True, tol=tol):
                    reasons.append(
                        f"Camera {idx} at ({pt.x:.4f}, {pt.y:.4f}) is inside or on boundary of obstacle {o_idx}"
                    )
                    in_obstacle = True
                    break
            if in_obstacle:
                continue

            # Check wall intersection
            for w_idx, wall in enumerate(self._floorplan.walls):
                if wall.contains_point(pt, tol=tol):
                    reasons.append(
                        f"Camera {idx} at ({pt.x:.4f}, {pt.y:.4f}) coincides with interior wall {w_idx}"
                    )
                    break

        return (len(reasons) == 0, reasons)

    def evaluate(
        self,
        cameras: Sequence[CameraPose],
        evaluate_infeasible_metrics: bool = False,
        tol: float = DEFAULT_TOLERANCE,
        angular_tol: float = DEFAULT_ANGULAR_TOLERANCE,
    ) -> EvaluationResult:
        """Evaluate a layout of cameras, computing feasibility, coverage metrics, and objective cost.

        Parameters
        ----------
        cameras : Sequence[CameraPose]
            Ordered configuration of K camera poses.
        evaluate_infeasible_metrics : bool
            If True, calculates coverage metrics even when the layout has physical violations
            (e.g. for post-hoc diagnostic inspection), but objective_cost remains None.
        tol : float
            Spatial tolerance in meters.
        angular_tol : float
            Angular tolerance in radians.

        Returns
        -------
        EvaluationResult
            Complete evaluation record with feasibility status, objective cost (if feasible),
            and detailed coverage metrics.
        """
        is_feasible, reasons = self.check_feasibility(cameras, tol=tol)
        poses_tuple = tuple(cameras)

        if not is_feasible:
            metrics = None
            if evaluate_infeasible_metrics:
                metrics = evaluate_multicamera_coverage(
                    cameras=poses_tuple,
                    profile=self._profile,
                    grid=self._grid,
                    floorplan=self._floorplan,
                    t_crit=self._config.t_crit,
                    tol=tol,
                    angular_tol=angular_tol,
                )
            return EvaluationResult(
                is_feasible=False,
                infeasibility_reasons=reasons,
                objective_cost=None,
                metrics=metrics,
                camera_poses=poses_tuple,
            )

        # Layout is feasible: compute coverage metrics and objective cost
        metrics = evaluate_multicamera_coverage(
            cameras=poses_tuple,
            profile=self._profile,
            grid=self._grid,
            floorplan=self._floorplan,
            t_crit=self._config.t_crit,
            tol=tol,
            angular_tol=angular_tol,
        )

        c_risk = metrics.risk_weighted_coverage
        deficit_crit = metrics.critical_deficit

        # Minimization objective function:
        # f(X) = (1 - C_risk) + lambda_def * Deficit_crit
        objective_cost = (1.0 - c_risk) + self._config.lambda_def * deficit_crit
        if not math.isfinite(objective_cost):
            raise ValueError(f"Computed objective cost is not finite: {objective_cost}")

        return EvaluationResult(
            is_feasible=True,
            infeasibility_reasons=[],
            objective_cost=max(0.0, float(objective_cost)),
            metrics=metrics,
            camera_poses=poses_tuple,
        )
