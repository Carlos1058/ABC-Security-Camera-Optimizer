"""Pydantic DTOs and Data Contracts for ABC Security Camera Optimizer API.

These models define strictly typed contracts for scenarios, optical profiles,
optimization hyperparameters, validation, and optimization results.

Enforces:
- allow_inf_nan=False across all models (Defecto A).
- Non-negative, finite integer seeds within [0, 2^64 - 1] (Defecto B & C).
- Strict validation consistency between API schemas and domain services.
- 100% JSON-serializable standard Python data structures.
"""

from __future__ import annotations

import math
from typing import Any
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from camera_optimizer.camera.pose import wrap_pi


class PointDTO(BaseModel):
    """2D Point coordinate in meters."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    x: float = Field(..., description="X coordinate in meters")
    y: float = Field(..., description="Y coordinate in meters")


class WallDTO(BaseModel):
    """Interior wall or opaque partition segment."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    start: PointDTO = Field(..., description="Start point of the wall")
    end: PointDTO = Field(..., description="End point of the wall")
    is_opaque: bool = Field(default=True, description="Whether wall blocks line of sight")


class ObstacleDTO(BaseModel):
    """Polygonal solid obstacle."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    vertices: list[PointDTO] = Field(
        ..., min_length=3, description="Ordered sequence of polygon vertices (minimum 3)"
    )


class RiskZoneDTO(BaseModel):
    """High-priority spatial zone with coverage risk multiplier."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    vertices: list[PointDTO] = Field(
        ..., min_length=3, description="Ordered polygon vertices enclosing the risk zone"
    )
    weight: float = Field(
        default=2.0, ge=1.0, description="Risk multiplier weight w >= 1.0"
    )
    name: str = Field(default="", description="Descriptive label (e.g. 'Server Room', 'Safe')")


class ScenarioDTO(BaseModel):
    """Complete spatial scenario defining room bounds, walls, obstacles and evaluation grid."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    xmin: float = Field(default=0.0, description="Lower X bound in meters")
    xmax: float = Field(..., description="Upper X bound in meters")
    ymin: float = Field(default=0.0, description="Lower Y bound in meters")
    ymax: float = Field(..., description="Upper Y bound in meters")
    walls: list[WallDTO] = Field(default_factory=list, description="Interior wall segments")
    obstacles: list[ObstacleDTO] = Field(
        default_factory=list, description="Solid interior polygonal obstacles"
    )
    risk_zones: list[RiskZoneDTO] = Field(
        default_factory=list, description="Priority risk regions requiring heightened coverage"
    )
    grid_resolution: float = Field(
        default=0.5, gt=0.0, description="Discretization sampling grid step in meters"
    )

    @model_validator(mode="after")
    def validate_scenario_bounds(self) -> ScenarioDTO:
        """Validate that boundaries are finite numbers."""
        for name, val in [("xmin", self.xmin), ("xmax", self.xmax), ("ymin", self.ymin), ("ymax", self.ymax)]:
            if not math.isfinite(val):
                raise ValueError(f"Scenario boundary '{name}' must be a finite number, got {val}")
        if not math.isfinite(self.grid_resolution) or self.grid_resolution <= 0.0:
            raise ValueError(f"grid_resolution must be a finite positive number, got {self.grid_resolution}")
        return self

    @property
    def width(self) -> float:
        """Width of the floorplan."""
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        """Height of the floorplan."""
        return self.ymax - self.ymin


class CameraProfileDTO(BaseModel):
    """Optical sensing parameters for simulated security cameras."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", allow_inf_nan=False)

    Rmin: float = Field(
        default=0.0,
        ge=0.0,
        validation_alias=AliasChoices("Rmin", "rmin"),
        description="Minimum sensing distance in meters (blind spot near lens)",
    )
    Rmax: float = Field(
        default=10.0,
        gt=0.0,
        validation_alias=AliasChoices("Rmax", "rmax"),
        description="Maximum effective sensing distance in meters",
    )
    FOV: float = Field(
        default=math.pi / 2.0,
        gt=0.0,
        le=2.0 * math.pi,
        validation_alias=AliasChoices("FOV", "fov"),
        description="Horizontal angular field of view aperture in radians",
    )
    p0: float = Field(
        default=1.0,
        gt=0.0,
        le=1.0,
        description="Peak detection probability at optimal vantage",
    )
    beta_d: float = Field(
        default=0.5,
        ge=0.0,
        description="Radial distance exponential decay coefficient",
    )
    beta_theta: float = Field(
        default=0.5,
        ge=0.0,
        description="Angular deviation exponential decay coefficient",
    )

    @property
    def fov(self) -> float:
        """Convenience alias for FOV."""
        return self.FOV

    @model_validator(mode="after")
    def validate_range(self) -> CameraProfileDTO:
        """Ensure all profile parameters are finite and Rmax > Rmin."""
        params = {
            "Rmin": self.Rmin,
            "Rmax": self.Rmax,
            "FOV": self.FOV,
            "p0": self.p0,
            "beta_d": self.beta_d,
            "beta_theta": self.beta_theta,
        }
        for name, val in params.items():
            if not math.isfinite(val):
                raise ValueError(f"CameraProfile parameter '{name}' must be a finite number, got {val}")
        if self.Rmax <= self.Rmin:
            raise ValueError(f"Rmax ({self.Rmax}) must be strictly greater than Rmin ({self.Rmin})")
        return self


