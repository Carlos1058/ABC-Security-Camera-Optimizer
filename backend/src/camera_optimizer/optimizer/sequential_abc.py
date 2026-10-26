"""Strictly sequential, reproducible Artificial Bee Colony (ABC) optimizer."""

from __future__ import annotations

import math
import time
from collections.abc import Sequence

import numpy as np

from camera_optimizer.optimizer.bounds import VariableType
from camera_optimizer.optimizer.config import ABCConfig
from camera_optimizer.optimizer.food_source import FoodSource, calculate_fitness
from camera_optimizer.optimizer.problem import OptimizationProblem
from camera_optimizer.optimizer.tracking import (
    ABCOutput,
    ABCTracker,
    CycleRecord,
    TraceEvent,
)


def compute_stable_mean(values: Sequence[float]) -> float:
    """Compute arithmetic mean in a numerically stable way preventing overflow.

    By dividing each element by N before accumulation, sum of finite values
    is strictly bounded within [min(values), max(values)], avoiding overflow
    to infinity when values are of order 1e308.
    """
    n = len(values)
    if n == 0:
        return 0.0
    total = 0.0
    for x in values:
        f_x = float(x)
        if not math.isfinite(f_x):
            raise ValueError(f"Cannot compute mean with non-finite value: {f_x}")
        total += f_x / n
    if not math.isfinite(total):
        raise ValueError(f"Computed population mean is not finite: {total}")
    return total


