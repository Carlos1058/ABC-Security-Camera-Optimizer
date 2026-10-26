"""Automated test suite for FastAPI backend and Sequential ABC integration (TAREA 05).

Verifies:
- GET /api/v1/health
- GET /api/v1/scenarios
- POST /api/v1/scenarios/validate (valid scenarios, invalid geometry, invalid hyperparameters)
- POST /api/v1/optimize/run (real execution, 3K dimensionality, determinism, engine parity)
- Telemetry & history serialization (zero NumPy leaks, 100% JSON compliance)
- Concurrency protection (409 Conflict when busy)
- Resource limit enforcement (grid cell limits, camera limits, geometric complexity)
"""

from __future__ import annotations

import json
import math
import threading
import time
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

from camera_optimizer.api.app import app
from camera_optimizer.api.router import get_optimization_service
from camera_optimizer.api.scenarios import get_empty_warehouse, get_partitioned_office
from camera_optimizer.api.schemas import (
    CameraProfileDTO,
    ObstacleDTO,
    OptimizationConfigDTO,
    PointDTO,
    RiskZoneDTO,
    ScenarioDTO,
    WallDTO,
)
from camera_optimizer.api.service import OptimizationService
from camera_optimizer.optimizer.camera_problem import CameraOptimizationProblem
from camera_optimizer.optimizer.config import ABCConfig
from camera_optimizer.optimizer.sequential_abc import SequentialABC


@pytest.fixture
def client() -> TestClient:
    """Provide FastAPI test client."""
    return TestClient(app)


# =============================================================================
# 1. Health Endpoint Tests
# =============================================================================


def test_health_endpoint(client: TestClient) -> None:
    """GET /api/v1/health returns 200, operational status, and engine state."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "ABC Security Camera Optimizer API"
    assert data["version"] == "0.4.0"
    assert data["is_busy"] is False
    assert "details" in data


def test_root_endpoint(client: TestClient) -> None:
    """GET / returns service links and docs pointers."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert data["docs"] == "/docs"


# =============================================================================
# 2. Predefined Scenarios Tests
# =============================================================================


