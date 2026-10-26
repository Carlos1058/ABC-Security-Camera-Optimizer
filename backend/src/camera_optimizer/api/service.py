"""Service and domain-bridge layer for the ABC Security Camera Optimizer API.

Handles:
- Conversion between Pydantic DTOs and internal domain models.
- Deep geometric and hyperparameter validation.
- Concurrency control with a non-blocking execution lock (single-instance sequential guarantee).
- Global execution budget and population history resource enforcement.
- Concrete PRNG seed generation and determinism guarantees (Defecto B & C).
- Strict non-finite number and overflow prevention (Defecto A).
- Real sequential execution of SequentialABC and ConfigurationEvaluator.
- Pure JSON-compatible transformation of all output telemetry and metrics.
"""

from __future__ import annotations

import math
import secrets
import threading
import time
from typing import Any

import numpy as np

from camera_optimizer.api.limits import DEFAULT_LIMITS, ResourceLimits
from camera_optimizer.api.schemas import (
    CameraPoseDTO,
    CameraProfileDTO,
    CoverageEvaluationResponse,
    CoverageGridNodeDTO,
    CoverageMetricsDTO,
    CycleSnapshotDTO,
    FoodSourceDTO,
    OptimizationConfigDTO,
    OptimizationResultDTO,
    PointDTO,
    ScenarioDTO,
    ValidationResponse,
)
from camera_optimizer.camera.pose import CameraPose, wrap_pi
from camera_optimizer.camera.profile import CameraProfile
from camera_optimizer.domain.floorplan import FloorPlan
from camera_optimizer.domain.grid import SamplingGrid
from camera_optimizer.domain.obstacle import ObstaclePolygon
from camera_optimizer.domain.risk_zone import RiskZone
from camera_optimizer.domain.wall import WallSegment
from camera_optimizer.geometry.bounding_box import BoundingBox
from camera_optimizer.geometry.intersections import DEFAULT_TOLERANCE
from camera_optimizer.geometry.point import Point2D
from camera_optimizer.geometry.polygon import Polygon2D
from camera_optimizer.objective.config import ObjectiveConfig
from camera_optimizer.objective.evaluator import ConfigurationEvaluator
from camera_optimizer.optimizer.camera_problem import CameraOptimizationProblem
from camera_optimizer.optimizer.config import ABCConfig
from camera_optimizer.optimizer.sequential_abc import SequentialABC


class OptimizationBusyError(Exception):
    """Raised when an optimization run is requested while another is actively executing."""


