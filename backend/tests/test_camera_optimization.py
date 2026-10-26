"""Tests for CameraOptimizationProblem and its integration with SequentialABC.

Covers requirements ABC-13, ABC-14, ABC-15, and camera-domain edge cases.
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from camera_optimizer.camera.pose import CameraPose, wrap_pi
from camera_optimizer.camera.profile import CameraProfile
from camera_optimizer.domain.floorplan import FloorPlan
from camera_optimizer.domain.grid import SamplingGrid
from camera_optimizer.domain.obstacle import ObstaclePolygon
from camera_optimizer.domain.risk_zone import RiskZone
from camera_optimizer.domain.wall import WallSegment
from camera_optimizer.geometry.bounding_box import BoundingBox
from camera_optimizer.geometry.point import Point2D
from camera_optimizer.geometry.polygon import Polygon2D
from camera_optimizer.objective.config import ObjectiveConfig
from camera_optimizer.objective.evaluator import ConfigurationEvaluator
from camera_optimizer.optimizer.camera_problem import CameraOptimizationProblem
from camera_optimizer.optimizer.config import ABCConfig
from camera_optimizer.optimizer.sequential_abc import SequentialABC


@pytest.fixture
def simple_room_floorplan() -> FloorPlan:
    """10x10 m room with one square obstacle in the center."""
    # Obstacle from (4, 4) to (6, 6)
    obs = ObstaclePolygon.from_rectangle(4.0, 6.0, 4.0, 6.0)
    # Risk zone in corner [1, 3] x [1, 3]
    risk = RiskZone(
        [Point2D(1, 1), Point2D(3, 1), Point2D(3, 3), Point2D(1, 3)],
        weight=3.0,
    )
    return FloorPlan(
        boundary=BoundingBox(0, 10, 0, 10),
        obstacles=[obs],
        risk_zones=[risk],
    )


@pytest.fixture
def coarse_grid(simple_room_floorplan: FloorPlan) -> SamplingGrid:
    """Coarse grid for fast testing."""
    return SamplingGrid.generate(
        floorplan=simple_room_floorplan,
        resolution=1.0,
    )


# =========================================================================
# ABC-13: Fixed Number of Cameras K
# =========================================================================

def test_abc_13_fixed_number_of_cameras_dimension(
    simple_room_floorplan: FloorPlan, coarse_grid: SamplingGrid
) -> None:
    """ABC-13: For K=3, the candidate vector contains exactly 9 components and represents 3 cameras."""
    problem = CameraOptimizationProblem(
        floorplan=simple_room_floorplan,
        grid=coarse_grid,
        num_cameras=3,
    )

    assert problem.num_cameras == 3
    assert problem.dimension == 9
    assert len(problem.bounds) == 9

    # Vector conversion
    poses = (
        CameraPose(1.0, 2.0, 0.0),
        CameraPose(3.0, 4.0, math.pi / 2),
        CameraPose(5.0, 8.0, -math.pi / 4),
    )
    vec = problem.poses_to_vector(poses)
    assert len(vec) == 9
    assert vec[0] == 1.0 and vec[1] == 2.0 and vec[2] == 0.0
    assert vec[3] == 3.0 and vec[4] == 4.0 and pytest.approx(vec[5]) == math.pi / 2
    assert vec[6] == 5.0 and vec[7] == 8.0 and pytest.approx(vec[8]) == -math.pi / 4

    roundtrip_poses = problem.vector_to_poses(vec)
    assert len(roundtrip_poses) == 3
    for orig, rt in zip(poses, roundtrip_poses, strict=True):
        assert pytest.approx(orig.x) == rt.x
        assert pytest.approx(orig.y) == rt.y
        assert pytest.approx(orig.theta) == rt.theta

    # Reject vector of incorrect length (e.g., 6 or 12 instead of 9)
    with pytest.raises(ValueError, match="Candidate vector must be 1D of length 9"):
        problem.vector_to_poses(np.zeros(6))

    with pytest.raises(ValueError, match="Candidate vector must be 1D of length 9"):
        problem.vector_to_poses(np.zeros(12))

    # Reject non-finite vector
    bad_vec = np.copy(vec)
    bad_vec[0] = float("nan")
    with pytest.raises(ValueError, match="contains NaN or infinite"):
        problem.vector_to_poses(bad_vec)


def test_camera_problem_invalid_initialization(
    simple_room_floorplan: FloorPlan, coarse_grid: SamplingGrid
) -> None:
    """Reject invalid inputs during CameraOptimizationProblem initialization."""
    with pytest.raises(TypeError):
        CameraOptimizationProblem(floorplan="not_a_floorplan", grid=coarse_grid, num_cameras=2)  # type: ignore

    with pytest.raises(TypeError):
        CameraOptimizationProblem(floorplan=simple_room_floorplan, grid="not_a_grid", num_cameras=2)  # type: ignore

    with pytest.raises(TypeError, match="num_cameras must be an integer"):
        CameraOptimizationProblem(floorplan=simple_room_floorplan, grid=coarse_grid, num_cameras=True)  # type: ignore

    with pytest.raises(ValueError, match="strictly positive integer"):
        CameraOptimizationProblem(floorplan=simple_room_floorplan, grid=coarse_grid, num_cameras=0)

    with pytest.raises(ValueError, match="max_sampling_attempts must be positive"):
        CameraOptimizationProblem(
            floorplan=simple_room_floorplan, grid=coarse_grid, num_cameras=2, max_sampling_attempts=0
        )


# =========================================================================
# ABC-14: Obstacle Rejection
# =========================================================================

def test_abc_14_obstacle_rejection(
    simple_room_floorplan: FloorPlan, coarse_grid: SamplingGrid
) -> None:
    """ABC-14: No candidate placing a camera inside an obstacle or wall is accepted."""
    problem = CameraOptimizationProblem(
        floorplan=simple_room_floorplan,
        grid=coarse_grid,
        num_cameras=2,
    )

    # Valid candidate
    valid_x = np.array([2.0, 2.0, 0.0, 8.0, 8.0, 0.0], dtype=np.float64)
    assert problem.is_valid(valid_x)

    # Infeasible candidate 1: camera 1 inside obstacle [4, 6] x [4, 6]
    inside_obs_x = np.array([5.0, 5.0, 0.0, 8.0, 8.0, 0.0], dtype=np.float64)
    assert not problem.is_valid(inside_obs_x)

    # Infeasible candidate 2: camera on outer boundary wall
    on_wall_x = np.array([0.0, 5.0, 0.0, 8.0, 8.0, 0.0], dtype=np.float64)
    assert not problem.is_valid(on_wall_x)

    # Infeasible candidate 3: camera outside room
    outside_x = np.array([-1.0, 5.0, 0.0, 8.0, 8.0, 0.0], dtype=np.float64)
    assert not problem.is_valid(outside_x)

    # Trying to evaluate an infeasible candidate must raise ValueError
    with pytest.raises(ValueError, match="Cannot evaluate infeasible configuration"):
        problem.evaluate(inside_obs_x)


# =========================================================================
# ABC-15: Integration with ConfigurationEvaluator
# =========================================================================

def test_abc_15_integration_with_configuration_evaluator(
    simple_room_floorplan: FloorPlan, coarse_grid: SamplingGrid
) -> None:
    """ABC-15: Adapter uses the exact Phase 2 ConfigurationEvaluator without alternative math."""
    profile = CameraProfile(Rmax=8.0, fov=math.pi / 2)
    obj_cfg = ObjectiveConfig(lambda_def=1.5, t_crit=0.8)

    direct_evaluator = ConfigurationEvaluator(
        floorplan=simple_room_floorplan,
        grid=coarse_grid,
        profile=profile,
        config=obj_cfg,
    )

    problem = CameraOptimizationProblem(
        floorplan=simple_room_floorplan,
        grid=coarse_grid,
        num_cameras=2,
        profile=profile,
        config=obj_cfg,
    )

    poses = (CameraPose(2.0, 2.0, 0.0), CameraPose(8.0, 8.0, math.pi))
    vec = problem.poses_to_vector(poses)

    # Cost from adapter evaluate
    adapter_cost = problem.evaluate(vec)

    # Direct evaluation from ConfigurationEvaluator
    direct_result = direct_evaluator.evaluate(poses)
    assert direct_result.is_feasible
    assert direct_result.objective_cost is not None

    # Must be bitwise identical
    assert adapter_cost == direct_result.objective_cost

    # Detailed report from problem must match direct result metrics
    detailed_res = problem.get_detailed_evaluation(vec)
    assert detailed_res.objective_cost == direct_result.objective_cost
    assert detailed_res.metrics is not None
    assert direct_result.metrics is not None
    assert (
        detailed_res.metrics.risk_weighted_coverage
        == direct_result.metrics.risk_weighted_coverage
    )


def test_camera_problem_sampling_failure_under_impossible_geometry() -> None:
    """If facility has no free interior space, sample_valid raises clear RuntimeError."""
    room_box = BoundingBox(0, 10, 0, 10)
    full_obs = ObstaclePolygon([Point2D(0, 0), Point2D(10, 0), Point2D(10, 10), Point2D(0, 10)])
    fp = FloorPlan(boundary=room_box, obstacles=[full_obs])
    grid = SamplingGrid(resolution=1.0, nodes=())

    problem = CameraOptimizationProblem(
        floorplan=fp,
        grid=grid,
        num_cameras=1,
        max_sampling_attempts=10,
    )

    rng = np.random.default_rng(42)
    with pytest.raises(RuntimeError, match="Failed to sample a feasible position"):
        problem.sample_valid(rng)


def test_abc_camera_optimization_end_to_end_run(
    simple_room_floorplan: FloorPlan, coarse_grid: SamplingGrid
) -> None:
    """Run an end-to-end optimization with SequentialABC on CameraOptimizationProblem."""
    problem = CameraOptimizationProblem(
        floorplan=simple_room_floorplan,
        grid=coarse_grid,
        num_cameras=2,
    )

    cfg = ABCConfig(
        num_food_sources=6,
        max_cycles=5,
        limit=10,
        seed=12345,
        record_trace=True,
    )

    abc = SequentialABC(problem, cfg)
    output = abc.optimize()

    assert output.evaluations_count > 0
    assert output.best_cost <= output.history[0].best_cost
    assert len(output.best_solution) == 6
    assert problem.is_valid(output.best_solution)

    # Detailed evaluation of final solution
    detailed = problem.get_detailed_evaluation(output.best_solution)
    assert detailed.is_feasible
    assert detailed.metrics is not None
    assert detailed.metrics.geometric_coverage_ratio > 0.0
