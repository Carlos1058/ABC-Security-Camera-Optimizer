"""Resource, computational budget, and complexity limits for the Camera Optimizer API.

These limits are carefully configured to ensure that optimization runs remain
responsive, prevent Denial of Service (DoS) from disproportionate inputs,
and guarantee execution within the memory and compute capacity of standard
workstations without restricting realistic academic and practical security scenarios.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResourceLimits:
    """Configurable limits for spatial, optimization, and computational budget parameters.

    Justifications:
    --------------
    - min_room_dimension (1.0m) / max_room_dimension (500.0m):
      A physical facility cannot be smaller than a tiny closet or larger than a massive
      industrial complex. Prevents floating-point scale breakdown.
    - min_grid_resolution (0.05m = 5cm):
      Sampling finer than 5cm creates hundreds of thousands of evaluation points with
      negligible visual benefit, causing high CPU and memory pressure.
    - max_grid_cells (50,000):
      For a 50m x 50m facility at 0.25m resolution, there are ~40,000 cells. 50,000 cells
      evaluates in a fraction of a second while guarding against gigabyte-scale matrix allocations.
    - min_cameras (1) / max_cameras (30):
      At K=30, the search space dimension D = 3K = 90. In continuous metaheuristics, 90 dimensions
      provides an extensive optimization challenge suitable for university benchmarking.
    - min_food_sources (2) / max_food_sources (100):
      ABC mathematically requires SN >= 2 to select distinct partner k != i. SN > 100 is rarely
      needed for local exploration and increases NFE linearly per cycle.
    - min_cycles (1) / max_cycles (1,000):
      Permits both single-step debugging and deep convergence runs while ensuring the synchronous
      HTTP request terminates in reasonable time.
    - min_limit (1) / max_limit (5,000):
      Limit controls scout abandonment. A limit of 1 tests immediate abandonment, while higher
      values test stagnation persistence.
    - max_walls (100) / max_obstacles (50):
      Every line of sight evaluation tests against all blocking segments. 100 walls and 50 obstacles
      permit realistic, highly partitioned commercial floorplans without quadratic slowdown.
    - max_vertices_per_polygon (50):
      Ample for regular, concave, and L/U-shaped architectural barriers.
    - max_risk_zones (30):
      Sufficient to model multiple priority rooms, entrances, server racks, and cash registers.
    - max_work_budget (100,000,000 operations):
      Global execution budget upper bound:
        NFE_upper ≈ SN + 2 * SN * MaxCycles + MaxCycles
        work_upper ≈ NFE_upper * K * grid_points
      Prevents simultaneously selecting maximum values across all dimensions (e.g. K=30, SN=100,
      MaxCycles=1000, grid_points=50,000 would require > 3e11 operations). A normal academic
      benchmark (e.g. K=4, SN=20, MaxCycles=40, grid_points=600) requires ~4e6 operations (<4% of budget).
    - max_population_history_elements (50,000):
      When record_population=True, stores (MaxCycles + 1) * SN * K camera poses.
      50,000 elements bounds memory and response JSON size to < 5MB.
    """

    min_room_dim: float = 1.0
    max_room_dim: float = 500.0
    min_grid_resolution: float = 0.05
    max_grid_resolution: float = 100.0
    max_grid_cells: int = 50_000

    min_cameras: int = 1
    max_cameras: int = 30

    min_food_sources: int = 2
    max_food_sources: int = 100

    min_cycles: int = 1
    max_cycles: int = 1_000

    min_limit: int = 1
    max_limit: int = 5_000

    max_walls: int = 100
    max_obstacles: int = 50
    max_vertices_per_polygon: int = 50
    max_risk_zones: int = 30

    max_work_budget: float = 100_000_000.0
    max_population_history_elements: int = 50_000
    max_coverage_work_budget: float = 25_000_000.0

    @staticmethod
    def estimate_nfe_upper(sn: int, max_cycles: int) -> int:
        """Calculate theoretical upper bound on objective function evaluations (NFE).

        NFE_upper = SN (initial) + SN * MaxCycles (employed) + SN * MaxCycles (onlooker) + MaxCycles (scout)
                  = SN + 2 * SN * MaxCycles + MaxCycles
        """
        return int(sn + 2 * sn * max_cycles + max_cycles)

    @classmethod
    def estimate_work_upper(cls, sn: int, max_cycles: int, k: int, grid_points: int) -> float:
        """Estimate upper bound on computational workload units.

        work_upper ≈ NFE_upper * K * grid_points
        """
        nfe_upper = cls.estimate_nfe_upper(sn, max_cycles)
        return float(nfe_upper) * float(k) * float(grid_points)

    @classmethod
    def estimate_coverage_work(cls, k: int, estimated_nodes: int, num_blocking_segments: int) -> float:
        """Estimate upper bound on computational work for a single spatial coverage evaluation.

        work ≈ K * estimated_nodes * (1 + num_blocking_segments)
        Guarantees that large facilities with dense grids and many obstacles/walls
        do not freeze the synchronous API worker before raytracing begins.
        """
        return float(k) * float(estimated_nodes) * float(1 + max(0, num_blocking_segments))

    @staticmethod
    def estimate_population_history_elements(max_cycles: int, sn: int, k: int) -> int:
        """Estimate total camera pose elements stored across all cycles when record_population=True.

        elements = (MaxCycles + 1) * SN * K
        """
        return int((max_cycles + 1) * sn * k)


DEFAULT_LIMITS = ResourceLimits()
