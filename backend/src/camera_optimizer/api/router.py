"""FastAPI API Router providing REST endpoints for the Camera Optimizer."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from camera_optimizer.api.scenarios import ALL_PREDEFINED_SCENARIOS
from camera_optimizer.api.schemas import (
    CoverageEvaluationRequest,
    CoverageEvaluationResponse,
    HealthResponse,
    OptimizationRequest,
    OptimizationResultDTO,
    PredefinedScenariosResponse,
    ValidationRequest,
    ValidationResponse,
)
from camera_optimizer.api.service import OptimizationBusyError, OptimizationService


router = APIRouter(prefix="/api/v1", tags=["optimization"])

# Shared service instance
_service_instance: OptimizationService | None = None


def get_optimization_service() -> OptimizationService:
    """Dependency provider for the shared OptimizationService."""
    global _service_instance
    if _service_instance is None:
        _service_instance = OptimizationService()
    return _service_instance


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health and Operational Status",
    description="Verify service availability, version, and whether an optimization is actively running.",
)
def get_health(
    service: Annotated[OptimizationService, Depends(get_optimization_service)],
) -> HealthResponse:
    """Health check endpoint."""
    status_details = service.get_status_details()
    return HealthResponse(
        status="ok",
        service="ABC Security Camera Optimizer API",
        version="0.4.0",
        is_busy=service.is_busy,
        details=status_details,
    )


@router.get(
    "/scenarios",
    response_model=PredefinedScenariosResponse,
    summary="Get Predefined Benchmark Scenarios",
    description="Retrieve reproducible reference scenarios (open warehouse, partitioned office, museum gallery).",
)
def list_predefined_scenarios() -> PredefinedScenariosResponse:
    """Return catalog of validated benchmark scenarios."""
    return PredefinedScenariosResponse(scenarios=ALL_PREDEFINED_SCENARIOS)


@router.post(
    "/scenarios/validate",
    response_model=ValidationResponse,
    summary="Validate Scenario and Parameters",
    description="Validate facility geometry, optical sensor bounds, and ABC hyperparameters without running optimization.",
)
def validate_scenario(
    payload: ValidationRequest,
    service: Annotated[OptimizationService, Depends(get_optimization_service)],
) -> ValidationResponse:
    """Validate spatial geometry, obstacle topology, and configuration bounds."""
    return service.validate_scenario(
        scenario=payload.scenario,
        profile=payload.profile,
        config=payload.config,
    )


@router.post(
    "/optimize/run",
    response_model=OptimizationResultDTO,
    summary="Execute Sequential ABC Camera Optimization",
    description=(
        "Run real, strictly sequential Artificial Bee Colony optimization for camera placement. "
        "Blocks synchronously until optimization finishes and returns complete telemetry."
    ),
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Another optimization run is already in progress.",
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Validation failed for scenario, profile, or hyperparameters.",
        },
    },
)
def run_optimization(
    payload: OptimizationRequest,
    service: Annotated[OptimizationService, Depends(get_optimization_service)],
) -> OptimizationResultDTO:
    """Execute real sequential ABC optimization."""
    try:
        return service.run_optimization(
            scenario=payload.scenario,
            profile_dto=payload.profile,
            config_dto=payload.config,
        )
    except OptimizationBusyError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(err),
        ) from err
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Optimization request rejected: {err}",
        ) from err
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error during sequential optimization: {err}",
        ) from err


@router.post(
    "/coverage/evaluate",
    response_model=CoverageEvaluationResponse,
    summary="Evaluate Multi-Camera Simulated Detection Coverage",
    description=(
        "Compute exact continuous probabilistic detection and binary visibility "
        "coverage for a candidate configuration of cameras over the facility sampling grid."
    ),
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Another optimization or coverage evaluation is already in progress.",
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Validation failed for geometry, parameters, workload budget, or camera physical feasibility.",
        },
    },
)
def evaluate_coverage(
    payload: CoverageEvaluationRequest,
    service: Annotated[OptimizationService, Depends(get_optimization_service)],
) -> CoverageEvaluationResponse:
    """Evaluate spatial coverage field and objective cost for a camera configuration."""
    try:
        return service.evaluate_coverage(
            scenario=payload.scenario,
            profile_dto=payload.profile,
            cameras_dto=payload.cameras,
            lambda_def=payload.lambda_def,
            t_crit=payload.t_crit,
        )
    except OptimizationBusyError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(err),
        ) from err
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Coverage evaluation rejected: {err}",
        ) from err
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error during coverage evaluation: {err}",
        ) from err

