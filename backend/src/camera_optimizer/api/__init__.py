"""API package for the ABC Security Camera Optimizer."""

from camera_optimizer.api.app import app, create_app
from camera_optimizer.api.limits import DEFAULT_LIMITS, ResourceLimits
from camera_optimizer.api.router import router
from camera_optimizer.api.schemas import (
    CameraPoseDTO,
    CameraProfileDTO,
    CoverageMetricsDTO,
    CycleSnapshotDTO,
    FoodSourceDTO,
    HealthResponse,
    ObstacleDTO,
    OptimizationConfigDTO,
    OptimizationRequest,
    OptimizationResultDTO,
    PointDTO,
    PredefinedScenarioItemDTO,
    PredefinedScenariosResponse,
    RiskZoneDTO,
    ScenarioDTO,
    ValidationRequest,
    ValidationResponse,
    WallDTO,
)
from camera_optimizer.api.service import OptimizationBusyError, OptimizationService

__all__ = [
    "DEFAULT_LIMITS",
    "CameraPoseDTO",
    "CameraProfileDTO",
    "CoverageMetricsDTO",
    "CycleSnapshotDTO",
    "FoodSourceDTO",
    "HealthResponse",
    "ObstacleDTO",
    "OptimizationBusyError",
    "OptimizationConfigDTO",
    "OptimizationRequest",
    "OptimizationResultDTO",
    "OptimizationService",
    "PointDTO",
    "PredefinedScenarioItemDTO",
    "PredefinedScenariosResponse",
    "ResourceLimits",
    "RiskZoneDTO",
    "ScenarioDTO",
    "ValidationRequest",
    "ValidationResponse",
    "WallDTO",
    "app",
    "create_app",
    "router",
]
