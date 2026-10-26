"""Configuration and hyperparameters for the Sequential Artificial Bee Colony algorithm."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ABCConfig:
    """Hyperparameters governing execution of the sequential ABC algorithm.

    Attributes
    ----------
    num_food_sources : int
        Number of food sources (SN) in the colony, >= 2.
        Each food source corresponds to one employed bee and is tested by onlooker bees.
    max_cycles : int
        Maximum number of sequential search cycles (iterations), >= 1.
    limit : int | None
        Abandonment threshold: consecutive unsuccessful attempts before a food source
        is abandoned by a scout bee. If None, dynamically defaults to SN * D.
    seed : int | None
        Random seed for numpy.random.default_rng, ensuring full reproducibility.
    record_trace : bool
        If True, records step-by-step trace events for Employed, Onlooker, and Scout phases.
    record_population : bool
        If True, records a full independent snapshot of all food sources (positions,
        costs, trials) in each CycleRecord (including cycle 0) to allow authentic visual
        playback of colony dynamics. Defaults to False.

        Memory Consumption Note:
        Each source snapshot consumes approx (8*D + 200) bytes.
        Total memory over T cycles with SN sources:
            Memory ~ (T + 1) * SN * (8*D + 200) bytes.
        For K=2 cameras (D=6), T=30, SN=10: ~77 KB.
        For K=10 cameras (D=30), T=100, SN=20: ~888 KB (< 1 MB).
    """

    num_food_sources: int = 20
    max_cycles: int = 100
    limit: int | None = None
    seed: int | None = None
    record_trace: bool = False
    record_population: bool = False

    def __post_init__(self) -> None:
        """Validate ABC hyperparameters."""
        if not isinstance(self.num_food_sources, int):
            raise TypeError(f"num_food_sources must be an integer, got {type(self.num_food_sources).__name__}")
        if self.num_food_sources < 2:
            raise ValueError(
                f"num_food_sources (SN) must be >= 2 to permit partner bee selection (k != i), got {self.num_food_sources}"
            )

        if not isinstance(self.max_cycles, int):
            raise TypeError(f"max_cycles must be an integer, got {type(self.max_cycles).__name__}")
        if self.max_cycles < 1:
            raise ValueError(f"max_cycles must be >= 1, got {self.max_cycles}")

        if self.limit is not None:
            if not isinstance(self.limit, int):
                raise TypeError(f"limit must be an integer, got {type(self.limit).__name__}")
            if self.limit < 1:
                raise ValueError(f"limit must be >= 1, got {self.limit}")

        if self.seed is not None:
            if not isinstance(self.seed, int):
                raise TypeError(f"seed must be an integer or None, got {type(self.seed).__name__}")

        if not isinstance(self.record_trace, bool):
            raise TypeError(f"record_trace must be a boolean, got {type(self.record_trace).__name__}")

        if not isinstance(self.record_population, bool):
            raise TypeError(f"record_population must be a boolean, got {type(self.record_population).__name__}")
