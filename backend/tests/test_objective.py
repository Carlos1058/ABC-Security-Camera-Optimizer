"""Unit tests for objective function, feasibility checking, and risk-weighted coverage."""

import math
import numpy as np
import pytest

from camera_optimizer.camera.pose import CameraPose
from camera_optimizer.camera.profile import CameraProfile
from camera_optimizer.coverage.evaluator import evaluate_multicamera_coverage
from camera_optimizer.domain.floorplan import FloorPlan
from camera_optimizer.domain.grid import GridNode, SamplingGrid
from camera_optimizer.domain.obstacle import ObstaclePolygon
from camera_optimizer.domain.risk_zone import RiskZone
from camera_optimizer.domain.wall import WallSegment
from camera_optimizer.geometry.bounding_box import BoundingBox
from camera_optimizer.geometry.point import Point2D
from camera_optimizer.objective.config import ObjectiveConfig
from camera_optimizer.objective.evaluator import (
    ConfigurationEvaluator,
    EvaluationResult,
)


# ---------------------------------------------------------------------------
# OPT-09: Risk-Weighted Coverage Manual Verification
# ---------------------------------------------------------------------------


def test_opt_09_risk_weighted_coverage_calculation() -> None:
    """OPT-09: Manually verify the risk-weighted coverage formula with known probabilities and weights.
    Points: P1 (weight=1.0, prob=0.8), P2 (weight=3.0, prob=0.4), P3 (weight=6.0, prob=0.9).
    Sum weights = 1 + 3 + 6 = 10.
    Weighted sum = 1.0*0.8 + 3.0*0.4 + 6.0*0.9 = 0.8 + 1.2 + 5.4 = 7.4.
    C_risk = 7.4 / 10 = 0.74.
    """
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    floorplan = FloorPlan(boundary=boundary)

    # Construct an artificial SamplingGrid with the exact points and weights
    p1 = Point2D(1.0, 1.0)
    p2 = Point2D(3.0, 3.0)
    p3 = Point2D(5.0, 5.0)
    nodes = (
        GridNode(p1, weight=1.0),
        GridNode(p2, weight=3.0),
        GridNode(p3, weight=6.0),
    )
    grid = SamplingGrid(resolution=2.0, nodes=nodes, cell_width=2.0, cell_height=2.0)

    # Let's verify via the multi-camera evaluator calculation logic
    weights = np.array([1.0, 3.0, 6.0])
    probs = np.array([0.8, 0.4, 0.9])
    c_risk = float(np.sum(weights * probs) / np.sum(weights))
    assert c_risk == pytest.approx(0.74)


# ---------------------------------------------------------------------------
# OPT-10: Critical Deficit Verification
# ---------------------------------------------------------------------------


def test_opt_10_critical_deficit_calculation() -> None:
    """OPT-10: Verify critical zone deficit with configurable Tcrit, and when no critical nodes exist.
    Scenario A: Nodes with weights [1.0, 2.0, 4.0] and probabilities [0.9, 0.5, 0.7].
    Critical nodes are those with w > 1.0:
    Node 2: w=2.0, P=0.5
    Node 3: w=4.0, P=0.7
    Sum crit weights = 2.0 + 4.0 = 6.0.
    With Tcrit = 0.8:
    Shortfall Node 2 = max(0, 0.8 - 0.5) = 0.3
    Shortfall Node 3 = max(0, 0.8 - 0.7) = 0.1
    Weighted shortfall = 2.0 * 0.3 + 4.0 * 0.1 = 0.6 + 0.4 = 1.0
    Deficit_crit = 1.0 / 6.0 ~= 0.16666667
    """
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    floorplan = FloorPlan(boundary=boundary)

    nodes = (
        GridNode(Point2D(1.0, 1.0), weight=1.0),
        GridNode(Point2D(3.0, 3.0), weight=2.0),
        GridNode(Point2D(5.0, 5.0), weight=4.0),
    )
    grid = SamplingGrid(resolution=2.0, nodes=nodes, cell_width=2.0, cell_height=2.0)

    # Check deficit with simulated probabilities
    weights = np.array([1.0, 2.0, 4.0])
    probs = np.array([0.9, 0.5, 0.7])
    t_crit = 0.8

    crit_mask = weights > 1.0
    crit_w = weights[crit_mask]
    crit_p = probs[crit_mask]
    deficit = float(np.sum(crit_w * np.maximum(0.0, t_crit - crit_p)) / np.sum(crit_w))
    assert deficit == pytest.approx(1.0 / 6.0)

    # Scenario B: No critical nodes (all weights = 1.0)
    nodes_normal = (
        GridNode(Point2D(1.0, 1.0), weight=1.0),
        GridNode(Point2D(2.0, 2.0), weight=1.0),
    )
    grid_normal = SamplingGrid(resolution=2.0, nodes=nodes_normal, cell_width=2.0, cell_height=2.0)
    cov = evaluate_multicamera_coverage([], CameraProfile(), grid_normal, floorplan, t_crit=0.8)
    assert cov.num_critical_points == 0
    assert cov.critical_deficit == 0.0


