"""Domain model for the 2D FloorPlan facility and spatial validation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from camera_optimizer.domain.obstacle import ObstaclePolygon
from camera_optimizer.domain.risk_zone import RiskZone
from camera_optimizer.domain.wall import WallSegment
from camera_optimizer.geometry.bounding_box import BoundingBox
from camera_optimizer.geometry.intersections import DEFAULT_TOLERANCE
from camera_optimizer.geometry.point import Point2D


@dataclass
class FloorPlan:
    """Represents a 2D facility floor plan including boundaries, walls, obstacles and risk zones."""

    boundary: BoundingBox
    walls: list[WallSegment] = field(default_factory=list)
    obstacles: list[ObstaclePolygon] = field(default_factory=list)
    risk_zones: list[RiskZone] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate components and verify obstacles do not breach boundary."""
        if not isinstance(self.boundary, BoundingBox):
            raise TypeError("FloorPlan boundary must be a BoundingBox")

        for idx, wall in enumerate(self.walls):
            if not isinstance(wall, WallSegment):
                raise TypeError(f"Wall at index {idx} must be a WallSegment")
            for pt_name, pt in (("start", wall.start), ("end", wall.end)):
                if (
                    pt.x < self.boundary.xmin - DEFAULT_TOLERANCE
                    or pt.x > self.boundary.xmax + DEFAULT_TOLERANCE
                    or pt.y < self.boundary.ymin - DEFAULT_TOLERANCE
                    or pt.y > self.boundary.ymax + DEFAULT_TOLERANCE
                ):
                    raise ValueError(
                        f"Wall at index {idx} {pt_name} endpoint ({pt}) lies outside floor plan boundary"
                    )

        for idx, obs in enumerate(self.obstacles):
            if not isinstance(obs, ObstaclePolygon):
                raise TypeError(f"Obstacle at index {idx} must be an ObstaclePolygon")
            # Verify obstacle is contained within floorplan boundaries
            obs_box = obs.polygon.bounding_box
            if (
                obs_box.xmin < self.boundary.xmin - DEFAULT_TOLERANCE
                or obs_box.xmax > self.boundary.xmax + DEFAULT_TOLERANCE
                or obs_box.ymin < self.boundary.ymin - DEFAULT_TOLERANCE
                or obs_box.ymax > self.boundary.ymax + DEFAULT_TOLERANCE
            ):
                raise ValueError(f"Obstacle at index {idx} extends outside floor plan boundary")

        for idx, zone in enumerate(self.risk_zones):
            if not isinstance(zone, RiskZone):
                raise TypeError(f"RiskZone at index {idx} must be a RiskZone")
            zone_box = zone.polygon.bounding_box
            if (
                zone_box.xmin < self.boundary.xmin - DEFAULT_TOLERANCE
                or zone_box.xmax > self.boundary.xmax + DEFAULT_TOLERANCE
                or zone_box.ymin < self.boundary.ymin - DEFAULT_TOLERANCE
                or zone_box.ymax > self.boundary.ymax + DEFAULT_TOLERANCE
            ):
                raise ValueError(f"RiskZone at index {idx} extends outside floor plan boundary")

    def all_blocking_segments(self) -> list[WallSegment]:
        """Aggregate all opaque line segments: interior walls and obstacle perimeters."""
        segments: list[WallSegment] = []
        for wall in self.walls:
            if wall.is_opaque:
                segments.append(wall)
        for obs in self.obstacles:
            segments.extend(obs.boundary_segments)
        return segments

    def is_free_position(self, point: Point2D, tol: float = DEFAULT_TOLERANCE) -> bool:
        """Check if a point is geometrically free (inside room, outside obstacles and off walls)."""
        if not isinstance(point, Point2D):
            raise TypeError(f"Expected Point2D instance, got {type(point).__name__}")

        # Must lie within bounding box
        if not self.boundary.contains(point, inclusive=True):
            return False

        # Cannot lie on any wall segment
        for wall in self.walls:
            if wall.contains_point(point, tol=tol):
                return False

        # Cannot lie inside or on the boundary of any solid obstacle
        for obs in self.obstacles:
            if obs.contains_point(point, include_boundary=True, tol=tol):
                return False

        return True

    def is_valid_camera_position(self, point: Point2D, tol: float = DEFAULT_TOLERANCE) -> bool:
        """Validate if a 2D coordinate is an admissible ceiling-mount camera location.

        Policy:
        - Must be strictly within the interior of the floor plan enclosure (not outside or on outer perimeter).
        - Cannot be inside a solid obstacle or on its boundary.
        - Cannot coincide with any interior opaque wall.
        """
        if not isinstance(point, Point2D):
            raise TypeError(f"Expected Point2D instance, got {type(point).__name__}")

        # Must be strictly inside bounding box (ceiling mount within interior space)
        if not (
            self.boundary.xmin + tol < point.x < self.boundary.xmax - tol
            and self.boundary.ymin + tol < point.y < self.boundary.ymax - tol
        ):
            return False

        # Must be in free space (no obstacles, no walls)
        return self.is_free_position(point, tol=tol)

    def check_visibility(
        self,
        p1: Point2D,
        p2: Point2D,
        validate_endpoints: bool = True,
        tol: float = DEFAULT_TOLERANCE,
    ) -> bool:
        """Determine if line of sight between p1 and p2 is unobstructed by walls or obstacles.

        Parameters
        ----------
        p1 : Point2D
            Observer position.
        p2 : Point2D
            Target position.
        validate_endpoints : bool
            If True, verifies that p1 and p2 are admissible non-occluded positions.
        tol : float
            Spatial tolerance in meters.

        Returns
        -------
        bool
            True if visual line of sight is clear, False if obstructed or if the
            endpoints are invalid / identical (zero-length segment).
        """
        if validate_endpoints:
            # Endpoints inside solid obstacles or directly on walls cannot have clear vision
            if not self.is_free_position(p1, tol=tol) or not self.is_free_position(p2, tol=tol):
                return False

        # A visual segment of zero length does not constitute an evaluable line of sight
        if p1.distance_to(p2) < tol:
            return False

        # Check against all opaque walls and obstacle perimeters
        for segment in self.all_blocking_segments():
            if segment.blocks_ray(p1, p2, tol=tol):
                return False

        return True