class SequentialABC:
    """Canonical Artificial Bee Colony metaheuristic algorithm, strictly sequential.

    Architectural guarantees & algorithmic specifications (Audited TAREA 04.2 / TAREA 05):
    - Independent of domain-specific models: optimises any continuous OptimizationProblem.
    - Strictly sequential: zero threading, multiprocessing, GPU, or distributed logic.
    - Fully reproducible: all stochastic decisions derive from numpy.random.default_rng(seed).
    - True ABC phases: Employed Bees, Onlooker Bees (fixed probabilities), Scout Bees (at most 1 per cycle).
    - Monotonically non-worsening historical best solution tracking.
    - Strict Greedy Selection: The greedy selection mechanism requires strict improvement (cand_cost < source.cost,
      equivalent to cand_fitness > source.fitness). This faithfully adheres to the canonical ABC MATLAB v2 reference
      implementation (Akay & Karaboga, https://abc.erciyes.edu.tr/form.aspx), which specifies 'if (FitnessSol > Fitness(i))'.
      The operator is strictly '>' (and '<' for minimization), never '>=' or '<='.
    - Infeasibility Policy: Proposed candidate solutions that violate domain constraints (is_valid == False) are rejected
      immediately without objective function evaluation and explicitly increment the trial counter of the food source.
      This policy prevents stagnation in infeasible regions for constrained problems such as camera placement.
    - Onlooker Selection Probabilities: Probabilities are calculated once at the start of the onlooker phase using the
      current population fitnesses and remain fixed throughout all SN onlooker selection attempts in that cycle.
    - Scout Abandonment Criterion: The abandonment condition is 'trial >= limit'. The food source with the maximum trial
      counter is abandoned and reset by a scout bee if its trial reaches or exceeds limit (at most 1 scout reset per cycle).
    """

    def __init__(self, problem: OptimizationProblem, config: ABCConfig | None = None) -> None:
        """Initialize optimizer with problem and configuration.

        Parameters
        ----------
        problem : OptimizationProblem
            Objective function, bounds, and domain validator to optimize.
        config : ABCConfig | None
            Hyperparameters for the colony. Defaults to ABCConfig() if None.
        """
        if not isinstance(problem, OptimizationProblem):
            raise TypeError(f"Expected OptimizationProblem instance, got {type(problem).__name__}")

        self._problem = problem
        self._config = config if config is not None else ABCConfig()

        if not isinstance(self._config, ABCConfig):
            raise TypeError(f"Expected ABCConfig instance, got {type(self._config).__name__}")

        sn = self._config.num_food_sources
        d = self._problem.dimension
        self._limit = self._config.limit if self._config.limit is not None else (sn * d)

        self._rng = np.random.default_rng(self._config.seed)
        self._sources: list[FoodSource] = []
        self._best_source: FoodSource | None = None
        self._tracker = ABCTracker()

    @property
    def problem(self) -> OptimizationProblem:
        """The optimization problem being solved."""
        return self._problem

    @property
    def config(self) -> ABCConfig:
        """The active hyperparameter configuration."""
        return self._config

    @property
    def limit(self) -> int:
        """The active scout abandonment limit."""
        return self._limit

    @property
    def population(self) -> tuple[FoodSource, ...]:
        """Current population of food sources."""
        return tuple(self._sources)

    @property
    def best_source(self) -> FoodSource | None:
        """Global best food source found so far across all cycles."""
        return self._best_source

    @property
    def tracker(self) -> ABCTracker:
        """The algorithm telemetry and event tracker."""
        return self._tracker

    def _validate_sampled_candidate(self, pos: np.ndarray, context: str) -> None:
        """Validate that a candidate generated by problem.sample_valid conforms to the contract.

        Parameters
        ----------
        pos : np.ndarray
            The sampled candidate vector.
        context : str
            Diagnostic description of the operation (e.g. 'initialization of food source 0').

        Raises
        ------
        TypeError
            If pos is not a NumPy ndarray.
        ValueError
            If pos is not 1D, has wrong dimension, contains non-finite values,
            violates declared bounds, or fails problem.is_valid().
        """
        if not isinstance(pos, np.ndarray):
            raise TypeError(
                f"Sampled candidate in {context} must be a numpy.ndarray, got {type(pos).__name__}"
            )
        if pos.ndim != 1:
            raise ValueError(
                f"Sampled candidate in {context} must be 1-dimensional, got shape {pos.shape}"
            )
        if len(pos) != self._problem.dimension:
            raise ValueError(
                f"Sampled candidate in {context} has length {len(pos)}, "
                f"expected problem dimension {self._problem.dimension}"
            )
        if not np.all(np.isfinite(pos)):
            raise ValueError(
                f"Sampled candidate in {context} contains non-finite values (NaN or Inf)"
            )

        # Bounds consistency verification
        bounds = self._problem.bounds
        for j in range(len(bounds)):
            spec = bounds[j]
            val = float(pos[j])
            if spec.var_type == VariableType.CIRCULAR_ANGLE:
                if not (-math.pi <= val < math.pi):
                    raise ValueError(
                        f"Sampled candidate in {context} dimension {j} has angle {val}, "
                        f"which lies outside the canonical circular domain [-pi, pi)"
                    )
            else:
                if not (spec.lower <= val <= spec.upper):
                    raise ValueError(
                        f"Sampled candidate in {context} dimension {j} has value {val}, "
                        f"which violates declared bounds [{spec.lower}, {spec.upper}]"
                    )

        # Domain problem validity check
        if not self._problem.is_valid(pos):
            raise ValueError(
                f"Sampled candidate in {context} was rejected by problem.is_valid(). "
                f"sample_valid() violated its contract to produce feasible solutions."
            )

    def initialize_population(self) -> None:
        """Generate and evaluate SN initial valid food sources, and identify the initial best."""
        self._sources.clear()
        self._tracker = ABCTracker()
        sn = self._config.num_food_sources

        for idx in range(sn):
            self._tracker.record_proposal()
            pos = self._problem.sample_valid(self._rng)
            self._validate_sampled_candidate(pos, context=f"initialization of food source {idx}")
            cost = self._problem.evaluate(pos)
            self._tracker.record_evaluation()
            fitness = calculate_fitness(cost)
            source = FoodSource(position=pos, cost=cost, fitness=fitness, trial=0)
            self._sources.append(source)

        # Initial best historical solution (independent deep copy)
        initial_best = min(self._sources, key=lambda s: s.cost)
        self._best_source = initial_best.copy()

        # Record cycle 0 (baseline population)
        mean_cost = compute_stable_mean([s.cost for s in self._sources])
        pop_snapshot = (
            tuple(s.copy() for s in self._sources)
            if self._config.record_population
            else None
        )
        self._tracker.add_cycle(
            CycleRecord(
                cycle=0,
                best_cost=self._best_source.cost,
                best_position=np.copy(self._best_source.position),
                mean_population_cost=mean_cost,
                improvements_count=0,
                scout_resets=0,
                population=pop_snapshot,
            )
        )

    def _select_partner(self, current_idx: int) -> int:
        """Select a partner index k != current_idx uniformly at random in O(1)."""
        sn = len(self._sources)
        k = int(self._rng.integers(0, sn - 1))
        if k >= current_idx:
            k += 1
        return k

    def employed_bees_phase(self, cycle: int) -> int:
        """Execute the Employed Bees phase sequentially for all SN food sources.

        For each food source i:
        1. Select partner k != i.
        2. Select dimension j in [0, D-1].
        3. Sample phi in [-1, 1].
        4. Generate neighbor v.
        5. Verify validity. If invalid, reject proposal and increment trial (policy for constrained problems).
        6. Evaluate v and apply greedy selection with strict improvement (cand_cost < source.cost,
           strictly matching canonical MATLAB v2 'FitnessSol > Fitness(i)' reference).

        Returns
        -------
        int
            Number of strictly improving solutions accepted in this phase.
        """
        improvements = 0
        sn = len(self._sources)
        d = self._problem.dimension
        bounds = self._problem.bounds

        for i in range(sn):
            source = self._sources[i]
            k = self._select_partner(i)
            partner = self._sources[k]
            j = int(self._rng.integers(0, d))
            phi = float(self._rng.uniform(-1.0, 1.0))

            v = bounds.perturb_dimension(
                x_i=source.position,
                x_k=partner.position,
                dim_index=j,
                phi=phi,
            )
            self._tracker.record_proposal()

            # Constraint / feasibility check
            if not self._problem.is_valid(v):
                self._tracker.record_infeasible_rejection()
                source.increment_trial()
                if self._config.record_trace:
                    self._tracker.add_trace(
                        TraceEvent(
                            cycle=cycle,
                            phase="employed",
                            source_index=i,
                            partner_index=k,
                            dimension_index=j,
                            phi=phi,
                            candidate_cost=None,
                            accepted=False,
                            reason="rejected_infeasible",
                        )
                    )
                continue

            # Real objective function evaluation
            cand_cost = self._problem.evaluate(v)
            self._tracker.record_evaluation()
            cand_fitness = calculate_fitness(cand_cost)

            # Greedy selection with strict improvement (f(v) < f(x))
            if cand_cost < source.cost:
                self._sources[i] = FoodSource(
                    position=v,
                    cost=cand_cost,
                    fitness=cand_fitness,
                    trial=0,
                )
                assert self._best_source is not None
                if cand_cost < self._best_source.cost:
                    self._best_source = self._sources[i].copy()
                improvements += 1

                if self._config.record_trace:
                    self._tracker.add_trace(
                        TraceEvent(
                            cycle=cycle,
                            phase="employed",
                            source_index=i,
                            partner_index=k,
                            dimension_index=j,
                            phi=phi,
                            candidate_cost=cand_cost,
                            accepted=True,
                            reason="improved",
                        )
                    )
            else:
                source.increment_trial()
                if self._config.record_trace:
                    self._tracker.add_trace(
                        TraceEvent(
                            cycle=cycle,
                            phase="employed",
                            source_index=i,
                            partner_index=k,
                            dimension_index=j,
                            phi=phi,
                            candidate_cost=cand_cost,
                            accepted=False,
                            reason="rejected_worse",
                        )
                    )

        return improvements

    def onlooker_bees_phase(self, cycle: int) -> int:
        """Execute the Onlooker Bees phase with exactly SN roulette selection attempts.

        Probabilities are calculated from the current population fitnesses at the start
        of the phase and remain fixed throughout all SN onlooker attempts.

        Returns
        -------
        int
            Number of strictly improving solutions accepted in this phase.
        """
        improvements = 0
        sn = len(self._sources)
        d = self._problem.dimension
        bounds = self._problem.bounds

        # Compute fixed selection probabilities for the onlooker phase with numerical scaling
        fitnesses = np.array([s.fitness for s in self._sources], dtype=np.float64)
        if not np.all(np.isfinite(fitnesses)) or not np.all(fitnesses > 0.0):
            raise ValueError("All population fitnesses must be finite and strictly positive.")

        max_fit = float(np.max(fitnesses))
        if not (math.isfinite(max_fit) and max_fit > 0.0):
            raise ValueError(f"Invalid maximum fitness in onlooker phase: {max_fit}")

        scaled_fitnesses = fitnesses / max_fit
        sum_scaled = float(np.sum(scaled_fitnesses))
        if not (math.isfinite(sum_scaled) and sum_scaled > 0.0):
            raise ValueError(f"Invalid sum of scaled fitnesses: {sum_scaled}")

        probabilities = scaled_fitnesses / sum_scaled
        if not (np.all(np.isfinite(probabilities)) and np.all(probabilities >= 0.0)):
            raise ValueError("Computed onlooker probabilities contain non-finite or negative values.")

        prob_sum = float(np.sum(probabilities))
        if not math.isclose(prob_sum, 1.0, rel_tol=1e-7, abs_tol=1e-7):
            raise ValueError(f"Onlooker probabilities do not sum to 1.0 (sum={prob_sum})")
        probabilities /= prob_sum

        # Exactly SN onlooker selection attempts
        for _ in range(sn):
            i = int(self._rng.choice(sn, p=probabilities))
            source = self._sources[i]
            k = self._select_partner(i)
            partner = self._sources[k]
            j = int(self._rng.integers(0, d))
            phi = float(self._rng.uniform(-1.0, 1.0))

            v = bounds.perturb_dimension(
                x_i=source.position,
                x_k=partner.position,
                dim_index=j,
                phi=phi,
            )
            self._tracker.record_proposal()

            # Constraint / feasibility check
            if not self._problem.is_valid(v):
                self._tracker.record_infeasible_rejection()
                source.increment_trial()
                if self._config.record_trace:
                    self._tracker.add_trace(
                        TraceEvent(
                            cycle=cycle,
                            phase="onlooker",
                            source_index=i,
                            partner_index=k,
                            dimension_index=j,
                            phi=phi,
                            candidate_cost=None,
                            accepted=False,
                            reason="rejected_infeasible",
                        )
                    )
                continue

            # Real objective function evaluation
            cand_cost = self._problem.evaluate(v)
            self._tracker.record_evaluation()
            cand_fitness = calculate_fitness(cand_cost)

            # Greedy selection with strict improvement
            if cand_cost < source.cost:
                self._sources[i] = FoodSource(
                    position=v,
                    cost=cand_cost,
                    fitness=cand_fitness,
                    trial=0,
                )
                assert self._best_source is not None
                if cand_cost < self._best_source.cost:
                    self._best_source = self._sources[i].copy()
                improvements += 1

                if self._config.record_trace:
                    self._tracker.add_trace(
                        TraceEvent(
                            cycle=cycle,
                            phase="onlooker",
                            source_index=i,
                            partner_index=k,
                            dimension_index=j,
                            phi=phi,
                            candidate_cost=cand_cost,
                            accepted=True,
                            reason="improved",
                        )
                    )
            else:
                source.increment_trial()
                if self._config.record_trace:
                    self._tracker.add_trace(
                        TraceEvent(
                            cycle=cycle,
                            phase="onlooker",
                            source_index=i,
                            partner_index=k,
                            dimension_index=j,
                            phi=phi,
                            candidate_cost=cand_cost,
                            accepted=False,
                            reason="rejected_worse",
                        )
                    )

        return improvements

    def scout_bees_phase(self, cycle: int) -> int:
        """Execute the Scout Bees phase.

        Identifies the single food source with highest trial counter.
        If trial >= limit, abandons it and re-initializes it with a newly sampled valid solution.
        As in canonical ABC, at most ONE food source is abandoned per cycle.

        Returns
        -------
        int
            1 if a source was abandoned and reset, 0 otherwise.
        """
        trials = [s.trial for s in self._sources]
        max_idx = int(np.argmax(trials))

        if self._sources[max_idx].trial >= self._limit:
            self._tracker.record_proposal()
            new_pos = self._problem.sample_valid(self._rng)
            self._validate_sampled_candidate(
                new_pos, context=f"scout reinitialization of food source {max_idx}"
            )
            new_cost = self._problem.evaluate(new_pos)
            self._tracker.record_evaluation()
            new_fitness = calculate_fitness(new_cost)

            self._sources[max_idx] = FoodSource(
                position=new_pos,
                cost=new_cost,
                fitness=new_fitness,
                trial=0,
            )
            self._tracker.record_scout_reset()

            assert self._best_source is not None
            if new_cost < self._best_source.cost:
                self._best_source = self._sources[max_idx].copy()

            if self._config.record_trace:
                self._tracker.add_trace(
                    TraceEvent(
                        cycle=cycle,
                        phase="scout",
                        source_index=max_idx,
                        partner_index=None,
                        dimension_index=None,
                        phi=None,
                        candidate_cost=new_cost,
                        accepted=True,
                        reason="scout_reset",
                    )
                )
            return 1

        return 0

    def optimize(self) -> ABCOutput:
        """Run the complete sequential ABC optimization algorithm.

        Returns
        -------
        ABCOutput
            Structured output containing historical best solution, cycle history, and metrics.
        """
        start_time = time.perf_counter()

        self.initialize_population()

        for cycle in range(1, self._config.max_cycles + 1):
            emp_improvements = self.employed_bees_phase(cycle)
            onl_improvements = self.onlooker_bees_phase(cycle)
            scout_resets = self.scout_bees_phase(cycle)

            assert self._best_source is not None
            mean_cost = compute_stable_mean([s.cost for s in self._sources])
            pop_snapshot = (
                tuple(s.copy() for s in self._sources)
                if self._config.record_population
                else None
            )

            self._tracker.add_cycle(
                CycleRecord(
                    cycle=cycle,
                    best_cost=self._best_source.cost,
                    best_position=np.copy(self._best_source.position),
                    mean_population_cost=mean_cost,
                    improvements_count=emp_improvements + onl_improvements,
                    scout_resets=scout_resets,
                    population=pop_snapshot,
                )
            )

        elapsed = time.perf_counter() - start_time
        assert self._best_source is not None

        return ABCOutput(
            best_source=self._best_source.copy(),
            history=tuple(self._tracker.history),
            total_evaluations=self._tracker.nfe,
            total_proposals=self._tracker.total_proposals,
            rejected_infeasible_proposals=self._tracker.rejected_infeasible,
            total_scout_resets=self._tracker.total_scout_resets,
            execution_time_seconds=elapsed,
            trace=tuple(self._tracker.trace),
        )
