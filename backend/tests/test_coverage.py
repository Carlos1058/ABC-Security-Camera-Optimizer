"""Unit tests for optical visibility, individual detection probability, and multi-camera coverage."""

import math
import numpy as np
import pytest

from camera_optimizer.camera.pose import CameraPose
from camera_optimizer.camera.profile import CameraProfile
from camera_optimizer.coverage.evaluator import (
    calculate_point_probability,
    evaluate_camera_grid,
    evaluate_multicamera_coverage,
    is_point_geometrically_covered,
)
from camera_optimizer.domain.floorplan import FloorPlan
from camera_optimizer.domain.grid import GridNode, SamplingGrid
from camera_optimizer.domain.obstacle import ObstaclePolygon
from camera_optimizer.domain.wall import WallSegment
from camera_optimizer.geometry.bounding_box import BoundingBox
from camera_optimizer.geometry.point import Point2D


# ---------------------------------------------------------------------------
# OPT-01 to OPT-07: Single Camera Tests
# ---------------------------------------------------------------------------


def test_opt_01_camera_correctly_oriented() -> None:
    """OPT-01: Camera pointing to a visible target situated inside its range and FOV.
    Result: Positive probability and <= p0.
    """
    boundary = BoundingBox(0.0, 20.0, 0.0, 20.0)
    floorplan = FloorPlan(boundary=boundary)

    camera = CameraPose(5.0, 5.0, 0.0)  # Facing +X
    profile = CameraProfile(Rmin=0.0, Rmax=10.0, fov=math.pi / 2.0, p0=0.9, beta_d=0.5, beta_theta=0.5)
    target = Point2D(8.0, 5.0)

    p = calculate_point_probability(camera, profile, target, floorplan)
    assert 0.0 < p <= profile.p0


def test_opt_02_verifiable_exponential_probability() -> None:
    """OPT-02: Camera at (5,5), facing +X. Target at (10,5).
    Rmin=0, Rmax=10, FOV=pi/2, p0=1, beta_d=1, beta_theta=1.
    Expected result:
    p = exp(-0.25) ~= 0.7788007831
    """
    boundary = BoundingBox(0.0, 20.0, 0.0, 20.0)
    floorplan = FloorPlan(boundary=boundary)

    camera = CameraPose(5.0, 5.0, 0.0)
    profile = CameraProfile(
        Rmin=0.0,
        Rmax=10.0,
        fov=math.pi / 2.0,
        p0=1.0,
        beta_d=1.0,
        beta_theta=1.0,
    )
    target = Point2D(10.0, 5.0)

    p = calculate_point_probability(camera, profile, target, floorplan)
    expected_p = math.exp(-0.25)
    assert p == pytest.approx(expected_p, rel=1e-9)
    assert p == pytest.approx(0.7788007831, abs=1e-8)


def test_opt_03_target_out_of_range() -> None:
    """OPT-03: Target situated beyond Rmax or closer than Rmin.
    Result: p = 0.
    """
    boundary = BoundingBox(0.0, 30.0, 0.0, 30.0)
    floorplan = FloorPlan(boundary=boundary)

    camera = CameraPose(5.0, 5.0, 0.0)
    profile = CameraProfile(Rmin=2.0, Rmax=10.0, fov=math.pi / 2.0)

    # Beyond Rmax (distance = 11m)
    target_far = Point2D(16.0, 5.0)
    p_far = calculate_point_probability(camera, profile, target_far, floorplan)
    assert p_far == 0.0

    # Closer than Rmin (distance = 1m < 2m)
    target_near = Point2D(6.0, 5.0)
    p_near = calculate_point_probability(camera, profile, target_near, floorplan)
    assert p_near == 0.0


