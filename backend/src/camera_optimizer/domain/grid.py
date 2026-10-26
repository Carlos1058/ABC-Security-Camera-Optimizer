"""Domain model for evaluation sampling grid and deterministic node generation."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from camera_optimizer.domain.floorplan import FloorPlan
from camera_optimizer.geometry.intersections import DEFAULT_TOLERANCE
from camera_optimizer.geometry.point import Point2D


@dataclass(frozen=True, slots=True)
class GridNode:
    """Represents a discrete evaluation point with an associated risk weight."""

    point: Point2D
    weight: float

    def __post_init__(self) -> None:
        """Validate node attributes."""
        if not isinstance(self.point, Point2D):
            raise TypeError("GridNode point must be a Point2D")
        w = float(self.weight)
        if not math.isfinite(w) or w < 1.0:
            raise ValueError(f"GridNode weight must be >= 1.0, got {w}")
        object.__setattr__(self, "weight", w)


DEFAULT_MAX_GRID_CELLS: int = 1_000_000


@dataclass(frozen=True, slots=True)
class SamplingGrid:
    """Deterministic 2D evaluation grid discretizing the free space of a floor plan.

    Design note on free space discretization:
    Excluding cells whose centers fall inside obstacles or on walls is a discrete
    point-sampling approximation of the continuous free space area, not an exact
    analytical polygon-clipping decomposition. Refining the grid generally
    improves the spatial approximation of free space, though the approximation error
    does not necessarily decrease monotonically for every individual refinement step,
    as cell boundaries and sampling centers shift relative to obstacle edges.
    """

    resolution: float
    nodes: tuple[GridNode, ...]
    cell_width: float = 0.0
    cell_height: float = 0.0

    @classmethod
    def generate(
        cls,
        floorplan: FloorPlan,
        resolution: float,
        max_cells: int = DEFAULT_MAX_GRID_CELLS,
        tol: float = DEFAULT_TOLERANCE,
    ) -> SamplingGrid:
        """Generate evaluation nodes using uniform cell partitioning per axis.

        To prevent mathematical bias in coverage metrics when room dimensions
        are not integer multiples of resolution, the axes are divided into:
            nx = ceil(width / resolution),   dx = width / nx
            ny = ceil(height / resolution),  dy = height / ny
        All cells within the enclosure therefore possess identical area (dx * dy).

        Parameters
        ----------
        floorplan : FloorPlan
            Target facility floor plan.
        resolution : float
            Nominal maximum cell step size in meters (> 0.0).
        max_cells : int
            Safety threshold against disproportionate memory/CPU allocation.
        tol : float
            Spatial tolerance for exclusion queries.

        Returns
        -------
        SamplingGrid
            Deterministic grid with risk-weighted nodes in free interior space.

        Raises
        ------
        ValueError
            If resolution is non-positive, larger than room, exceeds max_cells,
            causes non-finite cell count quotients, or if zero valid nodes fall
            into the free interior space.
        """
        try:
            res = float(resolution)
        except (TypeError, ValueError) as err:
            raise TypeError(f"Resolution must be a real number, got {resolution!r}") from err

        if not math.isfinite(res) or res <= 0.0:
            raise ValueError(f"Sampling resolution must be finite and > 0, got {res}")

        if not isinstance(floorplan, FloorPlan):
            raise TypeError(f"Expected FloorPlan instance, got {type(floorplan).__name__}")

        box = floorplan.boundary

        if res > box.width or res > box.height:
            raise ValueError(
                f"Resolution {res}m is larger than floor plan dimensions ({box.width}x{box.height}m)"
            )

        # Validate that cell count quotients are finite numbers before integer conversion
        raw_nx = box.width / res
        raw_ny = box.height / res

        if not (math.isfinite(raw_nx) and math.isfinite(raw_ny)):
            raise ValueError(
                f"Resolution {res:.2e}m is too small: cell count quotient exceeds floating point limits."
            )

        # Guard against huge cell allocations before ceil and integer conversion
        if raw_nx > max_cells or raw_ny > max_cells or (raw_nx * raw_ny) > max_cells:
            raise ValueError(
                f"Requested resolution {res:.2e}m produces approximately {raw_nx * raw_ny:,.0f} cells, "
                f"which exceeds maximum safety limit of {max_cells:,} cells. Reduce resolution or adjust max_cells."
            )

        # Uniform partitioning per axis to prevent cell-area bias
        nx = int(math.ceil(raw_nx))
        ny = int(math.ceil(raw_ny))

        total_cells = nx * ny
        if total_cells > max_cells:
            raise ValueError(
                f"Requested grid size ({nx} x {ny} = {total_cells:,} cells) exceeds "
                f"maximum safety limit of {max_cells:,} cells. Reduce resolution or adjust max_cells."
            )

        dx = box.width / nx
        dy = box.height / ny

        x_centers = [box.xmin + (i + 0.5) * dx for i in range(nx)]
        y_centers = [box.ymin + (j + 0.5) * dy for j in range(ny)]

        nodes: list[GridNode] = []

        # Iterate deterministically row by row (y), then column by column (x)
        for cy in y_centers:
            for cx in x_centers:
                pt = Point2D(cx, cy)

                # Exclude point if it falls inside any solid obstacle or on a wall
                if not floorplan.is_free_position(pt, tol=tol):
                    continue

                # Determine risk weight: maximum applicable weight across matching risk zones
                matching_weights = [
                    zone.weight
                    for zone in floorplan.risk_zones
                    if zone.contains_point(pt, tol=tol)
                ]
                final_weight = max(matching_weights) if matching_weights else 1.0

                nodes.append(GridNode(point=pt, weight=final_weight))

        if not nodes:
            raise ValueError(
                f"Sampling grid generated 0 valid evaluation nodes in free space "
                f"(resolution={res}m across {nx}x{ny} cells). All cell centers fell inside "
                f"obstacles or on walls. Reduce resolution or modify scenario geometry."
            )

        return cls(
            resolution=res,
            nodes=tuple(nodes),
            cell_width=dx,
            cell_height=dy,
        )

    @property
    def cell_area(self) -> float:
        """Area of each individual discretization cell in square meters."""
        return self.cell_width * self.cell_height

    @property
    def num_nodes(self) -> int:
        """Total number of valid evaluation nodes in the grid."""
        return len(self.nodes)

    @property
    def points(self) -> list[Point2D]:
        """List of all evaluation points."""
        return [node.point for node in self.nodes]

    @property
    def weights(self) -> list[float]:
        """List of risk weights for all evaluation points."""
        return [node.weight for node in self.nodes]

    def as_numpy_arrays(self) -> tuple[np.ndarray, np.ndarray]:
        """Export grid nodes to NumPy arrays for vectorized calculations.

        Returns
        -------
        coords : np.ndarray
            Array of shape (N, 2) with coordinates [x, y] as float64.
        weights : np.ndarray
            Array of shape (N,) with risk weights as float64.
        """
        if not self.nodes:
            return np.empty((0, 2), dtype=np.float64), np.empty((0,), dtype=np.float64)

        coords = np.array([[node.point.x, node.point.y] for node in self.nodes], dtype=np.float64)
        weights = np.array([node.weight for node in self.nodes], dtype=np.float64)
        return coords, weights
