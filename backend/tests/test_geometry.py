"""Unit tests for geometric primitives, intersections, and polygon algorithms."""

import math
import pytest

from camera_optimizer.geometry.bounding_box import BoundingBox
from camera_optimizer.geometry.intersections import (
    DEFAULT_TOLERANCE,
    IntersectionType,
    blocks_line_of_sight,
    intersect_segments,
)
from camera_optimizer.geometry.point import Point2D
from camera_optimizer.geometry.polygon import Polygon2D
from camera_optimizer.geometry.segment import Segment2D


# ---------------------------------------------------------------------------
# Point2D Tests
# ---------------------------------------------------------------------------


def test_point2d_valid_creation_and_distance() -> None:
    p1 = Point2D(0.0, 0.0)
    p2 = Point2D(3.0, 4.0)
    assert p1.distance_to(p2) == pytest.approx(5.0)
    assert p2.as_tuple() == (3.0, 4.0)


def test_point2d_rejects_non_finite_coordinates() -> None:
    with pytest.raises(ValueError, match="finite"):
        Point2D(float("nan"), 0.0)
    with pytest.raises(ValueError, match="finite"):
        Point2D(0.0, float("inf"))
    with pytest.raises(ValueError, match="finite"):
        Point2D(float("-inf"), 0.0)


def test_point2d_rejects_invalid_types() -> None:
    with pytest.raises(TypeError):
        Point2D("abc", 1.0)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# BoundingBox Tests
# ---------------------------------------------------------------------------


def test_bounding_box_valid_properties() -> None:
    box = BoundingBox(0.0, 10.0, -5.0, 5.0)
    assert box.width == pytest.approx(10.0)
    assert box.height == pytest.approx(10.0)
    assert box.area == pytest.approx(100.0)
    assert box.center == Point2D(5.0, 0.0)


def test_bounding_box_containment() -> None:
    box = BoundingBox(0.0, 10.0, 0.0, 10.0)
    assert box.contains(Point2D(5.0, 5.0), inclusive=True)
    assert box.contains(Point2D(5.0, 5.0), inclusive=False)
    # Edge point
    assert box.contains(Point2D(0.0, 5.0), inclusive=True)
    assert not box.contains(Point2D(0.0, 5.0), inclusive=False)
    # Outside point
    assert not box.contains(Point2D(12.0, 5.0), inclusive=True)


def test_bounding_box_invalid_bounds() -> None:
    with pytest.raises(ValueError, match="xmin"):
        BoundingBox(10.0, 5.0, 0.0, 10.0)
    with pytest.raises(ValueError, match="ymin"):
        BoundingBox(0.0, 10.0, 10.0, 10.0)


# ---------------------------------------------------------------------------
# Segment2D Tests
# ---------------------------------------------------------------------------


def test_segment2d_valid_and_length() -> None:
    seg = Segment2D(Point2D(1.0, 1.0), Point2D(4.0, 5.0))
    assert seg.length == pytest.approx(5.0)


def test_segment2d_rejects_degenerate() -> None:
    with pytest.raises(ValueError, match="Degenerate segment"):
        Segment2D(Point2D(2.0, 3.0), Point2D(2.0, 3.0))


def test_segment2d_contains_point() -> None:
    seg = Segment2D(Point2D(0.0, 0.0), Point2D(10.0, 0.0))
    assert seg.contains_point(Point2D(5.0, 0.0))
    assert seg.contains_point(Point2D(0.0, 0.0))
    assert seg.contains_point(Point2D(10.0, 0.0))
    # Point off line
    assert not seg.contains_point(Point2D(5.0, 0.1))
    # Collinear point outside segment
    assert not seg.contains_point(Point2D(12.0, 0.0))


# ---------------------------------------------------------------------------
# Mandatory Geometry Test Cases (GEO-01 to GEO-05)
# ---------------------------------------------------------------------------


def test_geo_01_perpendicular_crossing() -> None:
    """GEO-01: Perpendicular ray-wall crossing.
    Ray: (2, 2) to (8, 2)
    Wall: (5, 0) to (5, 10)
    Result: Intersection at (5, 2), visibility blocked.
    """
    ray_start = Point2D(2.0, 2.0)
    ray_end = Point2D(8.0, 2.0)
    wall_start = Point2D(5.0, 0.0)
    wall_end = Point2D(5.0, 10.0)

    inter = intersect_segments(ray_start, ray_end, wall_start, wall_end)
    assert inter.type == IntersectionType.POINT
    assert inter.point is not None
    assert inter.point.x == pytest.approx(5.0)
    assert inter.point.y == pytest.approx(2.0)
    assert inter.t_param == pytest.approx(0.5)

    blocked = blocks_line_of_sight(ray_start, ray_end, wall_start, wall_end)
    assert blocked is True