class OptimizationConfigDTO(BaseModel):
    """Hyperparameters configuring the Sequential Artificial Bee Colony optimization."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", allow_inf_nan=False)

    K: int = Field(
        default=3,
        ge=1,
        validation_alias=AliasChoices("K", "num_cameras"),
        description="Fixed number of cameras K to place",
    )
    SN: int = Field(
        default=20,
        ge=2,
        validation_alias=AliasChoices("SN", "num_food_sources"),
        description="Colony population size / number of food sources SN >= 2",
    )
    max_cycles: int = Field(
        default=50,
        ge=1,
        description="Maximum sequential ABC iteration cycles",
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        description="Scout abandonment threshold. Defaults to SN * (3 * K) if None.",
    )
    seed: int | str | None = Field(
        default=None,
        description="PRNG seed for strictly reproducible stochastic optimization (0 <= seed < 2^64, as integer or decimal string)",
    )
    lambda_def: float = Field(
        default=1.0,
        ge=0.0,
        description="Penalty multiplier for critical zone coverage deficit",
    )
    Tcrit: float = Field(
        default=0.8,
        gt=0.0,
        le=1.0,
        validation_alias=AliasChoices("Tcrit", "t_crit"),
        description="Minimum critical detection probability threshold for high-risk points",
    )
    record_population: bool = Field(
        default=False,
        description="Whether to capture end-of-cycle population snapshots for visual replay",
    )

    @model_validator(mode="after")
    def validate_config(self) -> OptimizationConfigDTO:
        """Ensure hyperparameters are finite and seed domain is valid."""
        if not math.isfinite(self.lambda_def):
            raise ValueError("lambda_def must be a finite number")
        if not math.isfinite(self.Tcrit):
            raise ValueError("Tcrit must be a finite number")
        if self.seed is not None:
            seed_val = None
            if isinstance(self.seed, str):
                s = self.seed.strip()
                if not s.isdigit():
                    raise ValueError(f"Seed string must contain only decimal digits, got {self.seed!r}")
                seed_val = int(s)
            elif isinstance(self.seed, int) and not isinstance(self.seed, bool):
                seed_val = self.seed
            else:
                raise ValueError(f"Seed must be an integer or decimal string, got {type(self.seed).__name__}")

            if not (0 <= seed_val < 2**64):
                raise ValueError(f"Seed must be in range [0, 2^64 - 1], got {self.seed!r}")
        return self

    @property
    def num_cameras(self) -> int:
        """Convenience alias for K."""
        return self.K

    @property
    def num_food_sources(self) -> int:
        """Convenience alias for SN."""
        return self.SN

    @property
    def t_crit(self) -> float:
        """Convenience alias for Tcrit."""
        return self.Tcrit


class CameraPoseDTO(BaseModel):
    """Individual camera position and orientation."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    x: float = Field(..., description="Camera X position in meters")
    y: float = Field(..., description="Camera Y position in meters")
    theta: float = Field(..., description="Camera viewing angle in radians [-pi, pi]")
    theta_deg: float = Field(default=0.0, description="Camera viewing angle in degrees [-180, 180]")

    @model_validator(mode="before")
    @classmethod
    def populate_theta_deg(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "theta" in data and ("theta_deg" not in data or data["theta_deg"] is None):
                theta_val = data["theta"]
                if isinstance(theta_val, (int, float)) and math.isfinite(theta_val):
                    data["theta_deg"] = float(round(math.degrees(wrap_pi(float(theta_val))), 2))
        return data


class CoverageMetricsDTO(BaseModel):
    """Detailed summary coverage and visibility metrics."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    num_eval_points: int
    num_covered_points: int
    geometric_coverage_ratio: float
    geometric_coverage_percent: float
    mean_probabilistic_coverage: float
    risk_weighted_coverage: float
    num_critical_points: int
    critical_deficit: float


class FoodSourceDTO(BaseModel):
    """Single food source candidate in the population."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    position: list[float] = Field(..., description="Raw continuous 3K coordinate vector")
    poses: list[CameraPoseDTO] = Field(..., description="Decoded camera poses")
    cost: float = Field(..., description="Objective function cost f(X)")
    fitness: float = Field(..., description="ABC fitness metric 1/(1+cost)")
    trial: int = Field(..., description="Stagnation trial counter")


class CycleSnapshotDTO(BaseModel):
    """Historical telemetry record at the end of an ABC cycle."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    cycle: int
    best_cost: float
    best_poses: list[CameraPoseDTO]
    mean_population_cost: float
    improvements_count: int
    scout_resets: int
    population: list[FoodSourceDTO] | None = Field(
        default=None,
        description="Full population snapshot at cycle end (when record_population=True)",
    )


class OptimizationResultDTO(BaseModel):
    """Complete output produced by a real Sequential ABC optimization run."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    scenario: ScenarioDTO
    profile: CameraProfileDTO
    config: OptimizationConfigDTO
    effective_seed: str = Field(
        ..., description="Concrete reproducible PRNG integer seed formatted as decimal string"
    )
    dimension: int

    @field_validator("effective_seed", mode="before")
    @classmethod
    def coerce_seed_str(cls, v: Any) -> str:
        return str(v)

    initial_best_cost: float
    initial_best_poses: list[CameraPoseDTO]

    final_best_cost: float
    final_best_poses: list[CameraPoseDTO]

    best_cost_per_cycle: list[float]
    mean_cost_per_cycle: list[float]

    coverage_metrics: CoverageMetricsDTO

    total_evaluations: int
    total_proposals: int
    rejected_infeasible_proposals: int
    total_scout_resets: int
    execution_time_seconds: float

    history: list[CycleSnapshotDTO]
    population_history_available: bool
    notes: str = Field(
        default=(
            "Population history corresponds to the end-of-cycle state, not intra-cycle micro-movements. "
            "Greedy selection uses strict improvement (f(v) < f(x)) matching canonical MATLAB v2 ABC."
        )
    )


class OptimizationRequest(BaseModel):
    """Payload to initiate a real sequential optimization."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    scenario: ScenarioDTO
    profile: CameraProfileDTO = Field(default_factory=CameraProfileDTO)
    config: OptimizationConfigDTO = Field(default_factory=OptimizationConfigDTO)


class ValidationRequest(BaseModel):
    """Payload to validate geometry, optical profile, and hyperparameters."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    scenario: ScenarioDTO
    profile: CameraProfileDTO = Field(default_factory=CameraProfileDTO)
    config: OptimizationConfigDTO = Field(default_factory=OptimizationConfigDTO)


class ValidationResponse(BaseModel):
    """Validation response indicating admissibility and diagnostic messages."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    """Health check response confirming operational status."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    status: str = "ok"
    service: str = "ABC Security Camera Optimizer API"
    version: str = "0.4.0"
    is_busy: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class PredefinedScenarioItemDTO(BaseModel):
    """Summary and complete definition of a demo scenario."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    id: str
    name: str
    description: str
    scenario: ScenarioDTO
    recommended_profile: CameraProfileDTO
    recommended_config: OptimizationConfigDTO


class PredefinedScenariosResponse(BaseModel):
    """Response containing standard predefined benchmark scenarios."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    scenarios: list[PredefinedScenarioItemDTO]


class CoverageGridNodeDTO(BaseModel):
    """Discrete evaluation grid node with simulated detection coverage and risk."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    x: float = Field(..., description="X coordinate in meters")
    y: float = Field(..., description="Y coordinate in meters")
    probability: float = Field(
        ..., ge=0.0, le=1.0, description="Combined detection probability in [0, 1]"
    )
    binary_covered: bool = Field(
        ..., description="Whether node is geometrically covered by >= 1 camera"
    )
    risk_weight: float = Field(..., ge=1.0, description="Risk weight multiplier for this node")


class CoverageEvaluationRequest(BaseModel):
    """Payload to request spatial coverage evaluation for a camera configuration."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    scenario: ScenarioDTO
    profile: CameraProfileDTO = Field(default_factory=CameraProfileDTO)
    cameras: list[CameraPoseDTO] = Field(
        ...,
        min_length=1,
        max_length=30,
        description="Ordered configuration of camera poses to evaluate (1 <= K <= 30)",
    )
    lambda_def: float = Field(
        default=1.0, ge=0.0, description="Penalty multiplier for critical zone coverage deficit"
    )
    t_crit: float = Field(
        default=0.8,
        gt=0.0,
        le=1.0,
        validation_alias=AliasChoices("Tcrit", "t_crit", "tcrit"),
        description="Minimum critical detection probability threshold for high-risk points",
    )
    config: OptimizationConfigDTO | None = Field(
        default=None,
        description="Optional optimization config to inherit lambda_def and t_crit from",
    )

    @model_validator(mode="after")
    def inherit_config_params(self) -> CoverageEvaluationRequest:
        if not math.isfinite(self.lambda_def):
            raise ValueError("lambda_def must be a finite number")
        if not math.isfinite(self.t_crit):
            raise ValueError("t_crit must be a finite number")
        if self.config is not None:
            if not math.isfinite(self.config.lambda_def):
                raise ValueError("Config lambda_def must be a finite number")
            if not math.isfinite(self.config.Tcrit):
                raise ValueError("Config Tcrit must be a finite number")
            # If default values were used in top-level, inherit from config
            if self.lambda_def == 1.0 and self.config.lambda_def != 1.0:
                self.lambda_def = self.config.lambda_def
            if self.t_crit == 0.8 and self.config.Tcrit != 0.8:
                self.t_crit = self.config.Tcrit
        return self


class CoverageEvaluationResponse(BaseModel):
    """Detailed spatial coverage evaluation results for a camera configuration."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    cell_width: float = Field(..., gt=0.0, description="Physical cell width dx in meters")
    cell_height: float = Field(..., gt=0.0, description="Physical cell height dy in meters")
    total_nodes: int = Field(..., ge=0, description="Total number of valid free-space evaluation nodes")
    nodes: list[CoverageGridNodeDTO] = Field(
        ..., description="Ordered list of evaluated grid nodes in free space"
    )
    metrics: CoverageMetricsDTO = Field(
        ..., description="Aggregated multi-camera coverage and visibility metrics"
    )
    objective_cost: float = Field(..., ge=0.0, description="Computed objective function cost f(X)")
    is_feasible: bool = Field(default=True, description="Whether all camera poses are physically feasible")