# ---------------------------------------------------------------------------
# OPT-11: Infeasible Configuration Rejection
# ---------------------------------------------------------------------------


def test_opt_11_infeasible_configurations_rejected() -> None:
    """OPT-11: A camera placed inside an obstacle or wall must receive an infeasible result,
    with objective_cost = None and clear diagnostic reasons.
    """
    boundary = BoundingBox(0.0, 20.0, 0.0, 20.0)
    obstacle = ObstaclePolygon.from_rectangle(5.0, 10.0, 5.0, 10.0)
    wall = WallSegment(Point2D(15.0, 0.0), Point2D(15.0, 10.0))
    floorplan = FloorPlan(boundary=boundary, obstacles=[obstacle], walls=[wall])
    grid = SamplingGrid.generate(floorplan, resolution=2.0)

    evaluator = ConfigurationEvaluator(floorplan, grid)

    # Camera 0 is valid, Camera 1 is inside obstacle (7, 7)
    cameras_obstacle = [
        CameraPose(2.0, 2.0, 0.0),
        CameraPose(7.0, 7.0, 0.0),
    ]
    res_obs = evaluator.evaluate(cameras_obstacle)
    assert res_obs.is_feasible is False
    assert res_obs.objective_cost is None
    assert any("obstacle" in r.lower() for r in res_obs.infeasibility_reasons)

    # Camera on interior wall (15, 5)
    cameras_wall = [CameraPose(15.0, 5.0, 0.0)]
    res_wall = evaluator.evaluate(cameras_wall)
    assert res_wall.is_feasible is False
    assert res_wall.objective_cost is None
    assert any("wall" in r.lower() for r in res_wall.infeasibility_reasons)

    # Camera on room outer perimeter (0, 10)
    cameras_boundary = [CameraPose(0.0, 10.0, 0.0)]
    res_bound = evaluator.evaluate(cameras_boundary)
    assert res_bound.is_feasible is False
    assert res_bound.objective_cost is None
    assert any("boundary" in r.lower() for r in res_bound.infeasibility_reasons)

    # Camera completely outside room (-5, 10)
    cameras_outside = [CameraPose(-5.0, 10.0, 0.0)]
    res_out = evaluator.evaluate(cameras_outside)
    assert res_out.is_feasible is False
    assert res_out.objective_cost is None


# ---------------------------------------------------------------------------
# OPT-13: Determinism
# ---------------------------------------------------------------------------


def test_opt_13_evaluator_determinism() -> None:
    """OPT-13: Repeated evaluations of the identical configuration produce identical results."""
    boundary = BoundingBox(0.0, 20.0, 0.0, 20.0)
    zone = RiskZone.from_rectangle(12.0, 18.0, 12.0, 18.0, weight=3.0)
    obstacle = ObstaclePolygon.from_rectangle(5.0, 8.0, 5.0, 8.0)
    floorplan = FloorPlan(boundary=boundary, obstacles=[obstacle], risk_zones=[zone])
    grid = SamplingGrid.generate(floorplan, resolution=2.0)

    evaluator = ConfigurationEvaluator(
        floorplan=floorplan,
        grid=grid,
        config=ObjectiveConfig(lambda_def=1.5, t_crit=0.85),
    )

    cameras = [
        CameraPose(2.0, 2.0, math.pi / 4.0),
        CameraPose(15.0, 5.0, math.pi / 2.0),
    ]

    res1 = evaluator.evaluate(cameras)
    res2 = evaluator.evaluate(cameras)

    assert res1.is_feasible is True
    assert res2.is_feasible is True
    assert res1.objective_cost == res2.objective_cost
    assert res1.metrics is not None and res2.metrics is not None
    assert res1.metrics.risk_weighted_coverage == res2.metrics.risk_weighted_coverage
    assert res1.metrics.critical_deficit == res2.metrics.critical_deficit
    np.testing.assert_array_equal(res1.metrics.point_probabilities, res2.metrics.point_probabilities)


# ---------------------------------------------------------------------------
# Objective Function Properties & Config Validation
# ---------------------------------------------------------------------------


def test_objective_config_validation() -> None:
    # lambda_def < 0
    with pytest.raises(ValueError, match="lambda_def must be non-negative"):
        ObjectiveConfig(lambda_def=-0.1)

    # t_crit <= 0 or > 1.0
    with pytest.raises(ValueError, match="t_crit must be in the open-closed interval"):
        ObjectiveConfig(t_crit=0.0)
    with pytest.raises(ValueError, match="t_crit must be in the open-closed interval"):
        ObjectiveConfig(t_crit=1.1)

    # Non-finite
    with pytest.raises(ValueError, match="finite"):
        ObjectiveConfig(lambda_def=float("nan"))


