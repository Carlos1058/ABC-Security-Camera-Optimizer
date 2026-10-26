"""Unit tests for FloorPlan, WallSegment, ObstaclePolygon and spatial visibility."""

import pytest

from camera_optimizer.domain.floorplan import FloorPlan
from camera_optimizer.domain.obstacle import ObstaclePolygon
from camera_optimizer.domain.risk_zone import RiskZone
from camera_optimizer.domain.wall import WallSegment
from camera_optimizer.geometry.bounding_box import BoundingBox
from camera_optimizer.geometry.point import Point2D


# ---------------------------------------------------------------------------
# Obstacle and Camera Position Tests (GEO-06, GEO-07)
# ---------------------------------------------------------------------------


def test_geo_06_point_inside_obstacle() -> None:
    """GEO-06: Square obstacle from (3,3) to (7,7), point (5,5).
    Result: Position inside obstacle is invalid for camera placement.
    """
    obstacle = ObstaclePolygon.from_rectangle(3.0, 7.0, 3.0, 7.0)
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    floorplan = FloorPlan(boundary=boundary, obstacles=[obstacle])

    test_point = Point2D(5.0, 5.0)

    # Directly in obstacle
    assert obstacle.contains_point(test_point, include_boundary=True) is True
    # In floorplan
    assert floorplan.is_free_position(test_point) is False
    assert floorplan.is_valid_camera_position(test_point) is False


def test_geo_07_point_outside_obstacle() -> None:
    """GEO-07: Same square obstacle (3,3) to (7,7), point (2,2).
    Result: Geometrically free position if inside floor plan and off walls.
    """
    obstacle = ObstaclePolygon.from_rectangle(3.0, 7.0, 3.0, 7.0)
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    floorplan = FloorPlan(boundary=boundary, obstacles=[obstacle])

    test_point = Point2D(2.0, 2.0)

    assert obstacle.contains_point(test_point, include_boundary=True) is False
    assert floorplan.is_free_position(test_point) is True
    assert floorplan.is_valid_camera_position(test_point) is True


def test_obstacle_boundary_exclusion() -> None:
    """Points lying directly on the perimeter of an obstacle are invalid."""
    obstacle = ObstaclePolygon.from_rectangle(3.0, 7.0, 3.0, 7.0)
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    floorplan = FloorPlan(boundary=boundary, obstacles=[obstacle])

    edge_point = Point2D(3.0, 5.0)
    assert obstacle.contains_point(edge_point, include_boundary=True) is True
    assert floorplan.is_free_position(edge_point) is False
    assert floorplan.is_valid_camera_position(edge_point) is False


# ---------------------------------------------------------------------------
# Visibility and Wall Tests (GEO-08, GEO-09)
# ---------------------------------------------------------------------------


def test_geo_08_interior_wall_blocks_vision() -> None:
    """GEO-08: Camera and target on opposite sides of an interior opaque wall without opening.
    Boundary: 10x10 m.
    Wall: from (5, 0) to (5, 10).
    Camera: (2, 5).
    Target: (8, 5).
    Result: Vision blocked.
    """
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    wall = WallSegment(Point2D(5.0, 0.0), Point2D(5.0, 10.0), is_opaque=True)
    floorplan = FloorPlan(boundary=boundary, walls=[wall])

    camera = Point2D(2.0, 5.0)
    target = Point2D(8.0, 5.0)

    assert floorplan.is_valid_camera_position(camera) is True
    assert floorplan.is_free_position(target) is True

    visible = floorplan.check_visibility(camera, target)
    assert visible is False


def test_geo_09_door_opening_permits_vision() -> None:
    """GEO-09: A wall composed of two segments separated by an opening (doorway).
    Wall segment 1: (5, 0) to (5, 4).
    Wall segment 2: (5, 6) to (5, 10).
    Opening: y in (4, 6) at x = 5.
    Camera: (2, 5).
    Target: (8, 5).
    Result: Line of sight through the opening is NOT artificially blocked.
    """
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    wall1 = WallSegment(Point2D(5.0, 0.0), Point2D(5.0, 4.0), is_opaque=True)
    wall2 = WallSegment(Point2D(5.0, 6.0), Point2D(5.0, 10.0), is_opaque=True)
    floorplan = FloorPlan(boundary=boundary, walls=[wall1, wall2])

    camera = Point2D(2.0, 5.0)
    target = Point2D(8.0, 5.0)

    assert floorplan.is_valid_camera_position(camera) is True
    assert floorplan.is_free_position(target) is True

    visible = floorplan.check_visibility(camera, target)
    assert visible is True