class OptimizationService:
    """Singleton-style execution coordinator guaranteeing strict sequential execution."""

    def __init__(self, limits: ResourceLimits = DEFAULT_LIMITS) -> None:
        self.limits = limits
        self._lock = threading.Lock()
        self._active_run_id: str | None = None
        self._run_start_time: float | None = None

    @property
    def is_busy(self) -> bool:
        """Return True if an optimization is currently in progress."""
        return self._lock.locked()

    def get_status_details(self) -> dict[str, Any]:
        """Return diagnostic operational status of the service."""
        locked = self._lock.locked()
        elapsed = time.perf_counter() - self._run_start_time if (locked and self._run_start_time) else None
        return {
            "is_busy": locked,
            "active_run_id": self._active_run_id if locked else None,
            "elapsed_seconds": round(elapsed, 2) if elapsed is not None else None,
        }

    # -------------------------------------------------------------------------
    # Domain Object Builders
    # -------------------------------------------------------------------------

    @staticmethod
    def build_bounding_box(scenario: ScenarioDTO) -> BoundingBox:
        """Construct domain BoundingBox from scenario coordinates."""
        return BoundingBox(
            xmin=scenario.xmin,
            xmax=scenario.xmax,
            ymin=scenario.ymin,
            ymax=scenario.ymax,
        )

    @staticmethod
    def build_walls(scenario: ScenarioDTO) -> list[WallSegment]:
        """Construct domain WallSegment list from scenario."""
        walls: list[WallSegment] = []
        for w in scenario.walls:
            p1 = Point2D(w.start.x, w.start.y)
            p2 = Point2D(w.end.x, w.end.y)
            walls.append(WallSegment(start=p1, end=p2, is_opaque=w.is_opaque))
        return walls

    @staticmethod
    def build_obstacles(scenario: ScenarioDTO) -> list[ObstaclePolygon]:
        """Construct domain ObstaclePolygon list from scenario."""
        obstacles: list[ObstaclePolygon] = []
        for obs in scenario.obstacles:
            vertices = [Point2D(p.x, p.y) for p in obs.vertices]
            obstacles.append(ObstaclePolygon(vertices=vertices))
        return obstacles

    @staticmethod
    def build_risk_zones(scenario: ScenarioDTO) -> list[RiskZone]:
        """Construct domain RiskZone list from scenario."""
        zones: list[RiskZone] = []
        for rz in scenario.risk_zones:
            vertices = [Point2D(p.x, p.y) for p in rz.vertices]
            zones.append(RiskZone(polygon_or_vertices=vertices, weight=rz.weight, name=rz.name))
        return zones

    def build_floorplan(self, scenario: ScenarioDTO) -> FloorPlan:
        """Construct domain FloorPlan from ScenarioDTO."""
        bbox = self.build_bounding_box(scenario)
        walls = self.build_walls(scenario)
        obstacles = self.build_obstacles(scenario)
        risk_zones = self.build_risk_zones(scenario)
        return FloorPlan(
            boundary=bbox,
            walls=walls,
            obstacles=obstacles,
            risk_zones=risk_zones,
        )

    def build_sampling_grid(self, floorplan: FloorPlan, resolution: float) -> SamplingGrid:
        """Generate evaluation grid with max cell limit safeguard."""
        return SamplingGrid.generate(
            floorplan=floorplan,
            resolution=resolution,
            max_cells=self.limits.max_grid_cells,
            tol=DEFAULT_TOLERANCE,
        )

    @staticmethod
    def build_camera_profile(dto: CameraProfileDTO) -> CameraProfile:
        """Construct domain CameraProfile from DTO."""
        return CameraProfile(
            Rmin=dto.Rmin,
            Rmax=dto.Rmax,
            fov=dto.FOV,
            p0=dto.p0,
            beta_d=dto.beta_d,
            beta_theta=dto.beta_theta,
        )

    @staticmethod
    def build_objective_config(dto: OptimizationConfigDTO) -> ObjectiveConfig:
        """Construct domain ObjectiveConfig from DTO."""
        return ObjectiveConfig(
            lambda_def=dto.lambda_def,
            t_crit=dto.Tcrit,
        )

    @staticmethod
    def build_abc_config(dto: OptimizationConfigDTO, effective_seed: int | str | None = None) -> ABCConfig:
        """Construct domain ABCConfig from DTO using a concrete effective seed."""
        if effective_seed is not None:
            seed = int(effective_seed)
        elif dto.seed is not None:
            seed = int(dto.seed)
        else:
            seed = secrets.randbits(63)
        return ABCConfig(
            num_food_sources=dto.SN,
            max_cycles=dto.max_cycles,
            limit=dto.limit,
            seed=seed,
            record_trace=False,
            record_population=dto.record_population,
        )

    # -------------------------------------------------------------------------
    # Comprehensive Validation
    # -------------------------------------------------------------------------

    def validate_scenario(
        self,
        scenario: ScenarioDTO,
        profile: CameraProfileDTO | None = None,
        config: OptimizationConfigDTO | None = None,
    ) -> ValidationResponse:
        """Validate all spatial geometries, optical parameters, colony settings, and computational budget.

        Returns clear, human-understandable error messages for every violation.
        Guarantees that any configuration that passes validation is executable without unexpected errors.
        """
        errors: list[str] = []
        warnings: list[str] = []
        details: dict[str, Any] = {}

        # 1. Bounds & finitude validation (Defecto A)
        for name, val in [
            ("xmin", scenario.xmin),
            ("xmax", scenario.xmax),
            ("ymin", scenario.ymin),
            ("ymax", scenario.ymax),
        ]:
            if not math.isfinite(val):
                errors.append(f"Scenario boundary '{name}' must be a finite number, got {val}.")

        width = scenario.xmax - scenario.xmin
        height = scenario.ymax - scenario.ymin

        if not math.isfinite(width) or not math.isfinite(height):
            errors.append("Scenario dimensions (width or height) resulted in non-finite values.")
        else:
            if width <= 0.0:
                errors.append(f"Invalid room width: xmax ({scenario.xmax}) must be strictly greater than xmin ({scenario.xmin}).")
            elif width < self.limits.min_room_dim or width > self.limits.max_room_dim:
                errors.append(
                    f"Room width ({width:.2f}m) exceeds allowable bounds "
                    f"[{self.limits.min_room_dim}m, {self.limits.max_room_dim}m]."
                )

            if height <= 0.0:
                errors.append(f"Invalid room height: ymax ({scenario.ymax}) must be strictly greater than ymin ({scenario.ymin}).")
            elif height < self.limits.min_room_dim or height > self.limits.max_room_dim:
                errors.append(
                    f"Room height ({height:.2f}m) exceeds allowable bounds "
                    f"[{self.limits.min_room_dim}m, {self.limits.max_room_dim}m]."
                )

        # 2. Grid resolution & cell limits (Defecto A: no int() on non-finite)
        res = scenario.grid_resolution
        if not math.isfinite(res) or res <= 0.0:
            errors.append(f"Grid resolution must be a finite positive number, got {res}.")
        elif res < self.limits.min_grid_resolution or res > self.limits.max_grid_resolution:
            errors.append(
                f"Grid resolution ({res:.3f}m) is outside acceptable bounds "
                f"[{self.limits.min_grid_resolution}m, {self.limits.max_grid_resolution}m]."
            )
        elif math.isfinite(width) and math.isfinite(height) and width > 0 and height > 0:
            est_cells = (width / res) * (height / res)
            if math.isfinite(est_cells):
                details["estimated_grid_cells"] = int(est_cells)
                if est_cells > self.limits.max_grid_cells:
                    errors.append(
                        f"Requested grid resolution {res}m would produce approximately {int(est_cells):,} cells, "
                        f"exceeding the safety limit of {self.limits.max_grid_cells:,} cells."
                    )
            else:
                errors.append("Estimated grid cell count overflowed to infinity.")

        # 3. Walls complexity & containment
        if len(scenario.walls) > self.limits.max_walls:
            errors.append(
                f"Scenario wall count ({len(scenario.walls)}) exceeds maximum limit of {self.limits.max_walls}."
            )

        for idx, w in enumerate(scenario.walls):
            for pt_name, pt in [("start", w.start), ("end", w.end)]:
                if not (math.isfinite(pt.x) and math.isfinite(pt.y)):
                    errors.append(f"Wall at index {idx} has non-finite {pt_name} coordinates.")

            dx = w.end.x - w.start.x
            dy = w.end.y - w.start.y
            length = math.hypot(dx, dy)
            if not math.isfinite(length) or length < DEFAULT_TOLERANCE:
                errors.append(f"Wall at index {idx} is degenerate (start and end points are identical within tolerance).")

            for pt_name, pt in [("start", w.start), ("end", w.end)]:
                if not (
                    scenario.xmin - DEFAULT_TOLERANCE <= pt.x <= scenario.xmax + DEFAULT_TOLERANCE
                    and scenario.ymin - DEFAULT_TOLERANCE <= pt.y <= scenario.ymax + DEFAULT_TOLERANCE
                ):
                    errors.append(
                        f"Wall at index {idx} {pt_name} endpoint ({pt.x}, {pt.y}) lies outside the facility boundary."
                    )

        # 4. Obstacles complexity, topology & containment
        if len(scenario.obstacles) > self.limits.max_obstacles:
            errors.append(
                f"Scenario obstacle count ({len(scenario.obstacles)}) exceeds maximum limit of {self.limits.max_obstacles}."
            )

        for idx, obs in enumerate(scenario.obstacles):
            n_v = len(obs.vertices)
            if n_v < 3:
                errors.append(f"Obstacle at index {idx} has {n_v} vertices; minimum required is 3.")
            elif n_v > self.limits.max_vertices_per_polygon:
                errors.append(
                    f"Obstacle at index {idx} has {n_v} vertices, exceeding maximum limit of {self.limits.max_vertices_per_polygon}."
                )
            else:
                for v_idx, p in enumerate(obs.vertices):
                    if not (math.isfinite(p.x) and math.isfinite(p.y)):
                        errors.append(f"Obstacle at index {idx} vertex {v_idx} has non-finite coordinates.")

                pts = [Point2D(p.x, p.y) for p in obs.vertices]
                try:
                    poly = Polygon2D(pts)
                    if poly.area <= DEFAULT_TOLERANCE:
                        errors.append(f"Obstacle at index {idx} has zero or negligible area ({poly.area}).")
                    bbox = poly.bounding_box
                    if (
                        bbox.xmin < scenario.xmin - DEFAULT_TOLERANCE
                        or bbox.xmax > scenario.xmax + DEFAULT_TOLERANCE
                        or bbox.ymin < scenario.ymin - DEFAULT_TOLERANCE
                        or bbox.ymax > scenario.ymax + DEFAULT_TOLERANCE
                    ):
                        errors.append(f"Obstacle at index {idx} extends outside the facility boundary.")
                except ValueError as err:
                    errors.append(f"Obstacle at index {idx} is topologically invalid: {err}")

        # 5. Risk zones complexity & containment
        if len(scenario.risk_zones) > self.limits.max_risk_zones:
            errors.append(
                f"Risk zone count ({len(scenario.risk_zones)}) exceeds maximum limit of {self.limits.max_risk_zones}."
            )

        for idx, rz in enumerate(scenario.risk_zones):
            if not math.isfinite(rz.weight) or rz.weight < 1.0:
                errors.append(f"Risk zone at index {idx} has invalid weight {rz.weight}; must be a finite number >= 1.0.")
            n_v = len(rz.vertices)
            if n_v < 3:
                errors.append(f"Risk zone at index {idx} has {n_v} vertices; minimum required is 3.")
            elif n_v > self.limits.max_vertices_per_polygon:
                errors.append(
                    f"Risk zone at index {idx} has {n_v} vertices, exceeding maximum limit of {self.limits.max_vertices_per_polygon}."
                )
            else:
                for v_idx, p in enumerate(rz.vertices):
                    if not (math.isfinite(p.x) and math.isfinite(p.y)):
                        errors.append(f"Risk zone at index {idx} vertex {v_idx} has non-finite coordinates.")

                pts = [Point2D(p.x, p.y) for p in rz.vertices]
                try:
                    poly = Polygon2D(pts)
                    bbox = poly.bounding_box
                    if (
                        bbox.xmin < scenario.xmin - DEFAULT_TOLERANCE
                        or bbox.xmax > scenario.xmax + DEFAULT_TOLERANCE
                        or bbox.ymin < scenario.ymin - DEFAULT_TOLERANCE
                        or bbox.ymax > scenario.ymax + DEFAULT_TOLERANCE
                    ):
                        errors.append(f"Risk zone at index {idx} extends outside the facility boundary.")
                except ValueError as err:
                    errors.append(f"Risk zone at index {idx} is topologically invalid: {err}")

        # 6. Profile validation (Defecto A: check finitude of all parameters)
        if profile is not None:
            for name, val in [
                ("Rmin", profile.Rmin),
                ("Rmax", profile.Rmax),
                ("FOV", profile.FOV),
                ("p0", profile.p0),
                ("beta_d", profile.beta_d),
                ("beta_theta", profile.beta_theta),
            ]:
                if not math.isfinite(val):
                    errors.append(f"Camera profile parameter '{name}' must be a finite number, got {val}.")

            if profile.Rmin < 0.0:
                errors.append(f"Camera profile Rmin must be >= 0.0, got {profile.Rmin}.")
            if profile.Rmax <= profile.Rmin:
                errors.append(f"Camera profile Rmax ({profile.Rmax}) must be strictly greater than Rmin ({profile.Rmin}).")
            if not (0.0 < profile.FOV <= 2.0 * math.pi):
                errors.append(f"Camera profile FOV must be in (0, 2*pi] radians, got {profile.FOV}.")
            if not (0.0 < profile.p0 <= 1.0):
                errors.append(f"Camera profile p0 must be in (0, 1.0], got {profile.p0}.")
            if profile.beta_d < 0.0:
                errors.append(f"Camera profile beta_d must be >= 0.0, got {profile.beta_d}.")
            if profile.beta_theta < 0.0:
                errors.append(f"Camera profile beta_theta must be >= 0.0, got {profile.beta_theta}.")

        # 7. Config validation (Defecto B & C: check seed domain and bounds)
        if config is not None:
            if config.seed is not None:
                valid_seed = False
                if isinstance(config.seed, str):
                    s = config.seed.strip()
                    if s.isdigit() and 0 <= int(s) < 2**64:
                        valid_seed = True
                elif isinstance(config.seed, int) and not isinstance(config.seed, bool):
                    if 0 <= config.seed < 2**64:
                        valid_seed = True

                if not valid_seed:
                    errors.append(
                        f"PRNG seed must be a non-negative integer or decimal string within [0, 2^64 - 1], got {config.seed!r}."
                    )
            if not (self.limits.min_cameras <= config.K <= self.limits.max_cameras):
                errors.append(
                    f"Number of cameras K ({config.K}) is outside permitted range "
                    f"[{self.limits.min_cameras}, {self.limits.max_cameras}]."
                )
            if not (self.limits.min_food_sources <= config.SN <= self.limits.max_food_sources):
                errors.append(
                    f"Number of food sources SN ({config.SN}) is outside permitted range "
                    f"[{self.limits.min_food_sources}, {self.limits.max_food_sources}]."
                )
            if not (self.limits.min_cycles <= config.max_cycles <= self.limits.max_cycles):
                errors.append(
                    f"Maximum cycles ({config.max_cycles}) is outside permitted range "
                    f"[{self.limits.min_cycles}, {self.limits.max_cycles}]."
                )
            if config.limit is not None and not (self.limits.min_limit <= config.limit <= self.limits.max_limit):
                errors.append(
                    f"Scout limit ({config.limit}) is outside permitted range "
                    f"[{self.limits.min_limit}, {self.limits.max_limit}]."
                )
            if not math.isfinite(config.lambda_def):
                errors.append(f"lambda_def must be a finite number, got {config.lambda_def}.")
            elif config.lambda_def < 0.0:
                errors.append(f"lambda_def must be >= 0.0, got {config.lambda_def}.")
            if not math.isfinite(config.Tcrit):
                errors.append(f"Tcrit must be a finite number, got {config.Tcrit}.")
            elif not (0.0 < config.Tcrit <= 1.0):
                errors.append(f"Tcrit must be in (0, 1.0], got {config.Tcrit}.")

        # 8. Structural feasibility and global budget check (Defecto D)
        if not errors:
            try:
                floorplan = self.build_floorplan(scenario)
                grid = self.build_sampling_grid(floorplan, scenario.grid_resolution)
                actual_nodes = len(grid.nodes)
                details["actual_grid_nodes"] = actual_nodes
                if actual_nodes == 0:
                    errors.append(
                        "Discretization produced 0 evaluation nodes. Free space may be entirely occupied by obstacles."
                    )
                else:
                    # Global computational workload budget check
                    if config is not None:
                        nfe_upper = self.limits.estimate_nfe_upper(config.SN, config.max_cycles)
                        work_upper = self.limits.estimate_work_upper(
                            sn=config.SN,
                            max_cycles=config.max_cycles,
                            k=config.K,
                            grid_points=actual_nodes,
                        )
                        details["estimated_nfe_upper"] = nfe_upper
                        details["estimated_work_upper"] = work_upper

                        if work_upper > self.limits.max_work_budget:
                            errors.append(
                                f"Global computational work budget exceeded: estimated workload of {work_upper:,.0f} units "
                                f"exceeds maximum allowed budget of {self.limits.max_work_budget:,.0f}. "
                                f"Please reduce grid resolution, number of cameras K, food sources SN, or max cycles."
                            )

                        # Population history memory budget check
                        if config.record_population:
                            pop_elements = self.limits.estimate_population_history_elements(
                                max_cycles=config.max_cycles,
                                sn=config.SN,
                                k=config.K,
                            )
                            details["estimated_population_history_elements"] = pop_elements
                            if pop_elements > self.limits.max_population_history_elements:
                                errors.append(
                                    f"Population history size limit exceeded: requested {pop_elements:,} history elements "
                                    f"exceeds safety limit of {self.limits.max_population_history_elements:,}. "
                                    f"Disable record_population or reduce max_cycles, SN, or K."
                                )
            except Exception as err:
                errors.append(f"Spatial compilation failed: {err}")

        is_valid = len(errors) == 0
        return ValidationResponse(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details,
        )

    # -------------------------------------------------------------------------
    # Optimization Execution
    # -------------------------------------------------------------------------

    def run_optimization(
        self,
        scenario: ScenarioDTO,
        profile_dto: CameraProfileDTO,
        config_dto: OptimizationConfigDTO,
    ) -> OptimizationResultDTO:
        """Execute real, strictly sequential ABC camera optimization.

        Guarantees:
        - Mutual exclusion via self._lock: raises OptimizationBusyError if another run is active.
        - Synchronous termination before returning response.
        - Full numerical conversion to native JSON-serializable types.
        - Effective reproducible concrete seed returned (Defecto B).
        - Centralized validation enforcement (Defecto C).
        """
        # 1. Acquire execution lock without blocking
        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            raise OptimizationBusyError(
                "Another optimization run is currently executing. "
                "The ABC engine is strictly sequential and handles one optimization at a time."
            )

        run_id = f"abc-run-{int(time.time() * 1000)}"
        self._active_run_id = run_id
        self._run_start_time = time.perf_counter()

        try:
            # 2. Centralized validation check (Defecto C)
            val = self.validate_scenario(scenario, profile_dto, config_dto)
            if not val.is_valid:
                raise ValueError("Scenario validation failed: " + "; ".join(val.errors))

            # 3. Establish concrete reproducible effective seed (Defecto B)
            if config_dto.seed is not None:
                effective_seed = int(config_dto.seed)
            else:
                effective_seed = int(secrets.randbits(63))

            # 4. Build domain components
            floorplan = self.build_floorplan(scenario)
            grid = self.build_sampling_grid(floorplan, scenario.grid_resolution)
            profile = self.build_camera_profile(profile_dto)
            obj_config = self.build_objective_config(config_dto)
            abc_config = self.build_abc_config(config_dto, effective_seed=effective_seed)

            # 5. Construct problem adapter and optimizer
            problem = CameraOptimizationProblem(
                floorplan=floorplan,
                grid=grid,
                num_cameras=config_dto.K,
                profile=profile,
                config=obj_config,
            )
            optimizer = SequentialABC(problem=problem, config=abc_config)

            # 6. Run sequential optimization
            output = optimizer.optimize()

            # 7. Extract initial best and final best configurations
            initial_record = output.history[0]
            initial_poses_domain = problem.vector_to_poses(initial_record.best_position)
            initial_best_poses = [
                CameraPoseDTO(
                    x=float(p.x),
                    y=float(p.y),
                    theta=float(p.theta),
                    theta_deg=float(math.degrees(p.theta)),
                )
                for p in initial_poses_domain
            ]
            initial_best_cost = float(initial_record.best_cost)

            final_poses_domain = problem.vector_to_poses(output.best_source.position)
            final_best_poses = [
                CameraPoseDTO(
                    x=float(p.x),
                    y=float(p.y),
                    theta=float(p.theta),
                    theta_deg=float(math.degrees(p.theta)),
                )
                for p in final_poses_domain
            ]
            final_best_cost = float(output.best_cost)

            # 8. Evaluate detailed coverage metrics for final best solution
            eval_res = problem.evaluator.evaluate(final_poses_domain)
            if eval_res.metrics is None:
                raise RuntimeError("Failed to compute coverage metrics for final best solution.")

            m = eval_res.metrics
            coverage_dto = CoverageMetricsDTO(
                num_eval_points=int(m.num_eval_points),
                num_covered_points=int(m.num_covered_points),
                geometric_coverage_ratio=float(m.geometric_coverage_ratio),
                geometric_coverage_percent=float(m.geometric_coverage_percent),
                mean_probabilistic_coverage=float(m.mean_probabilistic_coverage),
                risk_weighted_coverage=float(m.risk_weighted_coverage),
                num_critical_points=int(m.num_critical_points),
                critical_deficit=float(m.critical_deficit),
            )

            # 9. Transform history and population snapshots
            best_cost_per_cycle = [float(rec.best_cost) for rec in output.history]
            mean_cost_per_cycle = [float(rec.mean_population_cost) for rec in output.history]

            history_snapshots: list[CycleSnapshotDTO] = []
            for rec in output.history:
                rec_poses = [
                    CameraPoseDTO(
                        x=float(p.x),
                        y=float(p.y),
                        theta=float(p.theta),
                        theta_deg=float(math.degrees(p.theta)),
                    )
                    for p in problem.vector_to_poses(rec.best_position)
                ]

                pop_dto: list[FoodSourceDTO] | None = None
                if rec.population is not None:
                    pop_dto = []
                    for src in rec.population:
                        src_poses = [
                            CameraPoseDTO(
                                x=float(p.x),
                                y=float(p.y),
                                theta=float(p.theta),
                                theta_deg=float(math.degrees(p.theta)),
                            )
                            for p in problem.vector_to_poses(src.position)
                        ]
                        pop_dto.append(
                            FoodSourceDTO(
                                position=[float(v) for v in src.position],
                                poses=src_poses,
                                cost=float(src.cost),
                                fitness=float(src.fitness),
                                trial=int(src.trial),
                            )
                        )

                history_snapshots.append(
                    CycleSnapshotDTO(
                        cycle=int(rec.cycle),
                        best_cost=float(rec.best_cost),
                        best_poses=rec_poses,
                        mean_population_cost=float(rec.mean_population_cost),
                        improvements_count=int(rec.improvements_count),
                        scout_resets=int(rec.scout_resets),
                        population=pop_dto,
                    )
                )

            # 10. Return structured OptimizationResultDTO
            return OptimizationResultDTO(
                scenario=scenario,
                profile=profile_dto,
                config=config_dto,
                effective_seed=str(effective_seed),
                dimension=int(problem.dimension),
                initial_best_cost=initial_best_cost,
                initial_best_poses=initial_best_poses,
                final_best_cost=final_best_cost,
                final_best_poses=final_best_poses,
                best_cost_per_cycle=best_cost_per_cycle,
                mean_cost_per_cycle=mean_cost_per_cycle,
                coverage_metrics=coverage_dto,
                total_evaluations=int(output.total_evaluations),
                total_proposals=int(output.total_proposals),
                rejected_infeasible_proposals=int(output.rejected_infeasible_proposals),
                total_scout_resets=int(output.total_scout_resets),
                execution_time_seconds=float(output.execution_time_seconds),
                history=history_snapshots,
                population_history_available=config_dto.record_population,
            )

        finally:
            self._active_run_id = None
            self._run_start_time = None
            self._lock.release()

    def evaluate_coverage(
        self,
        scenario: ScenarioDTO,
        profile_dto: CameraProfileDTO,
        cameras_dto: list[CameraPoseDTO],
        lambda_def: float = 1.0,
        t_crit: float = 0.8,
    ) -> CoverageEvaluationResponse:
        """Evaluate spatial simulated coverage for a given camera configuration.

        Validates facility geometry, camera poses, obstacles, and objective parameters.
        Reuses OptimizationService domain builders, ConfigurationEvaluator,
        CoverageMetrics.point_probabilities, and CoverageMetrics.point_binary_covered.
        Enforces mutual exclusion with active ABC optimization and pre-raytracing workload limits.
        """
        # 0. Shared mutual exclusion lock (strict sequential guarantee)
        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            raise OptimizationBusyError(
                "Another optimization or coverage evaluation is currently executing. "
                "The mathematical engine is strictly sequential."
            )

        run_id = f"coverage-eval-{int(time.time() * 1000)}"
        self._active_run_id = run_id
        self._run_start_time = time.perf_counter()

        try:
            # 1. Validate camera configuration bounds: 1 <= K <= max_cameras
            k = len(cameras_dto)
            if k < self.limits.min_cameras or k > self.limits.max_cameras:
                raise ValueError(
                    f"Number of cameras ({k}) must be between {self.limits.min_cameras} and {self.limits.max_cameras}."
                )

            # 2. Validate scenario and profile
            val_res = self.validate_scenario(scenario, profile_dto)
            if not val_res.is_valid:
                raise ValueError(f"Scenario validation failed: {'; '.join(val_res.errors)}")

            # 3. Pre-raytracing computational workload budget check
            width = scenario.xmax - scenario.xmin
            height = scenario.ymax - scenario.ymin
            res = scenario.grid_resolution
            est_nodes = (width / res) * (height / res)
            num_blocking_segments = len(scenario.walls) + sum(len(obs.vertices) for obs in scenario.obstacles)
            coverage_work = self.limits.estimate_coverage_work(k, int(est_nodes), num_blocking_segments)
            if coverage_work > self.limits.max_coverage_work_budget:
                raise ValueError(
                    f"Coverage evaluation workload budget exceeded: estimated workload of {coverage_work:,.0f} units "
                    f"exceeds maximum allowed single-evaluation budget of {self.limits.max_coverage_work_budget:,.0f} units. "
                    f"Please reduce the number of cameras K, facility area, or increase grid resolution."
                )

            # 4. Validate objective hyperparameters
            if not math.isfinite(lambda_def) or lambda_def < 0.0:
                raise ValueError(f"lambda_def must be a finite non-negative number, got {lambda_def}")
            if not math.isfinite(t_crit) or not (0.0 < t_crit <= 1.0):
                raise ValueError(f"t_crit must be a finite number in (0.0, 1.0], got {t_crit}")

            # 5. Validate camera poses (finitude & coordinates)
            domain_cameras: list[CameraPose] = []
            for idx, cam in enumerate(cameras_dto):
                if not (math.isfinite(cam.x) and math.isfinite(cam.y) and math.isfinite(cam.theta)):
                    raise ValueError(
                        f"Camera at index {idx} has non-finite coordinates: x={cam.x}, y={cam.y}, theta={cam.theta}"
                    )
                domain_cameras.append(CameraPose(x=cam.x, y=cam.y, theta=wrap_pi(cam.theta)))

            # 6. Build domain physical simulation objects
            floorplan = self.build_floorplan(scenario)
            grid = self.build_sampling_grid(floorplan, scenario.grid_resolution)
            profile = self.build_camera_profile(profile_dto)
            obj_config = ObjectiveConfig(lambda_def=lambda_def, t_crit=t_crit)

            evaluator = ConfigurationEvaluator(
                floorplan=floorplan,
                grid=grid,
                profile=profile,
                config=obj_config,
            )

            # 7. Feasibility verification
            is_feasible, reasons = evaluator.check_feasibility(domain_cameras)
            if not is_feasible:
                raise ValueError(f"Infeasible camera configuration: {'; '.join(reasons)}")

            # 8. Evaluate configuration using ConfigurationEvaluator
            eval_result = evaluator.evaluate(domain_cameras)

            # 9. Map grid nodes and per-node coverage
            # Preserve exact order of grid.nodes
            metrics = eval_result.metrics
            if metrics is None:
                raise ValueError("Evaluator failed to compute metrics for feasible configuration")

            nodes_dto: list[CoverageGridNodeDTO] = [
                CoverageGridNodeDTO(
                    x=float(node.point.x),
                    y=float(node.point.y),
                    probability=float(metrics.point_probabilities[i]),
                    binary_covered=bool(metrics.point_binary_covered[i]),
                    risk_weight=float(node.weight),
                )
                for i, node in enumerate(grid.nodes)
            ]

            metrics_dto = CoverageMetricsDTO(
                num_eval_points=int(metrics.num_eval_points),
                num_covered_points=int(metrics.num_covered_points),
                geometric_coverage_ratio=float(metrics.geometric_coverage_ratio),
                geometric_coverage_percent=float(metrics.geometric_coverage_percent),
                mean_probabilistic_coverage=float(metrics.mean_probabilistic_coverage),
                risk_weighted_coverage=float(metrics.risk_weighted_coverage),
                num_critical_points=int(metrics.num_critical_points),
                critical_deficit=float(metrics.critical_deficit),
            )

            return CoverageEvaluationResponse(
                cell_width=float(grid.cell_width),
                cell_height=float(grid.cell_height),
                total_nodes=len(grid.nodes),
                nodes=nodes_dto,
                metrics=metrics_dto,
                objective_cost=float(eval_result.objective_cost if eval_result.objective_cost is not None else 1.0),
                is_feasible=True,
            )
        finally:
            self._active_run_id = None
            self._run_start_time = None
            self._lock.release()

