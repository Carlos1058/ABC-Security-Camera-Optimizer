"""Robust, deterministic 2D segment intersection and line-of-sight algorithms."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from camera_optimizer.geometry.point import Point2D

# Numerical tolerances for geometric computations:
# DEFAULT_SPATIAL_TOLERANCE: Absolute spatial tolerance in meters (1 nanometer).
DEFAULT_SPATIAL_TOLERANCE: float = 1e-9

# DEFAULT_ANGULAR_TOLERANCE: Dimensionless angular tolerance (~1e-12 radians)
# used to distinguish strictly parallel/collinear lines from converging lines.
DEFAULT_ANGULAR_TOLERANCE: float = 1e-12

# Backwards compatibility alias for spatial tolerance
DEFAULT_TOLERANCE: float = DEFAULT_SPATIAL_TOLERANCE


class IntersectionType(Enum):
    """Categorization of segment-segment intersections."""
    NONE = "none"
    POINT = "point"
    SEGMENT = "segment"  # Collinear overlap with non-zero length


@dataclass(frozen=True, slots=True)
class SegmentIntersection:
    """Detailed result of a segment-segment intersection test."""

    type: IntersectionType
    point: Point2D | None = None
    overlap_start: Point2D | None = None
    overlap_end: Point2D | None = None
    t_param: float | None = None  # Parameter on segment 1 [0, 1]
    u_param: float | None = None  # Parameter on segment 2 [0, 1]
    t_range: tuple[float, float] | None = None  # Overlap range on segment 1
    u_range: tuple[float, float] | None = None  # Overlap range on segment 2


def intersect_segments(
    p1: Point2D,
    p2: Point2D,
    p3: Point2D,
    p4: Point2D,
    tol: float = DEFAULT_TOLERANCE,
    angular_tol: float = DEFAULT_ANGULAR_TOLERANCE,
) -> SegmentIntersection:
    """Compute the intersection between segment S1 = [P1, P2] and segment S2 = [P3, P4].

    Parameters
    ----------
    p1, p2 : Point2D
        Endpoints of the first segment.
    p3, p4 : Point2D
        Endpoints of the second segment.
    tol : float
        Absolute spatial tolerance in meters (default: 1e-9 m = 1 nm).
        Controls distance tests, collinear overlap boundaries, and endpoint clamping.
    angular_tol : float
        Dimensionless angular tolerance in radians (default: 1e-12 rad).
        Used to determine whether direction vectors are parallel/collinear (|r x s| / (|r||s|) <= angular_tol).
        Prevents misclassifying nearly parallel converging segments as parallel when they have
        a genuine geometric intersection inside their closed parameter intervals [0, 1].

    Returns
    -------
    SegmentIntersection
        Deterministic result describing whether there is no intersection,
        a single intersection point, or a collinear overlapping segment.
    """
    rx = p2.x - p1.x
    ry = p2.y - p1.y
    sx = p4.x - p3.x
    sy = p4.y - p3.y

    len_r = math.hypot(rx, ry)
    len_s = math.hypot(sx, sy)

    if len_r < tol:
        raise ValueError(f"First segment is degenerate (length {len_r:.2e} < {tol:.2e})")
    if len_s < tol:
        raise ValueError(f"Second segment is degenerate (length {len_s:.2e} < {tol:.2e})")

    # Vector from P1 to P3
    qx = p3.x - p1.x
    qy = p3.y - p1.y

    # 2D cross product: r x s
    cross_rs = rx * sy - ry * sx
    # Normalized sine of angle between r and s
    sin_angle = abs(cross_rs) / (len_r * len_s)

    if sin_angle <= angular_tol:
        # Segments are parallel or collinear
        # Distance between the two lines: |q x r| / len_r
        cross_qr = qx * ry - qy * rx
        dist_between_lines = abs(cross_qr) / len_r

        if dist_between_lines > tol:
            # Parallel but separated
            return SegmentIntersection(type=IntersectionType.NONE)

        # Collinear segments: project S2 onto S1 line via dot products
        # t = ((P - P1) . r) / (len_r^2)
        inv_r_sq = 1.0 / (len_r * len_r)
        t3 = (qx * rx + qy * ry) * inv_r_sq
        t4 = ((p4.x - p1.x) * rx + (p4.y - p1.y) * ry) * inv_r_sq

        t_min_s2 = min(t3, t4)
        t_max_s2 = max(t3, t4)

        # Overlap interval on S1 parameter space [0, 1]
        t_start = max(0.0, t_min_s2)
        t_end = min(1.0, t_max_s2)

        tol_t = tol / len_r

        if t_start > t_end + tol_t:
            # Collinear, but disjoint along line
            return SegmentIntersection(type=IntersectionType.NONE)

        if abs(t_start - t_end) <= tol_t:
            # Touching at a single point on collinear line
            t_touch = max(0.0, min(1.0, (t_start + t_end) / 2.0))
            touch_pt = Point2D(p1.x + t_touch * rx, p1.y + t_touch * ry)
            return SegmentIntersection(
                type=IntersectionType.POINT,
                point=touch_pt,
                t_param=t_touch,
            )

        # Collinear overlap with non-zero length
        overlap_pt1 = Point2D(p1.x + t_start * rx, p1.y + t_start * ry)
        overlap_pt2 = Point2D(p1.x + t_end * rx, p1.y + t_end * ry)
        return SegmentIntersection(
            type=IntersectionType.SEGMENT,
            overlap_start=overlap_pt1,
            overlap_end=overlap_pt2,
            t_range=(t_start, t_end),
        )

    # Non-parallel lines: solve r x s * t = q x s, r x s * u = q x r
    # t = (q x s) / (r x s)
    # u = (q x r) / (r x s)
    cross_qs = qx * sy - qy * sx
    cross_qr = qx * ry - qy * rx

    t = cross_qs / cross_rs
    u = cross_qr / cross_rs

    tol_t = tol / len_r
    tol_u = tol / len_s

    # Check if intersection lies within both closed intervals [0, 1]
    if (-tol_t <= t <= 1.0 + tol_t) and (-tol_u <= u <= 1.0 + tol_u):
        t_clamped = max(0.0, min(1.0, t))
        u_clamped = max(0.0, min(1.0, u))
        inter_pt = Point2D(p1.x + t_clamped * rx, p1.y + t_clamped * ry)
        return SegmentIntersection(
            type=IntersectionType.POINT,
            point=inter_pt,
            t_param=t_clamped,
            u_param=u_clamped,
        )

    return SegmentIntersection(type=IntersectionType.NONE)


def blocks_line_of_sight(
    ray_start: Point2D,
    ray_end: Point2D,
    wall_start: Point2D,
    wall_end: Point2D,
    tol: float = DEFAULT_TOLERANCE,
    angular_tol: float = DEFAULT_ANGULAR_TOLERANCE,
) -> bool:
    """Determine if an opaque wall segment blocks the line of sight between two points.

    Geometric visibility policy:
    1. A normal intersection inside the ray's trajectory blocks vision.
    2. An intersection with a wall endpoint/vertex inside the interior of the visual
       ray is treated conservatively as occlusion.
    3. Collinear overlap with an opaque wall along any interior portion of the ray
       blocks vision.
    4. Intersections occurring solely at the ray's exact endpoints (t <= tol or t >= 1 - tol)
       do not occlude the interior of the ray (camera and target are validated separately).

    Parameters
    ----------
    ray_start : Point2D
        Position of observer (e.g. camera).
    ray_end : Point2D
        Position of target point.
    wall_start, wall_end : Point2D
        Endpoints of the opaque wall segment.
    tol : float
        Numerical tolerance in meters.
    angular_tol : float
        Dimensionless angular tolerance in radians.

    Returns
    -------
    bool
        True if the wall segment obstructs line of sight, False otherwise.
    """
    inter = intersect_segments(
        ray_start, ray_end, wall_start, wall_end, tol=tol, angular_tol=angular_tol
    )

    if inter.type == IntersectionType.NONE:
        return False

    ray_len = ray_start.distance_to(ray_end)
    tol_t = tol / ray_len

    if inter.type == IntersectionType.POINT:
        # Check if the contact occurs in the interior of the visual ray
        assert inter.t_param is not None
        t = inter.t_param
        # Must be strictly inside (0, 1) relative to ray endpoints
        return (tol_t < t < 1.0 - tol_t)

    if inter.type == IntersectionType.SEGMENT:
        # Collinear overlap: blocks if the overlap covers any interior portion of the ray
        assert inter.t_range is not None
        t_start, t_end = inter.t_range
        return (t_end > tol_t) and (t_start < 1.0 - tol_t)

    return False
