"""Accounting, telemetry, and cycle history tracking for SequentialABC."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from camera_optimizer.optimizer.food_source import FoodSource


@dataclass(frozen=True, slots=True)
class CycleRecord:
    """Historical telemetry record captured at the end of each ABC cycle.

    Attributes
    ----------
    cycle : int
        Cycle index (1-based, 0 represents initial population).
    best_cost : float
        Best objective cost found so far across the entire search history.
    best_position : np.ndarray
        Best solution vector found so far.
    mean_population_cost : float
        Mean objective cost of the current population.
    improvements_count : int
        Number of accepted greedy improvements in this cycle (Employed + Onlooker).
    scout_resets : int
        Number of food sources abandoned and reset by scout bees in this cycle (0 or 1).
    """

    cycle: int
    best_cost: float
    best_position: np.ndarray
    mean_population_cost: float
    improvements_count: int
    scout_resets: int
    population: tuple[FoodSource, ...] | None = None

    @property
    def mean_cost(self) -> float:
        """Alias for mean_population_cost."""
        return self.mean_population_cost

    @property
    def best_vector(self) -> np.ndarray:
        """Alias for best_position."""
        return self.best_position

    @property
    def improvements(self) -> int:
        """Alias for improvements_count."""
        return self.improvements_count

    def to_dict(self) -> dict[str, Any]:
        """Convert record to a JSON-serializable dictionary."""
        d: dict[str, Any] = {
            "cycle": self.cycle,
            "best_cost": self.best_cost,
            "best_position": self.best_position.tolist(),
            "mean_population_cost": self.mean_population_cost,
            "improvements_count": self.improvements_count,
            "scout_resets": self.scout_resets,
        }
        if self.population is not None:
            d["population"] = [
                {
                    "position": s.position.tolist(),
                    "cost": s.cost,
                    "fitness": s.fitness,
                    "trial": s.trial,
                }
                for s in self.population
            ]
        return d


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """Detailed micro-step event log for audit and visualization playback."""

    cycle: int
    phase: str  # "employed", "onlooker", "scout"
    source_index: int
    partner_index: int | None
    dimension_index: int | None
    phi: float | None
    candidate_cost: float | None
    accepted: bool
    reason: str  # "improved", "rejected_worse", "rejected_infeasible", "scout_reset"


@dataclass(slots=True)
class ABCTracker:
    """Internal state tracker accumulating evaluation counters and history."""

    nfe: int = 0
    total_proposals: int = 0
    rejected_infeasible: int = 0
    total_scout_resets: int = 0
    history: list[CycleRecord] = field(default_factory=list)
    trace: list[TraceEvent] = field(default_factory=list)

    @property
    def evaluations_count(self) -> int:
        """Alias for nfe (number of real function evaluations)."""
        return self.nfe

    @property
    def proposals_count(self) -> int:
        """Alias for total_proposals."""
        return self.total_proposals

    @property
    def trace_history(self) -> tuple[TraceEvent, ...]:
        """Read-only view of recorded trace events."""
        return tuple(self.trace)

    def record_proposal(self) -> None:
        self.total_proposals += 1

    def record_evaluation(self) -> None:
        self.nfe += 1

    def record_infeasible_rejection(self) -> None:
        self.rejected_infeasible += 1

    def record_scout_reset(self) -> None:
        self.total_scout_resets += 1

    def add_cycle(self, record: CycleRecord) -> None:
        self.history.append(record)

    def add_trace(self, event: TraceEvent) -> None:
        self.trace.append(event)


@dataclass(frozen=True, slots=True)
class ABCOutput:
    """Complete structured output produced by a SequentialABC optimization run.

    Attributes
    ----------
    best_source : FoodSource
        The best solution vector and cost found across all cycles.
    history : tuple[CycleRecord, ...]
        Evolution of best and mean costs per cycle.
    total_evaluations : int
        Total number of real objective function evaluations (NFE).
    total_proposals : int
        Total number of neighbor and initialization candidate vectors generated.
    rejected_infeasible_proposals : int
        Total number of proposed vectors rejected due to constraint violations.
    total_scout_resets : int
        Total number of abandoned food sources replaced by scouts.
    execution_time_seconds : float
        Elapsed wall-clock time in seconds for the complete sequential optimization.
    trace : tuple[TraceEvent, ...]
        Optional micro-event trace (empty if record_trace was False).
    """

    best_source: FoodSource
    history: tuple[CycleRecord, ...]
    total_evaluations: int
    total_proposals: int
    rejected_infeasible_proposals: int
    total_scout_resets: int
    execution_time_seconds: float
    trace: tuple[TraceEvent, ...] = field(default_factory=tuple)

    @property
    def best_cost(self) -> float:
        """Best historical objective cost achieved."""
        return self.best_source.cost

    @property
    def best_position(self) -> np.ndarray:
        """Best historical solution vector achieved."""
        return self.best_source.position

    @property
    def best_solution(self) -> np.ndarray:
        """Alias for best_position."""
        return self.best_source.position

    @property
    def evaluations_count(self) -> int:
        """Alias for total_evaluations."""
        return self.total_evaluations

    @property
    def proposals_count(self) -> int:
        """Alias for total_proposals."""
        return self.total_proposals

    @property
    def rejected_infeasible_count(self) -> int:
        """Alias for rejected_infeasible_proposals."""
        return self.rejected_infeasible_proposals

    @property
    def scout_resets_count(self) -> int:
        """Alias for total_scout_resets."""
        return self.total_scout_resets

    @property
    def num_cycles(self) -> int:
        """Total number of recorded cycles in history (including cycle 0)."""
        return len(self.history)

    def to_dict(self) -> dict[str, Any]:
        """Convert output summary to a dictionary."""
        return {
            "best_cost": self.best_source.cost,
            "best_position": self.best_source.position.tolist(),
            "best_fitness": self.best_source.fitness,
            "total_evaluations": self.total_evaluations,
            "total_proposals": self.total_proposals,
            "rejected_infeasible_proposals": self.rejected_infeasible_proposals,
            "total_scout_resets": self.total_scout_resets,
            "execution_time_seconds": self.execution_time_seconds,
            "num_cycles": len(self.history),
        }