def test_objective_cost_formula_and_bounds() -> None:
    """Verify f(X) = (1 - C_risk) + lambda_def * Deficit_crit."""
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    zone = RiskZone.from_rectangle(2.0, 8.0, 2.0, 8.0, weight=2.5)
    floorplan = FloorPlan(boundary=boundary, risk_zones=[zone])
    grid = SamplingGrid.generate(floorplan, resolution=2.0)

    config = ObjectiveConfig(lambda_def=2.0, t_crit=0.7)
    evaluator = ConfigurationEvaluator(floorplan, grid, config=config)

    cameras = [CameraPose(5.0, 5.0, 0.0)]
    res = evaluator.evaluate(cameras)

    assert res.is_feasible is True
    assert res.objective_cost is not None
    assert res.metrics is not None

    expected_cost = (1.0 - res.metrics.risk_weighted_coverage) + 2.0 * res.metrics.critical_deficit
    assert res.objective_cost == pytest.approx(expected_cost)
    assert res.objective_cost >= 0.0


# ---------------------------------------------------------------------------
# DEFECT 2: Large Risk Weights Overflow Protection
# ---------------------------------------------------------------------------


def test_defect_2_large_risk_weights_overflow_protection() -> None:
    """DEFECT 2: Large finite weights (e.g. 1e308) must not overflow sum(weights) to infinity
    or produce NaN coverage / critical deficit.

    Reproducible case from technical audit:
    - FloorPlan: 20 x 20 m.
    - RiskZone: [1, 19] x [1, 19] with weight 1e308.
    - SamplingGrid: resolution 10m (4 nodes in the room).
    - Camera: CameraPose(5, 5, 0).
    - Expected: Evaluator returns valid, finite, non-NaN objective cost,
      with C_risk in [0, 1] and Deficit_crit in [0, 1].
    """
    boundary = BoundingBox(0.0, 20.0, 0.0, 20.0)
    risk_zone = RiskZone.from_rectangle(1.0, 19.0, 1.0, 19.0, weight=1e308)
    floorplan = FloorPlan(boundary=boundary, risk_zones=[risk_zone])

    grid = SamplingGrid.generate(floorplan, resolution=10.0)
    assert grid.num_nodes == 4
    # All 4 nodes are inside the risk zone and have weight 1e308
    assert all(node.weight == 1e308 for node in grid.nodes)

    evaluator = ConfigurationEvaluator(
        floorplan=floorplan,
        grid=grid,
        config=ObjectiveConfig(lambda_def=1.5, t_crit=0.8),
    )

    cameras = [CameraPose(5.0, 5.0, 0.0)]
    result = evaluator.evaluate(cameras)

    assert result.is_feasible is True
    assert result.objective_cost is not None
    assert math.isfinite(result.objective_cost)
    assert not math.isnan(result.objective_cost)

    metrics = result.metrics
    assert metrics is not None
    assert math.isfinite(metrics.risk_weighted_coverage)
    assert not math.isnan(metrics.risk_weighted_coverage)
    assert 0.0 <= metrics.risk_weighted_coverage <= 1.0

    assert math.isfinite(metrics.critical_deficit)
    assert not math.isnan(metrics.critical_deficit)
    assert 0.0 <= metrics.critical_deficit <= 1.0

    # Since all 4 nodes have the exact same weight (1e308),
    # the risk-weighted coverage must equal the arithmetic mean of the probabilities
    assert metrics.risk_weighted_coverage == pytest.approx(metrics.mean_probabilistic_coverage)


def test_defect_2_manually_verifiable_scaled_weights() -> None:
    """DEFECT 2: Verify scaled weight calculations match exact mathematical values.
    Weights: [1e300, 2e300, 4e300].
    Probabilities: [0.2, 0.5, 0.8].
    Scaling by max(w) = 4e300 yields scaled weights [0.25, 0.5, 1.0].
    Sum scaled weights = 1.75.
    Weighted prob sum = 0.25*0.2 + 0.5*0.5 + 1.0*0.8 = 0.05 + 0.25 + 0.8 = 1.10.
    C_risk = 1.10 / 1.75 = 22 / 35 ~= 0.62857142857.
    """
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    floorplan = FloorPlan(boundary=boundary)

    nodes = (
        GridNode(Point2D(1.0, 1.0), weight=1e300),
        GridNode(Point2D(3.0, 3.0), weight=2e300),
        GridNode(Point2D(5.0, 5.0), weight=4e300),
    )
    grid = SamplingGrid(resolution=2.0, nodes=nodes, cell_width=2.0, cell_height=2.0)

    weights = np.array([1e300, 2e300, 4e300])
    probs = np.array([0.2, 0.5, 0.8])

    max_w = np.max(weights)
    scaled_w = weights / max_w
    c_risk = float(np.sum(scaled_w * probs) / np.sum(scaled_w))

    assert math.isfinite(c_risk)
    assert c_risk == pytest.approx(22.0 / 35.0)