def test_camera_position_boundaries_and_walls() -> None:
    """Validate camera position rejection criteria."""
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    wall = WallSegment(Point2D(2.0, 2.0), Point2D(8.0, 2.0), is_opaque=True)
    floorplan = FloorPlan(boundary=boundary, walls=[wall])

    # Outside floorplan
    assert floorplan.is_valid_camera_position(Point2D(-1.0, 5.0)) is False
    assert floorplan.is_valid_camera_position(Point2D(11.0, 5.0)) is False

    # Exactly on perimeter boundary
    assert floorplan.is_valid_camera_position(Point2D(0.0, 5.0)) is False
    assert floorplan.is_valid_camera_position(Point2D(10.0, 5.0)) is False

    # Directly on an interior wall
    assert floorplan.is_valid_camera_position(Point2D(5.0, 2.0)) is False

    # Valid interior point
    assert floorplan.is_valid_camera_position(Point2D(5.0, 5.0)) is True


def test_floorplan_rejects_obstacle_breaching_boundary() -> None:
    """An obstacle protruding outside the floor plan boundary raises ValueError."""
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    breaching_obstacle = ObstaclePolygon.from_rectangle(8.0, 12.0, 2.0, 4.0)

    with pytest.raises(ValueError, match="extends outside floor plan boundary"):
        FloorPlan(boundary=boundary, obstacles=[breaching_obstacle])


def test_concave_l_shaped_obstacle() -> None:
    """Validate that non-convex (L-shaped) simple obstacles function correctly."""
    # L-shaped polygon
    vertices = [
        Point2D(0.0, 0.0),
        Point2D(6.0, 0.0),
        Point2D(6.0, 2.0),
        Point2D(2.0, 2.0),
        Point2D(2.0, 6.0),
        Point2D(0.0, 6.0),
    ]
    obstacle = ObstaclePolygon(vertices)
    assert obstacle.area == pytest.approx(12.0 + 8.0)  # (6x2) + (2x4) = 20.0

    # Point inside the lower leg: (4, 1)
    assert obstacle.contains_point(Point2D(4.0, 1.0)) is True
    # Point inside the vertical leg: (1, 4)
    assert obstacle.contains_point(Point2D(1.0, 4.0)) is True
    # Point in the concave cutout: (4, 4) -> OUTSIDE
    assert obstacle.contains_point(Point2D(4.0, 4.0)) is False


def test_risk_zone_validation() -> None:
    """Validate that risk zones reject weights < 1.0 and non-finite values."""
    with pytest.raises(ValueError, match=">= 1.0"):
        RiskZone.from_rectangle(0.0, 5.0, 0.0, 5.0, weight=0.5)

    with pytest.raises(ValueError, match=">= 1.0"):
        RiskZone.from_rectangle(0.0, 5.0, 0.0, 5.0, weight=-1.0)

    with pytest.raises(ValueError, match="finite"):
        RiskZone.from_rectangle(0.0, 5.0, 0.0, 5.0, weight=float("nan"))


def test_visibility_through_multiple_walls_with_subsequent_occlusion() -> None:
    """A ray clears a first doorway at x=3, but is blocked by a second solid wall at x=7."""
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    # First partition with doorway around y=5
    w1_lower = WallSegment(Point2D(3.0, 0.0), Point2D(3.0, 4.0))
    w1_upper = WallSegment(Point2D(3.0, 6.0), Point2D(3.0, 10.0))
    # Second partition without doorway
    w2_solid = WallSegment(Point2D(7.0, 0.0), Point2D(7.0, 10.0))

    floorplan = FloorPlan(boundary=boundary, walls=[w1_lower, w1_upper, w2_solid])

    # Ray from (1, 5) to (9, 5)
    camera = Point2D(1.0, 5.0)
    target = Point2D(9.0, 5.0)

    assert floorplan.check_visibility(camera, target) is False

    # Ray from (1, 5) to (5, 5) (between partitions) -> clear!
    intermediate = Point2D(5.0, 5.0)
    assert floorplan.check_visibility(camera, intermediate) is True