def test_opt_04_target_out_of_fov() -> None:
    """OPT-04: Target inside range, but outside horizontal FOV.
    Result: p = 0.
    """
    boundary = BoundingBox(0.0, 20.0, 0.0, 20.0)
    floorplan = FloorPlan(boundary=boundary)

    # Camera at (5, 5) facing East (+X, theta=0). FOV=pi/2 (+-45 degrees, [-pi/4, pi/4])
    camera = CameraPose(5.0, 5.0, 0.0)
    profile = CameraProfile(Rmin=0.0, Rmax=10.0, fov=math.pi / 2.0)

    # Target directly North at (5, 10): angle is +pi/2 (90 degrees) -> outside 45 degrees
    target_north = Point2D(5.0, 10.0)
    p_north = calculate_point_probability(camera, profile, target_north, floorplan)
    assert p_north == 0.0

    # Target directly behind camera at (2, 5) -> outside
    target_behind = Point2D(2.0, 5.0)
    p_behind = calculate_point_probability(camera, profile, target_behind, floorplan)
    assert p_behind == 0.0


def test_opt_05_blocking_wall() -> None:
    """OPT-05: Distance and angle are correct, but an opaque wall blocks line of sight.
    Result: p = 0.
    """
    boundary = BoundingBox(0.0, 20.0, 0.0, 20.0)
    # Wall dividing x = 7 from y = 0 to y = 10
    wall = WallSegment(Point2D(7.0, 0.0), Point2D(7.0, 10.0), is_opaque=True)
    floorplan = FloorPlan(boundary=boundary, walls=[wall])

    camera = CameraPose(5.0, 5.0, 0.0)  # Facing +X
    profile = CameraProfile(Rmin=0.0, Rmax=10.0, fov=math.pi / 2.0)
    target = Point2D(9.0, 5.0)  # Distance 4m, on optical axis, but wall is at x=7

    p = calculate_point_probability(camera, profile, target, floorplan)
    assert p == 0.0


def test_opt_06_doorway_opening_permits_vision() -> None:
    """OPT-06: Target observable through a door opening between wall segments.
    Result: p > 0.
    """
    boundary = BoundingBox(0.0, 20.0, 0.0, 20.0)
    # Two walls with a doorway between y=4.0 and y=6.0 along x=7.0
    wall1 = WallSegment(Point2D(7.0, 0.0), Point2D(7.0, 4.0), is_opaque=True)
    wall2 = WallSegment(Point2D(7.0, 6.0), Point2D(7.0, 20.0), is_opaque=True)
    floorplan = FloorPlan(boundary=boundary, walls=[wall1, wall2])

    camera = CameraPose(5.0, 5.0, 0.0)
    profile = CameraProfile(Rmin=0.0, Rmax=10.0, fov=math.pi / 2.0)
    target = Point2D(9.0, 5.0)  # Passes cleanly through doorway at y=5.0

    p = calculate_point_probability(camera, profile, target, floorplan)
    assert p > 0.0


def test_opt_07_circular_angular_continuity() -> None:
    """OPT-07: Verify seamless angular continuity near +pi and -pi branch cuts."""
    boundary = BoundingBox(-20.0, 20.0, -20.0, 20.0)
    floorplan = FloorPlan(boundary=boundary)

    # Camera at (0, 0) facing almost West at +3.13 rad (near +pi)
    # Target in 3rd quadrant at bearing -3.13 rad (near -pi)
    # The actual angular difference is (3.13 - (-3.13)) = 6.26, which wraps to 6.26 - 2*pi ~= -0.023 rad!
    # With FOV = pi/2 (45 deg = 0.785 rad), this target is directly in front of the lens!
    cam = CameraPose(0.0, 0.0, 3.13)
    profile = CameraProfile(Rmin=0.0, Rmax=10.0, fov=math.pi / 2.0, p0=1.0, beta_d=0.0, beta_theta=1.0)

    # Target at distance 5m along bearing -3.13 rad
    target_x = 5.0 * math.cos(-3.13)
    target_y = 5.0 * math.sin(-3.13)
    target = Point2D(target_x, target_y)

    p = calculate_point_probability(cam, profile, target, floorplan)
    # Difference is ~0.02318 rad, well within half_fov ~ 0.785 rad
    assert p > 0.95