def test_geo_02_no_intersection() -> None:
    """GEO-02: Ray stops before reaching the wall.
    Ray: (2, 2) to (4, 2)
    Wall: (5, 0) to (5, 10)
    Result: No intersection, visibility permitted.
    """
    ray_start = Point2D(2.0, 2.0)
    ray_end = Point2D(4.0, 2.0)
    wall_start = Point2D(5.0, 0.0)
    wall_end = Point2D(5.0, 10.0)

    inter = intersect_segments(ray_start, ray_end, wall_start, wall_end)
    assert inter.type == IntersectionType.NONE
    assert inter.point is None

    blocked = blocks_line_of_sight(ray_start, ray_end, wall_start, wall_end)
    assert blocked is False


def test_geo_03_collinearity() -> None:
    """GEO-03: Collinear overlap between ray and wall.
    Ray: (0, 5) to (10, 5)
    Wall: (2, 5) to (8, 5)
    Result: Overlap detected and vision blocked.
    """
    ray_start = Point2D(0.0, 5.0)
    ray_end = Point2D(10.0, 5.0)
    wall_start = Point2D(2.0, 5.0)
    wall_end = Point2D(8.0, 5.0)

    inter = intersect_segments(ray_start, ray_end, wall_start, wall_end)
    assert inter.type == IntersectionType.SEGMENT
    assert inter.overlap_start is not None
    assert inter.overlap_end is not None
    assert inter.overlap_start.x == pytest.approx(2.0)
    assert inter.overlap_end.x == pytest.approx(8.0)

    blocked = blocks_line_of_sight(ray_start, ray_end, wall_start, wall_end)
    assert blocked is True


def test_geo_04_vertex_contact() -> None:
    """GEO-04: Line of sight passes exactly through an endpoint of an opaque wall.
    Ray: (0, 0) to (10, 10)
    Wall: (5, 5) to (5, 10) - endpoint (5, 5) lies in the interior of the ray (t = 0.5).
    Result: Occlusion because contact occurs in the interior of the visual path.
    """
    ray_start = Point2D(0.0, 0.0)
    ray_end = Point2D(10.0, 10.0)
    wall_start = Point2D(5.0, 5.0)
    wall_end = Point2D(5.0, 10.0)

    inter = intersect_segments(ray_start, ray_end, wall_start, wall_end)
    assert inter.type == IntersectionType.POINT
    assert inter.point is not None
    assert inter.point.x == pytest.approx(5.0)
    assert inter.point.y == pytest.approx(5.0)
    assert inter.t_param == pytest.approx(0.5)
    assert inter.u_param == pytest.approx(0.0)  # Exact vertex of the wall

    blocked = blocks_line_of_sight(ray_start, ray_end, wall_start, wall_end)
    assert blocked is True


def test_geo_05_parallel_separated() -> None:
    """GEO-05: Parallel separated segments.
    Ray: (0, 0) to (10, 0)
    Wall: (0, 2) to (10, 2)
    Result: No intersection exists.
    """
    ray_start = Point2D(0.0, 0.0)
    ray_end = Point2D(10.0, 0.0)
    wall_start = Point2D(0.0, 2.0)
    wall_end = Point2D(10.0, 2.0)

    inter = intersect_segments(ray_start, ray_end, wall_start, wall_end)
    assert inter.type == IntersectionType.NONE
    assert inter.point is None

    blocked = blocks_line_of_sight(ray_start, ray_end, wall_start, wall_end)
    assert blocked is False


# ---------------------------------------------------------------------------
# Polygon2D Tests
# ---------------------------------------------------------------------------


def test_polygon2d_valid_and_area() -> None:
    vertices = [Point2D(0.0, 0.0), Point2D(4.0, 0.0), Point2D(4.0, 3.0), Point2D(0.0, 3.0)]
    poly = Polygon2D(vertices)
    assert poly.num_vertices == 4
    assert poly.area == pytest.approx(12.0)
    assert len(poly.edges) == 4


def test_polygon2d_rejects_insufficient_vertices() -> None:
    with pytest.raises(ValueError, match="at least 3"):
        Polygon2D([Point2D(0.0, 0.0), Point2D(1.0, 1.0)])


def test_polygon2d_rejects_self_intersection() -> None:
    # Hourglass / bowtie shape (self-intersecting)
    vertices = [
        Point2D(0.0, 0.0),
        Point2D(4.0, 4.0),
        Point2D(4.0, 0.0),
        Point2D(0.0, 4.0),
    ]
    with pytest.raises(ValueError, match="Self-intersecting"):
        Polygon2D(vertices)


def test_polygon2d_rejects_collinear_zero_area() -> None:
    vertices = [Point2D(0.0, 0.0), Point2D(2.0, 0.0), Point2D(5.0, 0.0)]
    with pytest.raises(ValueError, match="collinearly|near-zero area"):
        Polygon2D(vertices)


