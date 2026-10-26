"""Unit tests for SamplingGrid generation, risk weight assignment, and determinism."""

import pytest

from camera_optimizer.domain.floorplan import FloorPlan
from camera_optimizer.domain.grid import GridNode, SamplingGrid
from camera_optimizer.domain.obstacle import ObstaclePolygon
from camera_optimizer.domain.risk_zone import RiskZone
from camera_optimizer.domain.wall import WallSegment
from camera_optimizer.geometry.bounding_box import BoundingBox
from camera_optimizer.geometry.point import Point2D


# ---------------------------------------------------------------------------
# Mandatory Sampling Grid Test Cases (GEO-10 to GEO-12)
# ---------------------------------------------------------------------------


def test_geo_10_sampling_grid_generation() -> None:
    """GEO-10: 10 x 10 m room, 2 m resolution, no obstacles.
    Result: Exactly 25 points, with coordinates corresponding to cell centers.
    """
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    floorplan = FloorPlan(boundary=boundary)

    grid = SamplingGrid.generate(floorplan, resolution=2.0)

    assert grid.num_nodes == 25

    expected_coords = [
        (cx, cy)
        for cy in [1.0, 3.0, 5.0, 7.0, 9.0]
        for cx in [1.0, 3.0, 5.0, 7.0, 9.0]
    ]

    actual_coords = [(node.point.x, node.point.y) for node in grid.nodes]
    assert actual_coords == expected_coords

    # Without risk zones, all nodes have default weight 1.0
    assert all(node.weight == 1.0 for node in grid.nodes)


def test_geo_11_overlapping_risk_zones() -> None:
    """GEO-11: Two risk zones with weights 3.0 and 5.0 containing the same point.
    Result: Maximum weight of 5.0 is assigned.
    """
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)

    # Zone A: [2, 6] x [2, 6] with weight 3.0
    zone_a = RiskZone.from_rectangle(2.0, 6.0, 2.0, 6.0, weight=3.0, name="Zone A")
    # Zone B: [4, 8] x [4, 8] with weight 5.0
    zone_b = RiskZone.from_rectangle(4.0, 8.0, 4.0, 8.0, weight=5.0, name="Zone B")

    floorplan = FloorPlan(boundary=boundary, risk_zones=[zone_a, zone_b])

    # Grid with 2.0m resolution: cell centers at 1, 3, 5, 7, 9
    grid = SamplingGrid.generate(floorplan, resolution=2.0)

    # Find the node at (5.0, 5.0), which lies inside both Zone A and Zone B
    node_overlap = next(n for n in grid.nodes if n.point == Point2D(5.0, 5.0))
    assert node_overlap.weight == pytest.approx(5.0)

    # Node at (3.0, 3.0) lies only in Zone A (weight 3.0)
    node_a_only = next(n for n in grid.nodes if n.point == Point2D(3.0, 3.0))
    assert node_a_only.weight == pytest.approx(3.0)

    # Node at (7.0, 7.0) lies only in Zone B (weight 5.0)
    node_b_only = next(n for n in grid.nodes if n.point == Point2D(7.0, 7.0))
    assert node_b_only.weight == pytest.approx(5.0)

    # Node at (1.0, 1.0) lies in neither zone (default weight 1.0)
    node_default = next(n for n in grid.nodes if n.point == Point2D(1.0, 1.0))
    assert node_default.weight == pytest.approx(1.0)


def test_geo_12_grid_determinism() -> None:
    """GEO-12: Two grid generations with identical parameters produce exactly
    the same points and weights, in the identical sequence.
    """
    boundary = BoundingBox(0.0, 20.0, 0.0, 20.0)
    obstacle = ObstaclePolygon.from_rectangle(5.0, 15.0, 5.0, 15.0)
    zone = RiskZone.from_rectangle(12.0, 18.0, 2.0, 8.0, weight=4.0)

    floorplan = FloorPlan(boundary=boundary, obstacles=[obstacle], risk_zones=[zone])

    grid1 = SamplingGrid.generate(floorplan, resolution=1.0)
    grid2 = SamplingGrid.generate(floorplan, resolution=1.0)

    assert grid1.num_nodes == grid2.num_nodes
    assert grid1.num_nodes > 0

    for n1, n2 in zip(grid1.nodes, grid2.nodes, strict=True):
        assert n1.point == n2.point
        assert n1.weight == n2.weight


# ---------------------------------------------------------------------------
# Additional Grid Filtering & Numerical Tests
# ---------------------------------------------------------------------------


def test_grid_excludes_obstacle_interior() -> None:
    """Nodes inside solid obstacles must be excluded from the evaluation grid."""
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    # Obstacle covering center [4, 6] x [4, 6] -> contains point (5, 5)
    obstacle = ObstaclePolygon.from_rectangle(4.0, 6.0, 4.0, 6.0)
    floorplan = FloorPlan(boundary=boundary, obstacles=[obstacle])

    grid = SamplingGrid.generate(floorplan, resolution=2.0)

    # In 10x10 at 2m step, normally 25 points. (5, 5) is removed -> 24 points.
    assert grid.num_nodes == 24
    assert Point2D(5.0, 5.0) not in grid.points


def test_grid_rejects_invalid_resolution() -> None:
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    floorplan = FloorPlan(boundary=boundary)

    with pytest.raises(ValueError, match="must be finite and > 0"):
        SamplingGrid.generate(floorplan, resolution=0.0)
    with pytest.raises(ValueError, match="must be finite and > 0"):
        SamplingGrid.generate(floorplan, resolution=-2.0)
    with pytest.raises(ValueError, match="larger than floor plan dimensions"):
        SamplingGrid.generate(floorplan, resolution=25.0)