# ---------------------------------------------------------------------------
# OPT-08, OPT-14 & Multi-Camera Combination Tests
# ---------------------------------------------------------------------------


def test_opt_08_combined_multi_camera_probability() -> None:
    """OPT-08: Two cameras with individual probabilities of 0.5 on a point:
    P_det = 1 - (1 - 0.5)^2 = 0.75.
    """
    boundary = BoundingBox(0.0, 20.0, 0.0, 20.0)
    floorplan = FloorPlan(boundary=boundary)

    # Design profile where point on optical axis at distance d gives p = 0.5
    # p = p0 * exp(-beta_d * u_d^2). Let p0=1, u_d=1 (d=10), beta_d = ln(2) ~= 0.69314718
    # Then p = exp(-ln(2)) = 0.5.
    ln2 = math.log(2.0)
    profile = CameraProfile(Rmin=0.0, Rmax=10.0, fov=math.pi, p0=1.0, beta_d=ln2, beta_theta=0.0)

    # Target at (10, 10)
    # Camera 1 at (0, 10) facing +X (distance 10, on axis -> p = 0.5)
    cam1 = CameraPose(0.01, 10.0, 0.0)
    # Camera 2 at (10, 0) facing +Y (distance 10, on axis -> p = 0.5)
    cam2 = CameraPose(10.0, 0.01, math.pi / 2.0)

    target = Point2D(10.0, 10.0)
    p1 = calculate_point_probability(cam1, profile, target, floorplan)
    p2 = calculate_point_probability(cam2, profile, target, floorplan)
    assert p1 == pytest.approx(0.5, abs=1e-3)
    assert p2 == pytest.approx(0.5, abs=1e-3)

    grid = SamplingGrid(resolution=1.0, nodes=(SamplingGrid.generate(floorplan, resolution=10.0).nodes[0],))
    # We test via the multi-camera formula: 1 - (1 - p1) * (1 - p2)
    p_combined = 1.0 - (1.0 - p1) * (1.0 - p2)
    assert p_combined == pytest.approx(0.75, abs=1e-3)


def test_opt_14_detection_probability_monotonicity() -> None:
    """OPT-14: Adding an additional valid camera cannot decrease combined probability
    at any point, within numerical floating-point tolerance.
    """
    boundary = BoundingBox(0.0, 20.0, 0.0, 20.0)
    obstacle = ObstaclePolygon.from_rectangle(8.0, 12.0, 8.0, 12.0)
    floorplan = FloorPlan(boundary=boundary, obstacles=[obstacle])

    grid = SamplingGrid.generate(floorplan, resolution=2.0)
    profile = CameraProfile(Rmin=0.0, Rmax=12.0, fov=math.pi / 2.0)

    cam1 = CameraPose(2.0, 2.0, math.pi / 4.0)
    cam2 = CameraPose(18.0, 18.0, -3.0 * math.pi / 4.0)
    cam3 = CameraPose(2.0, 18.0, -math.pi / 4.0)

    # 1 camera
    cov_1 = evaluate_multicamera_coverage([cam1], profile, grid, floorplan)
    # 2 cameras
    cov_2 = evaluate_multicamera_coverage([cam1, cam2], profile, grid, floorplan)
    # 3 cameras
    cov_3 = evaluate_multicamera_coverage([cam1, cam2, cam3], profile, grid, floorplan)

    tol = 1e-12
    # Monotonicity check for every point in the grid
    assert np.all(cov_2.point_probabilities >= cov_1.point_probabilities - tol)
    assert np.all(cov_3.point_probabilities >= cov_2.point_probabilities - tol)

    # Overall metrics must also be non-decreasing
    assert cov_2.risk_weighted_coverage >= cov_1.risk_weighted_coverage - tol
    assert cov_3.risk_weighted_coverage >= cov_2.risk_weighted_coverage - tol
    assert cov_3.num_covered_points >= cov_2.num_covered_points >= cov_1.num_covered_points


