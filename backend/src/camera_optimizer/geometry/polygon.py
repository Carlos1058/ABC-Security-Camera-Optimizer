"""2D Simple Polygon representation and topological queries."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from camera_optimizer.geometry.bounding_box import BoundingBox
from camera_optimizer.geometry.intersections import DEFAULT_TOLERANCE, IntersectionType
from camera_optimizer.geometry.point import Point2D
from camera_optimizer.geometry.segment import Segment2D


@dataclass(frozen=True, slots=True)
class Polygon2D:
    """Represents a simple, non-self-intersecting 2D polygon with at least 3 vertices."""

    vertices: tuple[Point2D, ...]

    def __init__(self, vertices: Sequence[Point2D], tol: float = DEFAULT_TOLERANCE) -> None:
        """Initialize and validate a simple polygon.

        Parameters
        ----------
        vertices : Sequence[Point2D]
            Ordered sequence of polygon vertices (CCW or CW).
        tol : float
            Numerical tolerance for singularity and self-intersection tests.
        """
        if not isinstance(vertices, Sequence) or len(vertices) < 3:
            raise ValueError(f"Polygon must have at least 3 vertices, got {len(vertices) if isinstance(vertices, Sequence) else type(vertices).__name__}")

        norm_vertices: list[Point2D] = []
        for idx, pt in enumerate(vertices):
            if not isinstance(pt, Point2D):
                raise TypeError(f"Vertex at index {idx} must be a Point2D, got {type(pt).__name__}")
            norm_vertices.append(pt)

        # Validate that consecutive vertices are distinct
        n = len(norm_vertices)
        for i in range(n):
            j = (i + 1) % n
            if norm_vertices[i].distance_to(norm_vertices[j]) < tol:
                raise ValueError(
                    f"Consecutive vertices at indices {i} and {j} are identical within tolerance"
                )

        # Construct edges
        edges = [Segment2D(norm_vertices[i], norm_vertices[(i + 1) % n]) for i in range(n)]

        # Validate simplicity (no self-intersections)
        for i in range(n):
            for j in range(i + 1, n):
                is_adjacent = (j == i + 1) or (i == 0 and j == n - 1)
                inter = edges[i].intersect_with(edges[j], tol=tol)

                if is_adjacent:
                    # Adjacent edges must only touch at their shared vertex and must not overlap collinearly
                    if inter.type == IntersectionType.SEGMENT:
                        raise ValueError(f"Adjacent edges {i} and {j} overlap collinearly")
                else:
                    # Non-adjacent edges must not intersect at all
                    if inter.type != IntersectionType.NONE:
                        raise ValueError(f"Self-intersecting polygon: edge {i} intersects edge {j}")

        # Compute signed area via Shoelace formula
        signed_area = 0.0
        for i in range(n):
            j = (i + 1) % n
            signed_area += norm_vertices[i].x * norm_vertices[j].y - norm_vertices[j].x * norm_vertices[i].y
        signed_area /= 2.0

        if abs(signed_area) < tol:
            raise ValueError(f"Degenerate polygon with near-zero area: {abs(signed_area):.2e}")

        object.__setattr__(self, "vertices", tuple(norm_vertices))

    def __repr__(self) -> str:
        try:
            return f"Polygon2D({len(self.vertices)} vertices)"
        except AttributeError:
            return "Polygon2D(uninitialized)"

    @property
    def num_vertices(self) -> int:
        """Number of vertices in the polygon."""
        return len(self.vertices)

    @property
    def edges(self) -> tuple[Segment2D, ...]:
        """Boundary segments connecting consecutive vertices."""
        n = len(self.vertices)
        return tuple(Segment2D(self.vertices[i], self.vertices[(i + 1) % n]) for i in range(n))

    @property
    def signed_area(self) -> float:
        """Signed area of the polygon (positive for CCW, negative for CW)."""
        n = len(self.vertices)
        acc = 0.0
        for i in range(n):
            j = (i + 1) % n
            acc += self.vertices[i].x * self.vertices[j].y - self.vertices[j].x * self.vertices[i].y
        return acc / 2.0

    @property
    def area(self) -> float:
        """Positive area in square meters."""
        return abs(self.signed_area)

    @property
    def bounding_box(self) -> BoundingBox:
        """Axis-aligned bounding box enclosing the polygon."""
        xs = [pt.x for pt in self.vertices]
        ys = [pt.y for pt in self.vertices]
        return BoundingBox(min(xs), max(xs), min(ys), max(ys))

    def contains_point(self, point: Point2D, include_boundary: bool = True, tol: float = DEFAULT_TOLERANCE) -> bool:
        """Determine if a point lies inside the polygon using the winding number algorithm.

        Parameters
        ----------
        point : Point2D
            Query point.
        include_boundary : bool
            If True, points lying on any edge are considered inside.
        tol : float
            Tolerance for boundary checks.

        Returns
        -------
        bool
            True if point is inside (or on boundary when include_boundary=True).
        """
        if not isinstance(point, Point2D):
            raise TypeError(f"Expected Point2D instance, got {type(point).__name__}")

        # Fast rejection via bounding box
        box = self.bounding_box
        if not (box.xmin - tol <= point.x <= box.xmax + tol and box.ymin - tol <= point.y <= box.ymax + tol):
            return False

        # Explicit boundary check
        for edge in self.edges:
            if edge.contains_point(point, tol=tol):
                return include_boundary

        # Winding number calculation
        wn = 0
        n = len(self.vertices)
        for i in range(n):
            v1 = self.vertices[i]
            v2 = self.vertices[(i + 1) % n]

            if v1.y <= point.y:
                if v2.y > point.y:
                    # Upward crossing: test if point is strictly to the left of directed edge v1->v2
                    cross = (v2.x - v1.x) * (point.y - v1.y) - (v2.y - v1.y) * (point.x - v1.x)
                    if cross > tol:
                        wn += 1
            else:
                if v2.y <= point.y:
                    # Downward crossing: test if point is strictly to the right of directed edge v1->v2
                    cross = (v2.x - v1.x) * (point.y - v1.y) - (v2.y - v1.y) * (point.x - v1.x)
                    if cross < -tol:
                        wn -= 1

        return wn != 0