def test_grid_numpy_export() -> None:
    """Ensure grid exports properly to float64 NumPy coordinate and weight arrays."""
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    floorplan = FloorPlan(boundary=boundary)
    grid = SamplingGrid.generate(floorplan, resolution=2.0)

    coords, weights = grid.as_numpy_arrays()
    assert coords.shape == (25, 2)
    assert weights.shape == (25,)
    assert coords.dtype.name == "float64"
    assert weights.dtype.name == "float64"
    # First cell center (1.0, 1.0)
    assert coords[0, 0] == 1.0
    assert coords[0, 1] == 1.0
    assert weights[0] == 1.0


def test_grid_excludes_points_on_interior_walls() -> None:
    """Nodes directly on an interior wall segment must be excluded."""
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    # A wall along x = 5.0 from y=0 to y=10
    # In a 2.0m resolution grid, cell centers have x = 1, 3, 5, 7, 9
    # The entire column with x = 5.0 (5 points: (5,1), (5,3), (5,5), (5,7), (5,9)) lies on this wall!
    wall = WallSegment(Point2D(5.0, 0.0), Point2D(5.0, 10.0), is_opaque=True)
    floorplan = FloorPlan(boundary=boundary, walls=[wall])

    grid = SamplingGrid.generate(floorplan, resolution=2.0)
    # 25 total - 5 on the wall = 20 valid nodes
    assert grid.num_nodes == 20
    assert not any(pt.x == pytest.approx(5.0) for pt in grid.points)


def test_grid_single_cell_when_resolution_matches_dimensions() -> None:
    """When resolution matches room dimensions, exactly one node at center is created."""
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    floorplan = FloorPlan(boundary=boundary)

    grid = SamplingGrid.generate(floorplan, resolution=10.0)
    assert grid.num_nodes == 1
    assert grid.nodes[0].point == Point2D(5.0, 5.0)


def test_grid_non_multiple_dimensions() -> None:
    """DEFECT 2: Validate uniform axis partitioning when room dimensions are not integer multiples of resolution.
    Room: 11.0m x 7.0m, resolution: 2.0m.
    nx = ceil(11/2) = 6, dx = 11/6 (~1.833m)
    ny = ceil(7/2) = 4, dy = 7/4 (1.75m)
    Total nodes: 6 x 4 = 24 nodes, all with identical cell area (dx * dy).
    """
    boundary = BoundingBox(0.0, 11.0, 0.0, 7.0)
    floorplan = FloorPlan(boundary=boundary)

    grid = SamplingGrid.generate(floorplan, resolution=2.0)

    assert grid.num_nodes == 24
    assert grid.cell_width == pytest.approx(11.0 / 6.0)
    assert grid.cell_height == pytest.approx(7.0 / 4.0)
    assert grid.cell_area == pytest.approx((11.0 / 6.0) * (7.0 / 4.0))

    expected_xs = [(i + 0.5) * (11.0 / 6.0) for i in range(6)]
    expected_ys = [(j + 0.5) * (7.0 / 4.0) for j in range(4)]
    expected_coords = [(cx, cy) for cy in expected_ys for cx in expected_xs]

    actual_coords = [(node.point.x, node.point.y) for node in grid.nodes]
    for actual, expected in zip(actual_coords, expected_coords, strict=True):
        assert actual[0] == pytest.approx(expected[0])
        assert actual[1] == pytest.approx(expected[1])

    # Verify every node is strictly within interior free space
    assert all(0.0 < node.point.x < 11.0 for node in grid.nodes)
    assert all(0.0 < node.point.y < 7.0 for node in grid.nodes)


# ---------------------------------------------------------------------------
# Regression Tests: Defect 4 (Empty Grid and Safety Limits)
# ---------------------------------------------------------------------------


def test_defect_4_grid_rejects_empty_grid_when_free_space_has_no_cells() -> None:
    """DEFECT 4: Raise descriptive ValueError if obstacle configuration leaves zero evaluation nodes."""
    # 2x2 room with obstacle from (0.01, 0.01) to (1.99, 1.99)
    boundary = BoundingBox(0.0, 2.0, 0.0, 2.0)
    obstacle = ObstaclePolygon.from_rectangle(0.01, 1.99, 0.01, 1.99)
    floorplan = FloorPlan(boundary=boundary, obstacles=[obstacle])

    with pytest.raises(ValueError, match="0 valid evaluation nodes in free space"):
        SamplingGrid.generate(floorplan, resolution=2.0)


def test_defect_4_grid_rejects_excessive_cell_allocation() -> None:
    """DEFECT 4: Safety protection against disproportionate grid size requests."""
    boundary = BoundingBox(0.0, 100.0, 0.0, 100.0)
    floorplan = FloorPlan(boundary=boundary)

    # Resolution 0.1m would require 1,000 x 1,000 = 1,000,000 cells. With max_cells=10,000 it must be rejected
    with pytest.raises(ValueError, match="exceeds maximum safety limit"):
        SamplingGrid.generate(floorplan, resolution=0.1, max_cells=10_000)


def test_grid_rejects_subnormal_extreme_resolution() -> None:
    """Regression test: Protect against extreme subnormal resolution (e.g. 1e-310).
    Must raise descriptive ValueError instead of OverflowError.
    """
    floorplan = FloorPlan(BoundingBox(0.0, 10.0, 0.0, 10.0))
    with pytest.raises(ValueError, match="too small|exceeds"):
        SamplingGrid.generate(floorplan, resolution=1e-310)