# ---------------------------------------------------------------------------
# Advanced Geometric Edge Cases & Degeneracy Tests
# ---------------------------------------------------------------------------


def test_segment_t_junction_intersection() -> None:
    """T-junction: one segment's endpoint lands on the interior of another segment."""
    s1 = Segment2D(Point2D(0.0, 5.0), Point2D(10.0, 5.0))
    s2 = Segment2D(Point2D(5.0, 5.0), Point2D(5.0, 10.0))

    inter = s1.intersect_with(s2)
    assert inter.type == IntersectionType.POINT
    assert inter.point == Point2D(5.0, 5.0)
    assert inter.t_param == pytest.approx(0.5)
    assert inter.u_param == pytest.approx(0.0)


def test_segment_v_junction_intersection() -> None:
    """V-junction: two segments share an endpoint."""
    s1 = Segment2D(Point2D(0.0, 0.0), Point2D(5.0, 5.0))
    s2 = Segment2D(Point2D(5.0, 5.0), Point2D(10.0, 0.0))

    inter = s1.intersect_with(s2)
    assert inter.type == IntersectionType.POINT
    assert inter.point == Point2D(5.0, 5.0)
    assert inter.t_param == pytest.approx(1.0)
    assert inter.u_param == pytest.approx(0.0)


def test_collinear_disjoint_segments() -> None:
    """Two segments on the same line that do not touch or overlap."""
    s1 = Segment2D(Point2D(0.0, 0.0), Point2D(3.0, 0.0))
    s2 = Segment2D(Point2D(5.0, 0.0), Point2D(8.0, 0.0))

    inter = s1.intersect_with(s2)
    assert inter.type == IntersectionType.NONE
    assert inter.point is None


def test_collinear_touching_at_single_endpoint() -> None:
    """Two collinear segments that meet exactly at one point."""
    s1 = Segment2D(Point2D(0.0, 0.0), Point2D(5.0, 0.0))
    s2 = Segment2D(Point2D(5.0, 0.0), Point2D(10.0, 0.0))

    inter = s1.intersect_with(s2)
    assert inter.type == IntersectionType.POINT
    assert inter.point == Point2D(5.0, 0.0)


def test_nearly_parallel_intersecting_outside_bounds() -> None:
    """Lines intersect mathematically, but intersection point is far outside segments."""
    s1 = Segment2D(Point2D(0.0, 0.0), Point2D(10.0, 0.0))
    # Slightly non-parallel line (slope 0.001) starting 1m above
    s2 = Segment2D(Point2D(0.0, 1.0), Point2D(10.0, 1.01))

    inter = s1.intersect_with(s2)
    assert inter.type == IntersectionType.NONE


def test_concave_u_shaped_polygon() -> None:
    """Non-convex (U-shaped) polygon with interior channel."""
    # U-shaped polygon of 6x6 with 2x4 central channel cut out from top
    vertices = [
        Point2D(0.0, 0.0),
        Point2D(6.0, 0.0),
        Point2D(6.0, 6.0),
        Point2D(4.0, 6.0),
        Point2D(4.0, 2.0),
        Point2D(2.0, 2.0),
        Point2D(2.0, 6.0),
        Point2D(0.0, 6.0),
    ]
    poly = Polygon2D(vertices)
    assert poly.area == pytest.approx(36.0 - 8.0)  # 28.0 m^2

    # Point in the open channel (3, 4) -> OUTSIDE
    assert poly.contains_point(Point2D(3.0, 4.0)) is False
    # Point in the solid left prong (1, 4) -> INSIDE
    assert poly.contains_point(Point2D(1.0, 4.0)) is True
    # Point in the solid right prong (5, 4) -> INSIDE
    assert poly.contains_point(Point2D(5.0, 4.0)) is True
    # Point in the solid bottom base (3, 1) -> INSIDE
    assert poly.contains_point(Point2D(3.0, 1.0)) is True


def test_nearly_parallel_segments_intersecting_inside_bounds() -> None:
    """Regression test: Segments with nearly parallel direction vectors (converging slowly)
    having a real geometric intersection point strictly inside their parameter intervals [0, 1].
    P1 = (0, 0), P2 = (10, 0)
    P3 = (0, -2e-9), P4 = (10, 3e-9)
    Geometric crossing is at (4, 0).
    """
    p1 = Point2D(0.0, 0.0)
    p2 = Point2D(10.0, 0.0)
    p3 = Point2D(0.0, -2e-9)
    p4 = Point2D(10.0, 3e-9)

    result = intersect_segments(p1, p2, p3, p4)
    assert result.type == IntersectionType.POINT
    assert result.point is not None
    assert result.point.x == pytest.approx(4.0)
    assert result.point.y == pytest.approx(0.0)
    assert result.t_param == pytest.approx(0.4)
    assert result.u_param == pytest.approx(0.4)