def test_get_predefined_scenarios(client: TestClient) -> None:
    """GET /api/v1/scenarios returns predefined demo scenarios with valid geometry."""
    response = client.get("/api/v1/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert "scenarios" in data
    scenarios = data["scenarios"]
    assert len(scenarios) >= 2

    ids = [s["id"] for s in scenarios]
    assert "empty_warehouse" in ids
    assert "partitioned_office" in ids

    # Scenario 1: Empty warehouse has NO obstacles and NO interior walls
    warehouse = next(s for s in scenarios if s["id"] == "empty_warehouse")
    assert len(warehouse["scenario"]["walls"]) == 0
    assert len(warehouse["scenario"]["obstacles"]) == 0
    assert len(warehouse["scenario"]["risk_zones"]) >= 1

    # Scenario 2: Partitioned office has walls, doors, obstacles, and risk zones
    office = next(s for s in scenarios if s["id"] == "partitioned_office")
    assert len(office["scenario"]["walls"]) >= 2
    assert len(office["scenario"]["obstacles"]) >= 1
    assert len(office["scenario"]["risk_zones"]) >= 1

    # Every scenario must have valid recommended config and profile
    for scn in scenarios:
        assert scn["recommended_profile"]["Rmax"] > scn["recommended_profile"]["Rmin"]
        assert scn["recommended_config"]["K"] >= 1
        assert scn["recommended_config"]["SN"] >= 2


# =============================================================================
# 3. Validation Endpoint Tests
# =============================================================================


def test_validate_predefined_scenarios_pass(client: TestClient) -> None:
    """POST /api/v1/scenarios/validate confirms all predefined scenarios are valid."""
    for item in [get_empty_warehouse(), get_partitioned_office()]:
        payload = {
            "scenario": item.scenario.model_dump(),
            "profile": item.recommended_profile.model_dump(),
            "config": item.recommended_config.model_dump(),
        }
        response = client.post("/api/v1/scenarios/validate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True
        assert len(data["errors"]) == 0
        assert data["details"].get("actual_grid_nodes", 0) > 0


def test_validate_invalid_room_dimensions_rejected(client: TestClient) -> None:
    """POST /api/v1/scenarios/validate rejects invalid room dimensions."""
    # Negative width
    payload = {
        "scenario": {
            "xmin": 10.0,
            "xmax": 5.0,  # xmin > xmax
            "ymin": 0.0,
            "ymax": 10.0,
            "grid_resolution": 1.0,
        }
    }
    response = client.post("/api/v1/scenarios/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is False
    assert any("Invalid room width" in err for err in data["errors"])


def test_validate_self_intersecting_obstacle_rejected(client: TestClient) -> None:
    """POST /api/v1/scenarios/validate rejects self-intersecting polygon obstacles."""
    # Hourglass self-intersecting polygon
    payload = {
        "scenario": {
            "xmin": 0.0,
            "xmax": 20.0,
            "ymin": 0.0,
            "ymax": 20.0,
            "grid_resolution": 1.0,
            "obstacles": [
                {
                    "vertices": [
                        {"x": 2.0, "y": 2.0},
                        {"x": 8.0, "y": 8.0},
                        {"x": 2.0, "y": 8.0},
                        {"x": 8.0, "y": 2.0},
                    ]
                }
            ],
        }
    }
    response = client.post("/api/v1/scenarios/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is False
    assert any("topologically invalid" in err for err in data["errors"])


def test_validate_wall_outside_boundary_rejected(client: TestClient) -> None:
    """POST /api/v1/scenarios/validate rejects walls lying outside facility bounds."""
    payload = {
        "scenario": {
            "xmin": 0.0,
            "xmax": 10.0,
            "ymin": 0.0,
            "ymax": 10.0,
            "grid_resolution": 1.0,
            "walls": [
                {
                    "start": {"x": 5.0, "y": 5.0},
                    "end": {"x": 15.0, "y": 5.0},  # x=15 > xmax=10
                }
            ],
        }
    }
    response = client.post("/api/v1/scenarios/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is False
    assert any("lies outside the facility boundary" in err for err in data["errors"])


def test_validate_obstacle_outside_boundary_rejected(client: TestClient) -> None:
    """POST /api/v1/scenarios/validate rejects obstacles outside room boundary."""
    payload = {
        "scenario": {
            "xmin": 0.0,
            "xmax": 10.0,
            "ymin": 0.0,
            "ymax": 10.0,
            "grid_resolution": 1.0,
            "obstacles": [
                {
                    "vertices": [
                        {"x": 8.0, "y": 8.0},
                        {"x": 12.0, "y": 8.0},  # x=12 > 10
                        {"x": 12.0, "y": 12.0},
                        {"x": 8.0, "y": 12.0},
                    ]
                }
            ],
        }
    }
    response = client.post("/api/v1/scenarios/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is False
    assert any("outside the facility boundary" in err for err in data["errors"])


def test_validate_degenerate_wall_rejected(client: TestClient) -> None:
    """POST /api/v1/scenarios/validate rejects walls with identical start and end."""
    payload = {
        "scenario": {
            "xmin": 0.0,
            "xmax": 10.0,
            "ymin": 0.0,
            "ymax": 10.0,
            "grid_resolution": 1.0,
            "walls": [
                {
                    "start": {"x": 5.0, "y": 5.0},
                    "end": {"x": 5.0, "y": 5.0},
                }
            ],
        }
    }
    response = client.post("/api/v1/scenarios/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is False
    assert any("degenerate" in err for err in data["errors"])


def test_validate_invalid_optimization_hyperparameters_rejected(client: TestClient) -> None:
    """POST /api/v1/scenarios/validate rejects hyperparameter violations (K, SN, cycles)."""
    base_scenario = {
        "xmin": 0.0,
        "xmax": 10.0,
        "ymin": 0.0,
        "ymax": 10.0,
        "grid_resolution": 1.0,
    }

    # K=0 (Pydantic Field(ge=1) catches this and returns 422, which is correct HTTP validation)
    res_k = client.post(
        "/api/v1/scenarios/validate",
        json={"scenario": base_scenario, "config": {"K": 0}},
    )
    assert res_k.status_code == 422

    # SN=1 (Pydantic Field(ge=2) catches this and returns 422)
    res_sn = client.post(
        "/api/v1/scenarios/validate",
        json={"scenario": base_scenario, "config": {"SN": 1}},
    )
    assert res_sn.status_code == 422

    # Optical profile Rmin >= Rmax
    res_opt = client.post(
        "/api/v1/scenarios/validate",
        json={"scenario": base_scenario, "profile": {"Rmin": 10.0, "Rmax": 5.0}},
    )
    assert res_opt.status_code == 422


def test_resource_limits_protection_excessive_grid(client: TestClient) -> None:
    """POST /api/v1/scenarios/validate guards against disproportionate grid cell allocation."""
    # 50m x 50m room with 0.05m grid step -> (50/0.05)^2 = 1,000,000 cells > 50,000 limit
    payload = {
        "scenario": {
            "xmin": 0.0,
            "xmax": 50.0,
            "ymin": 0.0,
            "ymax": 50.0,
            "grid_resolution": 0.05,
        }
    }
    response = client.post("/api/v1/scenarios/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is False
    assert any("safety limit" in err for err in data["errors"])


def test_resource_limits_protection_too_many_cameras(client: TestClient) -> None:
    """Config with K > 30 is rejected by resource limit validation."""
    payload = {
        "scenario": {
            "xmin": 0.0,
            "xmax": 20.0,
            "ymin": 0.0,
            "ymax": 20.0,
            "grid_resolution": 1.0,
        },
        "config": {
            "K": 35,  # > max_cameras (30)
        },
    }
    response = client.post("/api/v1/scenarios/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is False
    assert any("Number of cameras K (35) is outside permitted range" in err for err in data["errors"])


# =============================================================================
# 4. Real Optimization Execution Tests
# =============================================================================


def test_optimize_real_execution_end_to_end(client: TestClient) -> None:
    """POST /api/v1/optimize/run executes real sequential ABC optimization and returns results."""
    scenario = {
        "xmin": 0.0,
        "xmax": 15.0,
        "ymin": 0.0,
        "ymax": 15.0,
        "grid_resolution": 1.5,
        "risk_zones": [
            {
                "vertices": [
                    {"x": 5.0, "y": 5.0},
                    {"x": 10.0, "y": 5.0},
                    {"x": 10.0, "y": 10.0},
                    {"x": 5.0, "y": 10.0},
                ],
                "weight": 2.5,
                "name": "Target Zone",
            }
        ],
    }
    profile = {
        "Rmin": 0.0,
        "Rmax": 10.0,
        "FOV": math.pi / 2.0,
        "p0": 1.0,
        "beta_d": 0.4,
        "beta_theta": 0.5,
    }
    config = {
        "num_cameras": 2,
        "num_food_sources": 4,
        "max_cycles": 5,
        "seed": 42,
        "lambda_def": 1.0,
        "Tcrit": 0.8,
        "record_population": True,
    }

    response = client.post(
        "/api/v1/optimize/run",
        json={"scenario": scenario, "profile": profile, "config": config},
    )
    assert response.status_code == 200
    data = response.json()

    # Dimensionality check: exactly 3K (2 cameras * 3 = 6)
    assert data["dimension"] == 6
    assert len(data["initial_best_poses"]) == 2
    assert len(data["final_best_poses"]) == 2

    # Verification of non-worsening optimization progress
    assert data["final_best_cost"] <= data["initial_best_cost"]
    assert math.isfinite(data["final_best_cost"])

    # Monotonic best cost history
    best_history = data["best_cost_per_cycle"]
    assert len(best_history) == 6  # cycle 0 + 5 cycles
    for i in range(1, len(best_history)):
        assert best_history[i] <= best_history[i - 1]

    # Mean cost history exists
    mean_history = data["mean_cost_per_cycle"]
    assert len(mean_history) == 6

    # Coverage metrics present and finite
    metrics = data["coverage_metrics"]
    assert metrics["num_eval_points"] > 0
    assert metrics["num_covered_points"] >= 0
    assert 0.0 <= metrics["geometric_coverage_ratio"] <= 1.0
    assert 0.0 <= metrics["geometric_coverage_percent"] <= 100.0
    assert 0.0 <= metrics["risk_weighted_coverage"] <= 1.0
    assert metrics["num_critical_points"] > 0

    # NFE, proposal, and scout telemetry
    assert data["total_evaluations"] > 0
    assert data["total_proposals"] > 0
    assert data["execution_time_seconds"] >= 0.0

    # Population history available
    assert data["population_history_available"] is True
    history = data["history"]
    assert len(history) == 6

    # Verify population snapshot inside history
    c0 = history[0]
    assert c0["cycle"] == 0
    assert c0["population"] is not None
    assert len(c0["population"]) == 4  # SN=4
    for src in c0["population"]:
        assert len(src["position"]) == 6  # 3K
        assert len(src["poses"]) == 2  # K
        assert math.isfinite(src["cost"])
        assert src["fitness"] > 0.0
        assert src["trial"] >= 0


def test_dimensionality_is_exactly_3k(client: TestClient) -> None:
    """Verifies that problem dimension is strictly 3K for K=1 and K=3."""
    scenario = {
        "xmin": 0.0,
        "xmax": 10.0,
        "ymin": 0.0,
        "ymax": 10.0,
        "grid_resolution": 2.0,
    }

    # K = 1
    res1 = client.post(
        "/api/v1/optimize/run",
        json={
            "scenario": scenario,
            "config": {"K": 1, "SN": 3, "max_cycles": 2, "seed": 10},
        },
    )
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["dimension"] == 3
    assert len(d1["final_best_poses"]) == 1

    # K = 3
    res3 = client.post(
        "/api/v1/optimize/run",
        json={
            "scenario": scenario,
            "config": {"K": 3, "SN": 3, "max_cycles": 2, "seed": 10},
        },
    )
    assert res3.status_code == 200
    d3 = res3.json()
    assert d3["dimension"] == 9
    assert len(d3["final_best_poses"]) == 3


def test_determinism_with_same_seed(client: TestClient) -> None:
    """Executing optimization twice with identical seed and config produces identical output."""
    scenario = {
        "xmin": 0.0,
        "xmax": 12.0,
        "ymin": 0.0,
        "ymax": 12.0,
        "grid_resolution": 1.5,
    }
    payload = {
        "scenario": scenario,
        "config": {"K": 2, "SN": 4, "max_cycles": 4, "seed": 999},
    }

    res1 = client.post("/api/v1/optimize/run", json=payload)
    res2 = client.post("/api/v1/optimize/run", json=payload)

    assert res1.status_code == 200
    assert res2.status_code == 200

    d1 = res1.json()
    d2 = res2.json()

    assert d1["final_best_cost"] == d2["final_best_cost"]
    assert d1["best_cost_per_cycle"] == d2["best_cost_per_cycle"]
    assert d1["total_evaluations"] == d2["total_evaluations"]
    assert d1["total_scout_resets"] == d2["total_scout_resets"]

    for p1, p2 in zip(d1["final_best_poses"], d2["final_best_poses"]):
        assert p1["x"] == pytest.approx(p2["x"], abs=1e-12)
        assert p1["y"] == pytest.approx(p2["y"], abs=1e-12)
        assert p1["theta"] == pytest.approx(p2["theta"], abs=1e-12)


def test_api_matches_direct_engine_execution(client: TestClient) -> None:
    """API result matches exactly the output obtained from calling SequentialABC directly."""
    service = get_optimization_service()
    scenario_dto = ScenarioDTO(
        xmin=0.0,
        xmax=10.0,
        ymin=0.0,
        ymax=10.0,
        grid_resolution=2.0,
    )
    profile_dto = CameraProfileDTO(
        Rmin=0.0,
        Rmax=8.0,
        FOV=math.pi / 2.0,
        p0=1.0,
        beta_d=0.5,
        beta_theta=0.5,
    )
    config_dto = OptimizationConfigDTO(
        K=2,
        SN=4,
        max_cycles=3,
        seed=777,
        record_population=False,
    )

    # 1. API Call
    response = client.post(
        "/api/v1/optimize/run",
        json={
            "scenario": scenario_dto.model_dump(),
            "profile": profile_dto.model_dump(),
            "config": config_dto.model_dump(),
        },
    )
    assert response.status_code == 200
    api_data = response.json()

    # 2. Direct Engine Run
    floorplan = service.build_floorplan(scenario_dto)
    grid = service.build_sampling_grid(floorplan, scenario_dto.grid_resolution)
    profile = service.build_camera_profile(profile_dto)
    obj_config = service.build_objective_config(config_dto)
    abc_config = service.build_abc_config(config_dto)

    problem = CameraOptimizationProblem(
        floorplan=floorplan,
        grid=grid,
        num_cameras=config_dto.num_cameras,
        profile=profile,
        config=obj_config,
    )
    direct_output = SequentialABC(problem, abc_config).optimize()

    # Exact parity checks
    assert api_data["final_best_cost"] == pytest.approx(direct_output.best_cost, abs=1e-12)
    assert api_data["total_evaluations"] == direct_output.total_evaluations
    assert api_data["total_proposals"] == direct_output.total_proposals
    assert api_data["rejected_infeasible_proposals"] == direct_output.rejected_infeasible_proposals
    assert api_data["total_scout_resets"] == direct_output.total_scout_resets

    direct_best_poses = problem.vector_to_poses(direct_output.best_source.position)
    for api_p, dir_p in zip(api_data["final_best_poses"], direct_best_poses):
        assert api_p["x"] == pytest.approx(dir_p.x, abs=1e-12)
        assert api_p["y"] == pytest.approx(dir_p.y, abs=1e-12)
        assert api_p["theta"] == pytest.approx(dir_p.theta, abs=1e-12)


def test_serialization_json_compliance_no_numpy(client: TestClient) -> None:
    """Verifies that the API response is 100% compliant JSON with no NumPy objects."""
    scenario = {
        "xmin": 0.0,
        "xmax": 10.0,
        "ymin": 0.0,
        "ymax": 10.0,
        "grid_resolution": 2.0,
    }
    response = client.post(
        "/api/v1/optimize/run",
        json={"scenario": scenario, "config": {"K": 2, "SN": 3, "max_cycles": 2, "seed": 42}},
    )
    assert response.status_code == 200

    # Ensure json.dumps re-encodes without any TypeError or custom serializer
    raw_json = json.dumps(response.json())
    assert isinstance(raw_json, str)
    assert len(raw_json) > 100


# =============================================================================
# 5. Concurrency Protection & Error Handling Tests
# =============================================================================


def test_simultaneous_requests_rejected_with_409(client: TestClient) -> None:
    """While an optimization run is in progress, subsequent requests receive HTTP 409 Conflict."""
    service = get_optimization_service()

    # Manually acquire the service lock to simulate an active optimization running
    acquired = service._lock.acquire(blocking=False)
    assert acquired is True
    assert service.is_busy is True

    try:
        scenario = {
            "xmin": 0.0,
            "xmax": 10.0,
            "ymin": 0.0,
            "ymax": 10.0,
            "grid_resolution": 2.0,
        }
        response = client.post(
            "/api/v1/optimize/run",
            json={"scenario": scenario, "config": {"K": 2, "SN": 3, "max_cycles": 2}},
        )
        assert response.status_code == 409
        data = response.json()
        assert "detail" in data
        assert "Another optimization run is currently executing" in data["detail"]
    finally:
        service._lock.release()
        assert service.is_busy is False


def test_invalid_scenario_returns_400_on_optimize(client: TestClient) -> None:
    """POST /api/v1/optimize/run returns 400 Bad Request when validation fails."""
    # Scenario with self-intersecting obstacle
    payload = {
        "scenario": {
            "xmin": 0.0,
            "xmax": 20.0,
            "ymin": 0.0,
            "ymax": 20.0,
            "grid_resolution": 1.0,
            "obstacles": [
                {
                    "vertices": [
                        {"x": 2.0, "y": 2.0},
                        {"x": 8.0, "y": 8.0},
                        {"x": 2.0, "y": 8.0},
                        {"x": 8.0, "y": 2.0},
                    ]
                }
            ],
        }
    }
    response = client.post("/api/v1/optimize/run", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "Optimization request rejected" in data["detail"]


# =============================================================================
# 6. Audit Regression Tests (TAREA 05.1 — Defectos A, B, C, D, E)
# =============================================================================


def test_defect_a_non_finite_values_rejected(client: TestClient) -> None:
    """DEFECTO A: Rejects 1e309, inf, NaN at Pydantic schema validation layer."""
    headers = {"Content-Type": "application/json"}

    # Case 1: Overflow xmax = 1e309 in validate
    raw_body1 = (
        '{"scenario": {"xmin": 0, "xmax": 1e309, "ymin": 0, "ymax": 10, "grid_resolution": 2}}'
    )
    res1 = client.post("/api/v1/scenarios/validate", content=raw_body1, headers=headers)
    assert res1.status_code == 422
    assert "finite_number" in str(res1.json())

    # Case 2: Overflow beta_d = 1e309 in profile
    raw_body2 = (
        '{"scenario": {"xmax": 10, "ymax": 10, "grid_resolution": 2}, "profile": {"beta_d": 1e309}}'
    )
    res2 = client.post("/api/v1/scenarios/validate", content=raw_body2, headers=headers)
    assert res2.status_code == 422
    assert "finite_number" in str(res2.json())

    # Case 3: Rejection on /optimize/run as well
    raw_body3 = (
        '{"scenario": {"xmax": 1e309, "ymax": 10, "grid_resolution": 2}}'
    )
    res3 = client.post("/api/v1/optimize/run", content=raw_body3, headers=headers)
    assert res3.status_code == 422
    assert "finite_number" in str(res3.json())


def test_defect_b_effective_seed_reproducibility(client: TestClient) -> None:
    """DEFECTO B: When seed is omitted, returns concrete effective_seed and allows identical reproduction."""
    scenario = {
        "xmin": 0.0,
        "xmax": 10.0,
        "ymin": 0.0,
        "ymax": 10.0,
        "grid_resolution": 2.0,
    }
    # 1. Request WITHOUT seed
    payload1 = {
        "scenario": scenario,
        "config": {
            "K": 2,
            "SN": 4,
            "max_cycles": 3,
            "seed": None,
        },
    }
    res1 = client.post("/api/v1/optimize/run", json=payload1)
    assert res1.status_code == 200
    d1 = res1.json()

    eff_seed = d1["effective_seed"]
    assert isinstance(eff_seed, str)
    assert eff_seed.isdigit()
    assert int(eff_seed) >= 0
    assert d1["config"]["seed"] is None  # original config echoed

    # 2. Re-run WITH effective_seed (as string decimal)
    payload2 = {
        "scenario": scenario,
        "config": {
            "K": 2,
            "SN": 4,
            "max_cycles": 3,
            "seed": eff_seed,
        },
    }
    res2 = client.post("/api/v1/optimize/run", json=payload2)
    assert res2.status_code == 200
    d2 = res2.json()

    assert d2["effective_seed"] == eff_seed
    assert d2["final_best_cost"] == d1["final_best_cost"]
    assert d2["best_cost_per_cycle"] == d1["best_cost_per_cycle"]
    assert d2["total_evaluations"] == d1["total_evaluations"]
    assert d2["total_scout_resets"] == d1["total_scout_resets"]

    for p1, p2 in zip(d1["final_best_poses"], d2["final_best_poses"]):
        assert p1["x"] == pytest.approx(p2["x"], abs=1e-12)
        assert p1["y"] == pytest.approx(p2["y"], abs=1e-12)
        assert p1["theta"] == pytest.approx(p2["theta"], abs=1e-12)


def test_64bit_seed_lossless_reproducibility(client: TestClient) -> None:
    """ERROR ALTO 1: Verify lossless 64-bit seed (e.g. 9007199254740993) reproduction."""
    scenario = {
        "xmin": 0,
        "xmax": 15,
        "ymin": 0,
        "ymax": 15,
        "grid_resolution": 2,
    }
    seed_64bit = "9007199254740993"  # 2^53 + 1, cannot be represented by IEEE 754 float64

    # Run 1: Send string seed
    payload1 = {
        "scenario": scenario,
        "config": {
            "K": 2,
            "SN": 4,
            "max_cycles": 3,
            "seed": seed_64bit,
        },
    }
    res1 = client.post("/api/v1/optimize/run", json=payload1)
    assert res1.status_code == 200
    d1 = res1.json()

    assert d1["effective_seed"] == seed_64bit
    cost1 = d1["final_best_cost"]

    # Run 2: Repeat using received string seed
    copied_seed = d1["effective_seed"]
    payload2 = {
        "scenario": scenario,
        "config": {
            "K": 2,
            "SN": 4,
            "max_cycles": 3,
            "seed": copied_seed,
        },
    }
    res2 = client.post("/api/v1/optimize/run", json=payload2)
    assert res2.status_code == 200
    d2 = res2.json()

    assert d2["effective_seed"] == seed_64bit
    assert d2["final_best_cost"] == cost1
    assert d2["best_cost_per_cycle"] == d1["best_cost_per_cycle"]

    # Contrast with rounded seed: 9007199254740992
    payload_rounded = {
        "scenario": scenario,
        "config": {
            "K": 2,
            "SN": 4,
            "max_cycles": 3,
            "seed": "9007199254740992",
        },
    }
    res_rounded = client.post("/api/v1/optimize/run", json=payload_rounded)
    assert res_rounded.status_code == 200
    d_rounded = res_rounded.json()
    assert d_rounded["effective_seed"] == "9007199254740992"
    # Different seed produces different pseudo-random sequence
    assert d_rounded["effective_seed"] != seed_64bit


def test_defect_b_invalid_seed_rejected(client: TestClient) -> None:
    """DEFECTO B: Negative seed or seed outside [0, 2^64-1] is rejected."""
    scenario = {
        "xmax": 10,
        "ymax": 10,
        "grid_resolution": 2,
    }
    # Negative seed
    res_neg = client.post(
        "/api/v1/scenarios/validate",
        json={"scenario": scenario, "config": {"seed": -1}},
    )
    assert res_neg.status_code == 422

    # Negative seed on optimize
    res_neg_opt = client.post(
        "/api/v1/optimize/run",
        json={"scenario": scenario, "config": {"seed": -1}},
    )
    assert res_neg_opt.status_code == 422


def test_defect_c_validation_consistency(client: TestClient) -> None:
    """DEFECTO C: Consistent validation rules across /scenarios/validate and /optimize/run."""
    case_invalid = {
        "scenario": {
            "xmax": 10,
            "ymax": 10,
            "grid_resolution": 2,
        },
        "config": {
            "K": 1,
            "SN": 2,
            "max_cycles": 1,
            "seed": -1,
        },
    }
    # Both endpoints reject the exact same invalid payload with 422
    val_res = client.post("/api/v1/scenarios/validate", json=case_invalid)
    assert val_res.status_code == 422

    opt_res = client.post("/api/v1/optimize/run", json=case_invalid)
    assert opt_res.status_code == 422


def test_defect_d_global_work_budget_exceeded_rejected(client: TestClient) -> None:
    """DEFECTO D: Disproportionate computational budget is rejected before running ABC."""
    # 40m x 40m room at 0.2m resolution -> (40/0.2)^2 = 40,000 cells (within max_cells 50,000)
    # But K=25, SN=80, max_cycles=300:
    # NFE_upper ≈ 80 + 2*80*300 + 300 = 48,380
    # work_upper ≈ 48,380 * 25 * 40,000 = 48,380,000,000 >> 100,000,000
    payload = {
        "scenario": {
            "xmin": 0.0,
            "xmax": 40.0,
            "ymin": 0.0,
            "ymax": 40.0,
            "grid_resolution": 0.2,
        },
        "config": {
            "K": 25,
            "SN": 80,
            "max_cycles": 300,
        },
    }
    val_res = client.post("/api/v1/scenarios/validate", json=payload)
    assert val_res.status_code == 200
    d = val_res.json()
    assert d["is_valid"] is False
    assert any("Global computational work budget exceeded" in err for err in d["errors"])

    # Must also be rejected on /optimize/run with 400
    opt_res = client.post("/api/v1/optimize/run", json=payload)
    assert opt_res.status_code == 400
    assert "Global computational work budget exceeded" in opt_res.json()["detail"]


def test_defect_d_normal_academic_scenarios_accepted(client: TestClient) -> None:
    """DEFECTO D: Normal academic benchmarks are comfortably within the computational budget."""
    # Scenario 1: Small classroom (K=2, SN=10, max_cycles=20, 20x20m at res=2.0m -> ~100 nodes)
    # work_upper = 430 * 2 * 100 = 86,000 << 100M
    res1 = client.post(
        "/api/v1/scenarios/validate",
        json={
            "scenario": {"xmax": 20.0, "ymax": 20.0, "grid_resolution": 2.0},
            "config": {"K": 2, "SN": 10, "max_cycles": 20},
        },
    )
    assert res1.status_code == 200
    assert res1.json()["is_valid"] is True

    # Scenario 2: Standard partitioned office (K=4, SN=20, max_cycles=40, 24x16m at res=1.0m -> ~384 nodes)
    # work_upper = 1660 * 4 * 384 = 2,549,760 << 100M
    res2 = client.post(
        "/api/v1/scenarios/validate",
        json={
            "scenario": {"xmax": 24.0, "ymax": 16.0, "grid_resolution": 1.0},
            "config": {"K": 4, "SN": 20, "max_cycles": 40},
        },
    )
    assert res2.status_code == 200
    assert res2.json()["is_valid"] is True

    # Scenario 3: Large laboratory (K=6, SN=30, max_cycles=60, 30x20m at res=1.0m -> ~600 nodes)
    # work_upper = 3690 * 6 * 600 = 13,284,000 << 100M
    res3 = client.post(
        "/api/v1/scenarios/validate",
        json={
            "scenario": {"xmax": 30.0, "ymax": 20.0, "grid_resolution": 1.0},
            "config": {"K": 6, "SN": 30, "max_cycles": 60},
        },
    )
    assert res3.status_code == 200
    assert res3.json()["is_valid"] is True


def test_defect_d_population_history_budget_exceeded_rejected(client: TestClient) -> None:
    """DEFECTO D: Excessive population history allocation is rejected before running ABC."""
    # (MaxCycles + 1) * SN * K = (201) * 50 * 20 = 201,000 > 50,000
    payload = {
        "scenario": {
            "xmax": 20.0,
            "ymax": 20.0,
            "grid_resolution": 2.0,
        },
        "config": {
            "K": 20,
            "SN": 50,
            "max_cycles": 200,
            "record_population": True,
        },
    }
    val_res = client.post("/api/v1/scenarios/validate", json=payload)
    assert val_res.status_code == 200
    d = val_res.json()
    assert d["is_valid"] is False
    assert any("Population history size limit exceeded" in err for err in d["errors"])

    # Without record_population, the same configuration is accepted (work_upper is well within budget)
    payload["config"]["record_population"] = False
    val_res_ok = client.post("/api/v1/scenarios/validate", json=payload)
    assert val_res_ok.status_code == 200
    assert val_res_ok.json()["is_valid"] is True


def test_defect_e_mathematical_consistency_of_results(client: TestClient) -> None:
    """DEFECTO E: Output objective cost exactly matches f(X) = (1 - C_risk) + lambda_def * Deficit_crit."""
    scenario = {
        "xmin": 0.0,
        "xmax": 16.0,
        "ymin": 0.0,
        "ymax": 16.0,
        "grid_resolution": 1.5,
        "risk_zones": [
            {
                "vertices": [
                    {"x": 4.0, "y": 4.0},
                    {"x": 10.0, "y": 4.0},
                    {"x": 10.0, "y": 10.0},
                    {"x": 4.0, "y": 10.0},
                ],
                "weight": 3.0,
                "name": "High Security Zone",
            }
        ],
    }
    lambda_def = 1.75
    payload = {
        "scenario": scenario,
        "config": {
            "K": 3,
            "SN": 8,
            "max_cycles": 5,
            "seed": 42,
            "lambda_def": lambda_def,
            "Tcrit": 0.8,
            "record_population": False,
        },
    }
    response = client.post("/api/v1/optimize/run", json=payload)
    assert response.status_code == 200
    data = response.json()

    cost = data["final_best_cost"]
    metrics = data["coverage_metrics"]
    c_risk = metrics["risk_weighted_coverage"]
    deficit_crit = metrics["critical_deficit"]

    # Mathematical identity verification
    expected_cost = max(0.0, (1.0 - c_risk) + lambda_def * deficit_crit)
    assert math.isclose(cost, expected_cost, rel_tol=1e-9, abs_tol=1e-12)

    # Initial cost >= final cost
    assert data["initial_best_cost"] >= data["final_best_cost"]


def test_defect_e_technical_lead_exact_audit_scenario(client: TestClient) -> None:
    """DEFECTO E: Exact reproduction of the technical lead's audit execution with seed=42.

    Matches exactly:
    - Initial cost: 1.4690508303
    - Final cost: 0.7012359027
    - Evaluation points: 378
    - Total evaluations (NFE): 287
    - Infeasible proposals rejected: 23
    - Total neighbor proposals: 310
    - Mathematical consistency: f(X) == (1 - C_risk) + lambda_def * Deficit_crit
    """
    payload = {
        "scenario": {
            "xmin": 0.0,
            "xmax": 24.0,
            "ymin": 0.0,
            "ymax": 16.0,
            "walls": [
                {"start": {"x": 0.0, "y": 8.0}, "end": {"x": 10.0, "y": 8.0}, "is_opaque": True},
                {"start": {"x": 12.0, "y": 8.0}, "end": {"x": 24.0, "y": 8.0}, "is_opaque": True},
            ],
            "obstacles": [
                {
                    "vertices": [
                        {"x": 4.0, "y": 3.0}, {"x": 7.0, "y": 3.0},
                        {"x": 7.0, "y": 5.0}, {"x": 4.0, "y": 5.0},
                    ]
                }
            ],
            "risk_zones": [
                {
                    "vertices": [
                        {"x": 1.0, "y": 9.0}, {"x": 6.0, "y": 9.0},
                        {"x": 6.0, "y": 15.0}, {"x": 1.0, "y": 15.0},
                    ],
                    "weight": 3.5,
                    "name": "Server Room",
                }
            ],
            "grid_resolution": 1.0,
        },
        "profile": {
            "Rmin": 0.2,
            "Rmax": 11.0,
            "FOV": 1.5707963,
            "p0": 1.0,
            "beta_d": 0.4,
            "beta_theta": 0.5,
        },
        "config": {
            "K": 3,
            "SN": 10,
            "max_cycles": 15,
            "limit": 45,
            "seed": 42,
            "lambda_def": 1.0,
            "Tcrit": 0.8,
            "record_population": True,
        },
    }

    res = client.post("/api/v1/optimize/run", json=payload)
    assert res.status_code == 200
    data = res.json()

    # Exact metrics matching auditor's findings
    assert data["coverage_metrics"]["num_eval_points"] == 378
    assert data["total_evaluations"] == 287
    assert data["rejected_infeasible_proposals"] == 23
    assert data["total_proposals"] == 310

    # Costs matching auditor's values
    assert math.isclose(data["initial_best_cost"], 1.46905083027, rel_tol=1e-8)
    assert math.isclose(data["final_best_cost"], 0.70123590272, rel_tol=1e-8)

    # Cost improvement
    assert data["initial_best_cost"] > data["final_best_cost"]

    # Exact internal mathematical consistency
    c_risk = data["coverage_metrics"]["risk_weighted_coverage"]
    deficit = data["coverage_metrics"]["critical_deficit"]
    expected_cost = (1.0 - c_risk) + 1.0 * deficit
    assert math.isclose(data["final_best_cost"], expected_cost, abs_tol=1e-12)