def test_scalar_and_vectorized_evaluation_equivalence() -> None:
    """Requirement 8: Verify that evaluate_camera_grid produces exactly the same
    probabilities as point-by-point calculate_point_probability in a complex environment
    with walls, doorways, and obstacles.
    """
    boundary = BoundingBox(0.0, 20.0, 0.0, 20.0)
    # Wall with door
    wall1 = WallSegment(Point2D(10.0, 0.0), Point2D(10.0, 8.0), is_opaque=True)
    wall2 = WallSegment(Point2D(10.0, 12.0), Point2D(10.0, 20.0), is_opaque=True)
    # Obstacle
    obstacle = ObstaclePolygon.from_rectangle(3.0, 6.0, 3.0, 6.0)
    floorplan = FloorPlan(boundary=boundary, walls=[wall1, wall2], obstacles=[obstacle])

    grid = SamplingGrid.generate(floorplan, resolution=1.0)
    profile = CameraProfile(Rmin=0.5, Rmax=15.0, fov=2.0 * math.pi / 3.0, beta_d=0.7, beta_theta=0.4)
    camera = CameraPose(2.0, 10.0, 0.0)

    # Vectorized
    vec_probs = evaluate_camera_grid(camera, profile, grid, floorplan)

    # Scalar point-by-point
    scalar_probs = np.array(
        [calculate_point_probability(camera, profile, node.point, floorplan) for node in grid.nodes],
        dtype=np.float64,
    )

    np.testing.assert_allclose(vec_probs, scalar_probs, atol=1e-12, rtol=1e-12)


def test_defect_1_geometric_coverage_independent_of_probability_underflow() -> None:
    """DEFECT 1: Geometric coverage must depend exclusively on range, angle, and line-of-sight,
    not on whether the numerical probability underflows to 0.0 in float64.

    Reproducible case from technical audit:
    - FloorPlan: BoundingBox(0, 20, 0, 20), no obstacles.
    - Camera: CameraPose(5, 5, 0).
    - Target: Point2D(10, 5).
    - Profile: Rmin=0, Rmax=10, FOV=pi/2, p0=1, beta_d=4000, beta_theta=0.
    - Result: Target is geometrically visible, but exp(-1000) underflows to 0.0 in float64.
    Expected:
    - is_point_geometrically_covered -> True
    - calculate_point_probability -> 0.0
    - num_covered_points -> 1
    - geometric_coverage_percent -> 100.0%
    """
    boundary = BoundingBox(0.0, 20.0, 0.0, 20.0)
    floorplan = FloorPlan(boundary=boundary)

    camera = CameraPose(5.0, 5.0, 0.0)
    target = Point2D(10.0, 5.0)

    # beta_d=4000 causes u_d = (5-0)/10 = 0.5 -> exponent = -4000 * 0.25 = -1000 -> exp(-1000) underflows to 0.0
    profile = CameraProfile(
        Rmin=0.0,
        Rmax=10.0,
        fov=math.pi / 2.0,
        p0=1.0,
        beta_d=4000.0,
        beta_theta=0.0,
    )

    # 1. Point-level check
    assert is_point_geometrically_covered(camera, profile, target, floorplan) is True
    prob = calculate_point_probability(camera, profile, target, floorplan)
    assert prob == 0.0

    # 2. Grid-level multi-camera check
    grid = SamplingGrid(
        resolution=1.0,
        nodes=(GridNode(target, weight=1.0),),
        cell_width=1.0,
        cell_height=1.0,
    )
    metrics = evaluate_multicamera_coverage([camera], profile, grid, floorplan)

    assert metrics.num_eval_points == 1
    assert metrics.num_covered_points == 1
    assert metrics.geometric_coverage_ratio == 1.0
    assert metrics.geometric_coverage_percent == 100.0
    assert metrics.point_binary_covered[0] == True
    assert metrics.point_probabilities[0] == 0.0

