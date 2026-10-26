"""Automated test suite for the Coverage Evaluation API endpoint (TAREA 07 / Fase 5B).

Verifies:
- Exact numerical match between ConfigurationEvaluator and POST /api/v1/coverage/evaluate
- Point probabilities, binary mask, aggregated metrics, objective cost
- Opaque wall blocking line of sight
- Free opening/doorway permitting line of sight
- Solid obstacle interior exclusion and shadow occlusion
- Absence of coverage (zero coverage)
- Multi-camera overlapping coverage: P = 1 - (1 - P1)(1 - P2)
- Angular continuity near ±pi
- Weighted risk zone contribution
- Rejection of infeasible camera configurations (outside room, in obstacle, on wall)
- Coherence of aggregated metrics reconstructed from per-node response
"""

from __future__ import annotations

import math
import numpy as np
import pytest
from fastapi.testclient import TestClient

from camera_optimizer.api.app import create_app
from camera_optimizer.api.service import OptimizationService
from camera_optimizer.camera.pose import CameraPose
from camera_optimizer.camera.profile import CameraProfile
from camera_optimizer.domain.floorplan import FloorPlan
from camera_optimizer.domain.grid import SamplingGrid
from camera_optimizer.domain.obstacle import ObstaclePolygon
from camera_optimizer.domain.risk_zone import RiskZone
from camera_optimizer.domain.wall import WallSegment
from camera_optimizer.geometry.bounding_box import BoundingBox
from camera_optimizer.geometry.point import Point2D
from camera_optimizer.objective.config import ObjectiveConfig
from camera_optimizer.objective.evaluator import ConfigurationEvaluator


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_coverage_endpoint_matches_direct_evaluator(client: TestClient) -> None:
    """Mandatory test: Known configuration evaluated directly via ConfigurationEvaluator

    and via POST /api/v1/coverage/evaluate must produce identical results across:
    - Probabilities per node
    - Binary geometric mask
    - Mean coverage
    - Risk weighted coverage
    - Critical deficit
    - Objective cost
    - Node coordinates and order matching SamplingGrid.nodes
    """
    # 1. Setup scenario
    scenario_dict = {
        "xmin": 0.0,
        "xmax": 20.0,
        "ymin": 0.0,
        "ymax": 20.0,
        "grid_resolution": 1.0,
        "walls": [
            {"start": {"x": 5.0, "y": 0.0}, "end": {"x": 5.0, "y": 10.0}, "is_opaque": True}
        ],
        "obstacles": [
            {
                "vertices": [
                    {"x": 12.0, "y": 12.0},
                    {"x": 16.0, "y": 12.0},
                    {"x": 16.0, "y": 16.0},
                    {"x": 12.0, "y": 16.0},
                ]
            }
        ],
        "risk_zones": [
            {
                "vertices": [
                    {"x": 2.0, "y": 2.0},
                    {"x": 4.0, "y": 2.0},
                    {"x": 4.0, "y": 4.0},
                    {"x": 2.0, "y": 4.0},
                ],
                "weight": 2.5,
                "name": "Vault",
            }
        ],
    }

    profile_dict = {
        "Rmin": 0.5,
        "Rmax": 12.0,
        "FOV": math.pi / 2.0,
        "p0": 1.0,
        "beta_d": 0.3,
        "beta_theta": 0.4,
    }

    cameras_dict = [
        {"x": 2.0, "y": 8.0, "theta": 0.0, "theta_deg": 0.0},
        {"x": 10.0, "y": 5.0, "theta": math.pi / 4.0, "theta_deg": 45.0},
        {"x": 8.0, "y": 18.0, "theta": -math.pi / 2.0, "theta_deg": -90.0},
    ]

    lambda_def = 1.5
    t_crit = 0.85

    # 2. Direct evaluation using ConfigurationEvaluator
    service = OptimizationService()
    from camera_optimizer.api.schemas import CameraProfileDTO, CameraPoseDTO, ScenarioDTO
    sc_dto = ScenarioDTO(**scenario_dict)
    pr_dto = CameraProfileDTO(**profile_dict)

    floorplan = service.build_floorplan(sc_dto)
    grid = service.build_sampling_grid(floorplan, sc_dto.grid_resolution)
    profile = service.build_camera_profile(pr_dto)
    config = ObjectiveConfig(lambda_def=lambda_def, t_crit=t_crit)

    evaluator = ConfigurationEvaluator(floorplan, grid, profile=profile, config=config)
    domain_cameras = [CameraPose(x=c["x"], y=c["y"], theta=c["theta"]) for c in cameras_dict]
    direct_res = evaluator.evaluate(domain_cameras)
    assert direct_res.is_feasible is True
    assert direct_res.metrics is not None

    # 3. API evaluation via endpoint
    payload = {
        "scenario": scenario_dict,
        "profile": profile_dict,
        "cameras": cameras_dict,
        "lambda_def": lambda_def,
        "t_crit": t_crit,
    }

    resp = client.post("/api/v1/coverage/evaluate", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # 4. Rigorous numerical comparison
    assert data["total_nodes"] == len(grid.nodes)
    assert data["cell_width"] == pytest.approx(grid.cell_width, abs=1e-12)
    assert data["cell_height"] == pytest.approx(grid.cell_height, abs=1e-12)
    assert data["is_feasible"] is True
    assert data["objective_cost"] == pytest.approx(direct_res.objective_cost, abs=1e-12)

    api_metrics = data["metrics"]
    direct_metrics = direct_res.metrics

    assert api_metrics["num_eval_points"] == direct_metrics.num_eval_points
    assert api_metrics["num_covered_points"] == direct_metrics.num_covered_points
    assert api_metrics["geometric_coverage_ratio"] == pytest.approx(
        direct_metrics.geometric_coverage_ratio, abs=1e-12
    )
    assert api_metrics["geometric_coverage_percent"] == pytest.approx(
        direct_metrics.geometric_coverage_percent, abs=1e-12
    )
    assert api_metrics["mean_probabilistic_coverage"] == pytest.approx(
        direct_metrics.mean_probabilistic_coverage, abs=1e-12
    )
    assert api_metrics["risk_weighted_coverage"] == pytest.approx(
        direct_metrics.risk_weighted_coverage, abs=1e-12
    )
    assert api_metrics["num_critical_points"] == direct_metrics.num_critical_points
    assert api_metrics["critical_deficit"] == pytest.approx(direct_metrics.critical_deficit, abs=1e-12)

    # 5. Check 1-to-1 node correspondence in exact order
    nodes = data["nodes"]
    assert len(nodes) == len(grid.nodes)

    for i, (node_data, grid_node) in enumerate(zip(nodes, grid.nodes)):
        assert node_data["x"] == pytest.approx(grid_node.point.x, abs=1e-12)
        assert node_data["y"] == pytest.approx(grid_node.point.y, abs=1e-12)
        assert node_data["probability"] == pytest.approx(
            float(direct_metrics.point_probabilities[i]), abs=1e-12
        )
        assert node_data["binary_covered"] == bool(direct_metrics.point_binary_covered[i])
        assert node_data["risk_weight"] == pytest.approx(grid_node.weight, abs=1e-12)


def test_coverage_opaque_wall_occlusion(client: TestClient) -> None:
    """Opaque wall strictly blocks line of sight."""
    scenario = {
        "xmin": 0.0,
        "xmax": 20.0,
        "ymin": 0.0,
        "ymax": 20.0,
        "grid_resolution": 1.0,
        "walls": [
            {"start": {"x": 10.0, "y": 0.0}, "end": {"x": 10.0, "y": 20.0}, "is_opaque": True}
        ],
    }

    # Camera at (5, 10) facing right (theta = 0)
    cameras = [{"x": 5.0, "y": 10.0, "theta": 0.0}]

    resp = client.post("/api/v1/coverage/evaluate", json={"scenario": scenario, "cameras": cameras})
    assert resp.status_code == 200
    data = resp.json()

    # Points with x > 10 must have zero probability and binary_covered = False
    for node in data["nodes"]:
        if node["x"] > 10.0:
            assert node["binary_covered"] is False
            assert node["probability"] == 0.0


def test_coverage_free_doorway_opening(client: TestClient) -> None:
    """Wall with doorway opening permits line of sight through the opening only."""
    scenario = {
        "xmin": 0.0,
        "xmax": 20.0,
        "ymin": 0.0,
        "ymax": 20.0,
        "grid_resolution": 1.0,
        "walls": [
            # Wall with opening between y=8 and y=12
            {"start": {"x": 10.0, "y": 0.0}, "end": {"x": 10.0, "y": 8.0}, "is_opaque": True},
            {"start": {"x": 10.0, "y": 12.0}, "end": {"x": 10.0, "y": 20.0}, "is_opaque": True},
        ],
    }

    # Camera at (5, 10) pointing east (theta = 0)
    cameras = [{"x": 5.0, "y": 10.0, "theta": 0.0}]

    resp = client.post("/api/v1/coverage/evaluate", json={"scenario": scenario, "cameras": cameras})
    assert resp.status_code == 200
    data = resp.json()

    # Node directly through opening at x=15, y=10 should be visible
    opening_nodes = [n for n in data["nodes"] if abs(n["x"] - 14.5) < 0.6 and abs(n["y"] - 9.5) < 0.6]
    assert len(opening_nodes) > 0
    assert any(n["binary_covered"] is True for n in opening_nodes)
    assert any(n["probability"] > 0.0 for n in opening_nodes)

    # Node behind upper wall segment at x=15, y=16 should be blocked
    blocked_nodes = [n for n in data["nodes"] if abs(n["x"] - 14.5) < 0.6 and abs(n["y"] - 15.5) < 0.6]
    assert len(blocked_nodes) > 0
    for n in blocked_nodes:
        assert n["binary_covered"] is False
        assert n["probability"] == 0.0


def test_coverage_obstacle_exclusion_and_shadow(client: TestClient) -> None:
    """Solid obstacles exclude nodes from their interior and cast geometric shadows."""
    scenario = {
        "xmin": 0.0,
        "xmax": 20.0,
        "ymin": 0.0,
        "ymax": 20.0,
        "grid_resolution": 1.0,
        "obstacles": [
            {
                "vertices": [
                    {"x": 8.0, "y": 8.0},
                    {"x": 12.0, "y": 8.0},
                    {"x": 12.0, "y": 12.0},
                    {"x": 8.0, "y": 12.0},
                ]
            }
        ],
    }

    resp = client.post(
        "/api/v1/coverage/evaluate",
        json={"scenario": scenario, "cameras": [{"x": 4.0, "y": 10.0, "theta": 0.0}]},
    )
    assert resp.status_code == 200
    data = resp.json()

    # 1. No node should be inside obstacle [8, 12] x [8, 12]
    for node in data["nodes"]:
        is_inside = 8.0 < node["x"] < 12.0 and 8.0 < node["y"] < 12.0
        assert not is_inside, f"Node at ({node['x']}, {node['y']}) fell inside obstacle interior!"

    # 2. Points in shadow behind obstacle at x=15, y=10 should be blocked
    shadow_nodes = [n for n in data["nodes"] if abs(n["x"] - 15.5) < 0.6 and abs(n["y"] - 9.5) < 0.6]
    assert len(shadow_nodes) > 0
    for n in shadow_nodes:
        assert n["binary_covered"] is False
        assert n["probability"] == 0.0


def test_coverage_absence_of_coverage(client: TestClient) -> None:
    """When cameras point away or have 0 coverage, probability and coverage are 0."""
    scenario = {
        "xmin": 0.0,
        "xmax": 20.0,
        "ymin": 0.0,
        "ymax": 20.0,
        "grid_resolution": 2.0,
    }

    # Camera placed near left wall pointing west (outside room boundary) with narrow range
    profile = {
        "Rmin": 0.0,
        "Rmax": 1.0,
        "FOV": 0.5,
        "p0": 1.0,
        "beta_d": 0.5,
        "beta_theta": 0.5,
    }

    # Camera at (0.5, 10.0) pointing directly at left boundary wall
    cameras = [{"x": 0.5, "y": 10.0, "theta": math.pi}]

    resp = client.post(
        "/api/v1/coverage/evaluate",
        json={"scenario": scenario, "profile": profile, "cameras": cameras},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["metrics"]["num_covered_points"] == 0
    assert data["metrics"]["geometric_coverage_ratio"] == 0.0
    assert data["metrics"]["mean_probabilistic_coverage"] == 0.0
    assert all(n["probability"] == 0.0 for n in data["nodes"])
    assert all(n["binary_covered"] is False for n in data["nodes"])


def test_coverage_two_cameras_overlap(client: TestClient) -> None:
    """Overlapping cameras combine probabilities via P = 1 - (1 - P1)(1 - P2)."""
    scenario = {
        "xmin": 0.0,
        "xmax": 20.0,
        "ymin": 0.0,
        "ymax": 20.0,
        "grid_resolution": 1.0,
    }

    # Single camera 1
    cam1 = [{"x": 5.0, "y": 10.0, "theta": 0.0}]
    resp1 = client.post(
        "/api/v1/coverage/evaluate", json={"scenario": scenario, "cameras": cam1}
    )
    nodes1 = resp1.json()["nodes"]

    # Single camera 2
    cam2 = [{"x": 10.0, "y": 5.0, "theta": math.pi / 2.0}]
    resp2 = client.post(
        "/api/v1/coverage/evaluate", json={"scenario": scenario, "cameras": cam2}
    )
    nodes2 = resp2.json()["nodes"]

    # Both cameras together
    resp_both = client.post(
        "/api/v1/coverage/evaluate", json={"scenario": scenario, "cameras": cam1 + cam2}
    )
    nodes_both = resp_both.json()["nodes"]

    for n1, n2, nb in zip(nodes1, nodes2, nodes_both):
        expected_p = 1.0 - (1.0 - n1["probability"]) * (1.0 - n2["probability"])
        assert nb["probability"] == pytest.approx(expected_p, abs=1e-12)
        assert nb["binary_covered"] == (n1["binary_covered"] or n2["binary_covered"])


def test_coverage_angles_near_plus_minus_pi(client: TestClient) -> None:
    """Angles near ±pi evaluate properly without boundary discontinuities or errors."""
    scenario = {
        "xmin": 0.0,
        "xmax": 20.0,
        "ymin": 0.0,
        "ymax": 20.0,
        "grid_resolution": 2.0,
    }

    # Cam 1 near +pi, Cam 2 near -pi
    cameras = [
        {"x": 10.0, "y": 10.0, "theta": math.pi - 0.01},
        {"x": 10.0, "y": 15.0, "theta": -math.pi + 0.01},
    ]

    resp = client.post(
        "/api/v1/coverage/evaluate", json={"scenario": scenario, "cameras": cameras}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_feasible"] is True
    # Both cameras face west (negative x), so nodes at x < 10 must have coverage
    covered_west = [n for n in data["nodes"] if n["x"] < 10.0 and n["binary_covered"]]
    assert len(covered_west) > 0


def test_coverage_weighted_risks_contribution(client: TestClient) -> None:
    """High risk zones scale node risk weights and contribute to risk-weighted metrics."""
    scenario = {
        "xmin": 0.0,
        "xmax": 20.0,
        "ymin": 0.0,
        "ymax": 20.0,
        "grid_resolution": 2.0,
        "risk_zones": [
            {
                "vertices": [
                    {"x": 2.0, "y": 2.0},
                    {"x": 8.0, "y": 2.0},
                    {"x": 8.0, "y": 8.0},
                    {"x": 2.0, "y": 8.0},
                ],
                "weight": 3.0,
                "name": "HighRiskZone",
            }
        ],
    }

    cameras = [{"x": 10.0, "y": 10.0, "theta": -2.35}]  # pointing towards risk zone

    resp = client.post(
        "/api/v1/coverage/evaluate", json={"scenario": scenario, "cameras": cameras}
    )
    assert resp.status_code == 200
    data = resp.json()

    # Verify risk weights
    for node in data["nodes"]:
        if 2.0 < node["x"] < 8.0 and 2.0 < node["y"] < 8.0:
            assert node["risk_weight"] == 3.0
        else:
            assert node["risk_weight"] == 1.0

    assert data["metrics"]["num_critical_points"] > 0


def test_coverage_infeasible_configurations_rejected(client: TestClient) -> None:
    """Infeasible cameras (outside bounds, inside obstacle, on wall) return HTTP 400."""
    scenario = {
        "xmin": 0.0,
        "xmax": 20.0,
        "ymin": 0.0,
        "ymax": 20.0,
        "walls": [
            {"start": {"x": 5.0, "y": 0.0}, "end": {"x": 5.0, "y": 10.0}, "is_opaque": True}
        ],
        "obstacles": [
            {
                "vertices": [
                    {"x": 12.0, "y": 12.0},
                    {"x": 16.0, "y": 12.0},
                    {"x": 16.0, "y": 16.0},
                    {"x": 12.0, "y": 16.0},
                ]
            }
        ],
    }

    # 1. Camera outside room perimeter
    resp_outside = client.post(
        "/api/v1/coverage/evaluate",
        json={"scenario": scenario, "cameras": [{"x": -1.0, "y": 10.0, "theta": 0.0}]},
    )
    assert resp_outside.status_code == 400
    assert "Infeasible camera configuration" in resp_outside.json()["detail"]
    assert "outside or on perimeter boundary" in resp_outside.json()["detail"]

    # 2. Camera inside obstacle
    resp_obstacle = client.post(
        "/api/v1/coverage/evaluate",
        json={"scenario": scenario, "cameras": [{"x": 14.0, "y": 14.0, "theta": 0.0}]},
    )
    assert resp_obstacle.status_code == 400
    assert "inside or on boundary of obstacle" in resp_obstacle.json()["detail"]

    # 3. Camera on interior wall
    resp_wall = client.post(
        "/api/v1/coverage/evaluate",
        json={"scenario": scenario, "cameras": [{"x": 5.0, "y": 5.0, "theta": 0.0}]},
    )
    assert resp_wall.status_code == 400
    assert "coincides with interior wall" in resp_wall.json()["detail"]


def test_aggregated_metrics_coherence_with_node_data(client: TestClient) -> None:
    """Reconstructed aggregated metrics from the nodes array must match response.metrics."""
    scenario = {
        "xmin": 0.0,
        "xmax": 15.0,
        "ymin": 0.0,
        "ymax": 15.0,
        "grid_resolution": 1.0,
        "risk_zones": [
            {
                "vertices": [
                    {"x": 1.0, "y": 1.0},
                    {"x": 5.0, "y": 1.0},
                    {"x": 5.0, "y": 5.0},
                    {"x": 1.0, "y": 5.0},
                ],
                "weight": 2.0,
            }
        ],
    }

    cameras = [
        {"x": 2.0, "y": 2.0, "theta": 0.5},
        {"x": 8.0, "y": 8.0, "theta": -1.0},
    ]

    t_crit = 0.8
    lambda_def = 1.2

    resp = client.post(
        "/api/v1/coverage/evaluate",
        json={
            "scenario": scenario,
            "cameras": cameras,
            "t_crit": t_crit,
            "lambda_def": lambda_def,
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    nodes = data["nodes"]
    metrics = data["metrics"]

    # 1. Total nodes count
    assert len(nodes) == metrics["num_eval_points"]

    # 2. Binary covered count
    covered_count = sum(1 for n in nodes if n["binary_covered"])
    assert covered_count == metrics["num_covered_points"]

    # 3. Geometric coverage ratio
    geo_ratio = covered_count / len(nodes)
    assert geo_ratio == pytest.approx(metrics["geometric_coverage_ratio"], abs=1e-12)
    assert (geo_ratio * 100.0) == pytest.approx(metrics["geometric_coverage_percent"], abs=1e-12)

    # 4. Mean probabilistic coverage
    probs = [n["probability"] for n in nodes]
    assert np.mean(probs) == pytest.approx(metrics["mean_probabilistic_coverage"], abs=1e-12)

    # 5. Risk weighted coverage: sum(w_i * P_i) / sum(w_i)
    weights = [n["risk_weight"] for n in nodes]
    weighted_cov = sum(w * p for w, p in zip(weights, probs)) / sum(weights)
    assert weighted_cov == pytest.approx(metrics["risk_weighted_coverage"], abs=1e-12)

    # 6. Critical points deficit: sum(scaled_w * max(0, Tcrit - P_j)) / sum(scaled_w)
    crit_nodes = [n for n in nodes if n["risk_weight"] > 1.0]
    assert len(crit_nodes) == metrics["num_critical_points"]
    if crit_nodes:
        crit_weights = [n["risk_weight"] for n in crit_nodes]
        max_w = max(crit_weights)
        scaled_w = [w / max_w for w in crit_weights]
        crit_shortfall = [max(0.0, t_crit - n["probability"]) for n in crit_nodes]
        expected_deficit = sum(sw * sf for sw, sf in zip(scaled_w, crit_shortfall)) / sum(scaled_w)
        assert expected_deficit == pytest.approx(metrics["critical_deficit"], abs=1e-12)

    # 7. Objective cost f(X) = (1 - C_risk) + lambda_def * Deficit_crit
    expected_cost = (1.0 - weighted_cov) + lambda_def * metrics["critical_deficit"]
    assert expected_cost == pytest.approx(data["objective_cost"], abs=1e-12)


def test_coverage_rejects_k_zero_and_k_thirty_one(client: TestClient) -> None:
    """PRUEBA 6: Coverage endpoint rejects empty camera configuration (K=0) and K=31 (> max_cameras=30)."""
    scenario = {
        "xmin": 0.0,
        "xmax": 10.0,
        "ymin": 0.0,
        "ymax": 10.0,
        "grid_resolution": 2.0,
    }

    # Case 1: Empty camera list (K=0)
    resp_empty = client.post(
        "/api/v1/coverage/evaluate",
        json={"scenario": scenario, "cameras": []},
    )
    assert resp_empty.status_code in (400, 422)

    # Case 2: 31 cameras (K=31 > max_cameras=30)
    cameras_31 = [{"x": 5.0, "y": 5.0, "theta": 0.0} for _ in range(31)]
    resp_31 = client.post(
        "/api/v1/coverage/evaluate",
        json={"scenario": scenario, "cameras": cameras_31},
    )
    assert resp_31.status_code in (400, 422)

    # Case 3: Valid boundary K=1
    cameras_1 = [{"x": 5.0, "y": 5.0, "theta": 0.0}]
    resp_1 = client.post(
        "/api/v1/coverage/evaluate",
        json={"scenario": scenario, "cameras": cameras_1},
    )
    assert resp_1.status_code == 200

    # Case 4: Valid boundary K=30
    cameras_30 = [{"x": 5.0, "y": 5.0, "theta": float(i) * 0.1} for i in range(30)]
    resp_30 = client.post(
        "/api/v1/coverage/evaluate",
        json={"scenario": scenario, "cameras": cameras_30},
    )
    assert resp_30.status_code == 200


def test_coverage_rejects_excessive_computational_workload(client: TestClient) -> None:
    """PRUEBA 7: Excessive spatial evaluation workload is rejected with controlled HTTP 400 before raytracing."""
    # 50m x 50m room at 0.25m resolution -> 40,000 cells (within max_grid_cells=50,000)
    # With 30 cameras and 40 blocking walls:
    # workload ≈ 30 * 40,000 * (1 + 40) = 49,200,000 > max_coverage_work_budget (25,000,000)
    walls = [
        {"start": {"x": 1.0, "y": float(i)}, "end": {"x": 49.0, "y": float(i)}, "is_opaque": True}
        for i in range(1, 41)
    ]
    cameras = [{"x": 25.0, "y": 25.0, "theta": float(i) * 0.1} for i in range(30)]

    payload = {
        "scenario": {
            "xmin": 0.0,
            "xmax": 50.0,
            "ymin": 0.0,
            "ymax": 50.0,
            "grid_resolution": 0.25,
            "walls": walls,
        },
        "cameras": cameras,
    }

    resp = client.post("/api/v1/coverage/evaluate", json=payload)
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "Coverage evaluation workload budget exceeded" in detail


def test_coverage_academic_scenarios_normal_evaluation_allowed(client: TestClient) -> None:
    """PRUEBA 8: Normal academic scenarios evaluate with 200 OK without hitting workload limits."""
    # Retrieve predefined scenarios
    scenarios_resp = client.get("/api/v1/scenarios")
    assert scenarios_resp.status_code == 200
    scenarios_list = scenarios_resp.json()["scenarios"]
    assert len(scenarios_list) >= 3

    for item in scenarios_list:
        scenario = item["scenario"]
        profile = item["recommended_profile"]

        if item["id"] == "empty_warehouse":
            cameras = [
                {"x": 5.0, "y": 5.0, "theta": 0.5},
                {"x": 15.0, "y": 5.0, "theta": 2.5},
                {"x": 10.0, "y": 15.0, "theta": -1.5},
            ]
        elif item["id"] == "partitioned_office":
            cameras = [
                {"x": 2.0, "y": 2.0, "theta": 0.8},
                {"x": 2.0, "y": 12.0, "theta": -0.8},
                {"x": 14.0, "y": 14.0, "theta": 2.3},
            ]
        else:  # museum_gallery
            cameras = [
                {"x": 2.0, "y": 5.0, "theta": 0.7},
                {"x": 20.0, "y": 2.0, "theta": 2.4},
                {"x": 26.0, "y": 16.0, "theta": -1.57},
            ]

        resp = client.post(
            "/api/v1/coverage/evaluate",
            json={
                "scenario": scenario,
                "profile": profile,
                "cameras": cameras,
                "lambda_def": 1.0,
                "t_crit": 0.8,
            },
        )
        assert resp.status_code == 200, f"Failed for scenario {item['id']}: {resp.text}"
        data = resp.json()
        assert data["total_nodes"] > 0
        assert 0.0 <= data["metrics"]["mean_probabilistic_coverage"] <= 1.0


def test_coverage_mutual_exclusion_and_http_409(client: TestClient) -> None:
    """PRUEBA 9: Shared mutual exclusion ensures coverage evaluation returns 409 when service is busy.

    Also verifies:
    - Optimization returns 409 when coverage evaluation is running.
    - GET /health remains available with is_busy=True during lock acquisition.
    - Lock is safely released even on exception.
    """
    from camera_optimizer.api.router import get_optimization_service

    service = get_optimization_service()
    assert service.is_busy is False

    scenario = {
        "xmin": 0.0,
        "xmax": 10.0,
        "ymin": 0.0,
        "ymax": 10.0,
        "grid_resolution": 2.0,
    }
    cameras = [{"x": 5.0, "y": 5.0, "theta": 0.0}]

    # 1. Acquire service execution lock artificially (simulating in-progress ABC optimization)
    acquired = service._lock.acquire(blocking=False)
    assert acquired is True
    assert service.is_busy is True

    try:
        # GET /health must remain available and report is_busy=True
        health_resp = client.get("/api/v1/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["is_busy"] is True

        # Coverage evaluation must be rejected with HTTP 409 Conflict
        cov_resp = client.post(
            "/api/v1/coverage/evaluate",
            json={"scenario": scenario, "cameras": cameras},
        )
        assert cov_resp.status_code == 409
        assert "Another optimization or coverage evaluation is currently executing" in cov_resp.json()["detail"]

        # ABC optimization must also be rejected with HTTP 409 Conflict
        opt_resp = client.post(
            "/api/v1/optimize/run",
            json={"scenario": scenario, "config": {"K": 1, "SN": 2, "max_cycles": 1}},
        )
        assert opt_resp.status_code == 409
    finally:
        service._lock.release()
        assert service.is_busy is False

    # After releasing lock, both GET /health reports is_busy=False and evaluate_coverage succeeds with 200
    health_after = client.get("/api/v1/health")
    assert health_after.status_code == 200
    assert health_after.json()["is_busy"] is False

    cov_after = client.post(
        "/api/v1/coverage/evaluate",
        json={"scenario": scenario, "cameras": cameras},
    )
    assert cov_after.status_code == 200