def test_camera_placement_near_obstacle_tolerance() -> None:
    """Validate camera placement very close to an obstacle boundary."""
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    obstacle = ObstaclePolygon.from_rectangle(3.0, 7.0, 3.0, 7.0)
    floorplan = FloorPlan(boundary=boundary, obstacles=[obstacle])

    # Point 1mm outside obstacle (x=2.999) -> valid free position
    pt_outside = Point2D(2.999, 5.0)
    assert floorplan.is_valid_camera_position(pt_outside) is True

    # Point directly on obstacle boundary (x=3.000) -> invalid
    pt_on_edge = Point2D(3.0, 5.0)
    assert floorplan.is_valid_camera_position(pt_on_edge) is False

    # Point 1mm inside obstacle (x=3.001) -> invalid
    pt_inside = Point2D(3.001, 5.0)
    assert floorplan.is_valid_camera_position(pt_inside) is False


# ---------------------------------------------------------------------------
# Regression Tests: Defect 1 (Zero-Length / Identical Points Visibility)
# ---------------------------------------------------------------------------


def test_defect_1_visibility_identical_points_inside_obstacle_rejected() -> None:
    """DEFECT 1: check_visibility with identical points inside an obstacle must return False."""
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    obstacle = ObstaclePolygon.from_rectangle(3.0, 7.0, 3.0, 7.0)
    floorplan = FloorPlan(boundary=boundary, obstacles=[obstacle])

    pt_inside = Point2D(5.0, 5.0)
    # Both with endpoint validation and without, a zero-length line of sight is invalid
    assert floorplan.check_visibility(pt_inside, pt_inside, validate_endpoints=True) is False
    assert floorplan.check_visibility(pt_inside, pt_inside, validate_endpoints=False) is False


def test_defect_1_visibility_identical_points_outside_room_rejected() -> None:
    """DEFECT 1: check_visibility with identical points outside the enclosure must return False."""
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    floorplan = FloorPlan(boundary=boundary)

    pt_outside = Point2D(20.0, 20.0)
    assert floorplan.check_visibility(pt_outside, pt_outside, validate_endpoints=True) is False
    assert floorplan.check_visibility(pt_outside, pt_outside, validate_endpoints=False) is False


def test_defect_1_visibility_identical_points_in_free_space_rejected() -> None:
    """DEFECT 1: Even in free interior space, a zero-length segment does not constitute an evaluable line of sight."""
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    floorplan = FloorPlan(boundary=boundary)

    pt_free = Point2D(5.0, 5.0)
    assert floorplan.check_visibility(pt_free, pt_free, validate_endpoints=True) is False
    assert floorplan.check_visibility(pt_free, pt_free, validate_endpoints=False) is False


# ---------------------------------------------------------------------------
# Regression Tests: Defect 3 (Walls and Risk Zones Outside Floor Plan)
# ---------------------------------------------------------------------------


def test_defect_3_floorplan_rejects_walls_completely_outside() -> None:
    """DEFECT 3: Walls entirely outside the floor plan boundary must be rejected."""
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    wall_outside = WallSegment(Point2D(20.0, 20.0), Point2D(30.0, 30.0))

    with pytest.raises(ValueError, match="lies outside floor plan boundary"):
        FloorPlan(boundary=boundary, walls=[wall_outside])


def test_defect_3_floorplan_rejects_walls_partially_outside() -> None:
    """DEFECT 3: Walls with one endpoint protruding outside the boundary must be rejected."""
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    wall_protruding = WallSegment(Point2D(5.0, 5.0), Point2D(15.0, 5.0))

    with pytest.raises(ValueError, match="lies outside floor plan boundary"):
        FloorPlan(boundary=boundary, walls=[wall_protruding])


def test_defect_3_floorplan_accepts_walls_connected_to_boundary() -> None:
    """DEFECT 3: Walls whose endpoints touch the boundary perimeter are valid."""
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    # Interior dividing wall spanning from west to east perimeter
    wall_spanning = WallSegment(Point2D(0.0, 5.0), Point2D(10.0, 5.0))
    # Wall starting at south perimeter extending inward
    wall_attached = WallSegment(Point2D(5.0, 0.0), Point2D(5.0, 5.0))

    floorplan = FloorPlan(boundary=boundary, walls=[wall_spanning, wall_attached])
    assert len(floorplan.walls) == 2


def test_defect_3_floorplan_rejects_risk_zones_outside_boundary() -> None:
    """DEFECT 3: Risk zones extending outside the floor plan boundary must be rejected."""
    boundary = BoundingBox(0.0, 10.0, 0.0, 10.0)
    risk_zone_outside = RiskZone.from_rectangle(8.0, 12.0, 2.0, 4.0, weight=3.0)

    with pytest.raises(ValueError, match="extends outside floor plan boundary"):
        FloorPlan(boundary=boundary, risk_zones=[risk_zone_outside])
