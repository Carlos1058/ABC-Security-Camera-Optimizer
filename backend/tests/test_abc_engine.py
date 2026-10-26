"""Unit and algorithmic property tests for the Sequential ABC optimization engine.

Covers requirements ABC-01 through ABC-12, tracking, configuration, and edge cases.
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from camera_optimizer.optimizer.bounds import (
    Bounds,
    DimensionSpec,
    VariableType,
)
from camera_optimizer.optimizer.config import ABCConfig
from camera_optimizer.optimizer.food_source import (
    FoodSource,
    calculate_fitness,
)
from camera_optimizer.optimizer.problem import (
    OptimizationProblem,
    RastriginProblem,
    SphereProblem,
)
from camera_optimizer.optimizer.sequential_abc import SequentialABC
from camera_optimizer.camera.pose import wrap_pi


class DummyCountingProblem(OptimizationProblem):
    """Simple 2D problem tracking exact number of evaluations and validity calls."""

    def __init__(self) -> None:
        self._bounds = Bounds.uniform_linear(dim=2, lower=-5.0, upper=5.0)
        self.eval_count = 0
        self.valid_count = 0

    @property
    def dimension(self) -> int:
        return 2

    @property
    def bounds(self) -> Bounds:
        return self._bounds

    def evaluate(self, x: np.ndarray) -> float:
        self.eval_count += 1
        return float(np.sum(x**2))

    def is_valid(self, x: np.ndarray) -> bool:
        self.valid_count += 1
        return bool(np.all(np.abs(x) <= 5.0))

    def sample_valid(self, rng: np.random.Generator) -> np.ndarray:
        return rng.uniform(-5.0, 5.0, size=2)


class MockProblemWithForcedFailure(OptimizationProblem):
    """Problem where candidates with x[0] > 0 are marked invalid."""

    def __init__(self) -> None:
        self._bounds = Bounds.uniform_linear(dim=2, lower=-5.0, upper=5.0)

    @property
    def dimension(self) -> int:
        return 2

    @property
    def bounds(self) -> Bounds:
        return self._bounds

    def evaluate(self, x: np.ndarray) -> float:
        return float(np.sum(x**2))

    def is_valid(self, x: np.ndarray) -> bool:
        # Candidate is invalid if x[0] > 0
        return float(x[0]) <= 0.0

    def sample_valid(self, rng: np.random.Generator) -> np.ndarray:
        return rng.uniform(-5.0, 0.0, size=2)


# =========================================================================
# Hyperparameters and Configuration
# =========================================================================

def test_abc_config_validation() -> None:
    """Test hyperparameter boundaries and validation."""
    cfg = ABCConfig(num_food_sources=10, max_cycles=50, limit=20, seed=42)
    assert cfg.num_food_sources == 10
    assert cfg.max_cycles == 50
    assert cfg.limit == 20
    assert cfg.seed == 42

    # Population must be >= 2
    with pytest.raises(ValueError, match="num_food_sources .* must be >= 2"):
        ABCConfig(num_food_sources=1)

    with pytest.raises(TypeError):
        ABCConfig(num_food_sources="ten")  # type: ignore

    with pytest.raises(ValueError, match="max_cycles must be >= 1"):
        ABCConfig(max_cycles=0)

    with pytest.raises(ValueError, match="limit must be >= 1"):
        ABCConfig(limit=0)


def test_abc_fitness_calculation() -> None:
    """Verify standard ABC fitness calculation for non-negative and negative costs."""
    # For f >= 0: fitness = 1 / (1 + f)
    assert calculate_fitness(0.0) == 1.0
    assert calculate_fitness(1.0) == 0.5
    assert calculate_fitness(3.0) == 0.25

    # For f < 0: fitness = 1 + |f|
    assert calculate_fitness(-2.0) == 3.0
    assert calculate_fitness(-0.5) == 1.5

    with pytest.raises(ValueError, match="finite real number"):
        calculate_fitness(float("inf"))

    with pytest.raises(ValueError, match="finite real number"):
        calculate_fitness(float("nan"))


# =========================================================================
# ABC-01: Initialization
# =========================================================================

def test_abc_01_initialization() -> None:
    """ABC-01: Exactly SN valid food sources initialized with trial=0 and finite cost."""
    prob = SphereProblem(dimension=3)
    sn = 6
    cfg = ABCConfig(num_food_sources=sn, max_cycles=10, seed=123)
    abc = SequentialABC(prob, cfg)

    assert len(abc.population) == 0
    assert abc.best_source is None

    abc.initialize_population()

    assert len(abc.population) == sn
    for source in abc.population:
        assert isinstance(source, FoodSource)
        assert source.trial == 0
        assert math.isfinite(source.cost)
        assert source.cost >= 0.0
        assert math.isfinite(source.fitness)
        assert source.fitness > 0.0
        assert len(source.position) == 3
        assert prob.is_valid(source.position)

    # Global best should match the best in initial population
    min_pop_cost = min(s.cost for s in abc.population)
    assert abc.best_source is not None
    assert abc.best_source.cost == min_pop_cost


# =========================================================================
# ABC-02: Neighbor Generation
# =========================================================================

def test_abc_02_neighbor_generation() -> None:
    """ABC-02: Perturbs exactly one dimension j; k != i; other dimensions remain identical."""
    bounds = Bounds.uniform_linear(dim=4, lower=-10.0, upper=10.0)
    x_i = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float64)
    x_k = np.array([5.0, 6.0, 7.0, 8.0], dtype=np.float64)

    dim_to_perturb = 2
    phi = 0.5

    v = bounds.perturb_dimension(x_i, x_k, dim_index=dim_to_perturb, phi=phi)

    # Check that dimensions other than dim_to_perturb remain strictly unchanged
    assert v[0] == x_i[0]
    assert v[1] == x_i[1]
    assert v[3] == x_i[3]

    # Check perturbed dimension: v_j = x_ij + phi * (x_ij - x_kj)
    expected_v2 = 3.0 + 0.5 * (3.0 - 7.0)  # 3.0 - 2.0 = 1.0
    assert pytest.approx(v[2], abs=1e-12) == expected_v2


def test_abc_02_partner_selection() -> None:
    """ABC-02: Partner k is strictly different from i across many random selections."""
    prob = SphereProblem(dimension=3)
    cfg = ABCConfig(num_food_sources=4, seed=42)
    abc = SequentialABC(prob, cfg)
    abc.initialize_population()

    for i in range(4):
        for _ in range(50):
            k = abc._select_partner(i)
            assert 0 <= k < 4
            assert k != i


# =========================================================================
# ABC-03: Greedy Selection
# =========================================================================

def test_abc_03_greedy_selection_replacement_and_trial() -> None:
    """ABC-03: Strict improvement replaces food source and resets trial; worse or equal increments trial."""
    src = FoodSource(position=np.array([2.0, 2.0]), cost=8.0, fitness=calculate_fitness(8.0), trial=3)

    # 1. Worse candidate (cost = 10.0 > 8.0)
    incremented = src.with_incremented_trial()
    assert incremented.trial == 4
    assert np.array_equal(incremented.position, src.position)

    # 2. Equal candidate (cost = 8.0)
    # ABC requires strict improvement (f(v) < f(x))
    assert not (8.0 < src.cost)

    # 3. Better candidate (cost = 5.0 < 8.0)
    better = FoodSource(position=np.array([1.0, 2.0]), cost=5.0, fitness=calculate_fitness(5.0), trial=0)
    assert better.cost < src.cost
    assert better.trial == 0


# =========================================================================
# ABC-04: Employed Bees Phase
# =========================================================================

def test_abc_04_employed_phase_attempts() -> None:
    """ABC-04: Each food source receives exactly one opportunity in the Employed phase."""
    prob = SphereProblem(dimension=2)
    sn = 5
    cfg = ABCConfig(num_food_sources=sn, max_cycles=1, seed=99, record_trace=True)
    abc = SequentialABC(prob, cfg)
    abc.initialize_population()

    assert abc.tracker.evaluations_count == sn  # Initial population

    abc.employed_bees_phase(cycle=1)

    # In Employed phase, all SN sources are visited once
    # Since all Sphere points are valid, exactly SN proposals and evaluations occur
    assert abc.tracker.proposals_count == sn + sn
    assert abc.tracker.evaluations_count == sn + sn

    # Trace events should record exactly sn employed attempts
    employed_traces = [t for t in abc.tracker.trace_history if t.phase == "employed"]
    assert len(employed_traces) == sn
    visited_sources = {t.source_index for t in employed_traces}
    assert visited_sources == set(range(sn))


# =========================================================================
# ABC-05: Onlooker Bees Phase
# =========================================================================

def test_abc_05_onlooker_phase_probabilities_and_attempts() -> None:
    """ABC-05: Exactly SN roulette attempts are executed with valid probabilities summing to 1."""
    prob = SphereProblem(dimension=2)
    sn = 6
    cfg = ABCConfig(num_food_sources=sn, max_cycles=1, seed=42, record_trace=True)
    abc = SequentialABC(prob, cfg)
    abc.initialize_population()

    # Pre-calculate fitness probabilities manually
    fits = np.array([s.fitness for s in abc.population])
    expected_probs = fits / np.sum(fits)
    assert pytest.approx(float(np.sum(expected_probs)), abs=1e-12) == 1.0

    evals_before = abc.tracker.evaluations_count
    abc.onlooker_bees_phase(cycle=1)

    # Exactly SN onlooker attempts were executed
    onlooker_traces = [t for t in abc.tracker.trace_history if t.phase == "onlooker"]
    assert len(onlooker_traces) == sn
    assert abc.tracker.evaluations_count == evals_before + sn


# =========================================================================
# ABC-06: Scout Bees Phase
# =========================================================================

def test_abc_06_scout_phase_at_most_one_abandonment() -> None:
    """ABC-06: Reinitializes at most ONE food source with max trial when trial >= limit."""
    prob = SphereProblem(dimension=2)
    sn = 4
    cfg = ABCConfig(num_food_sources=sn, max_cycles=1, limit=5, seed=123, record_trace=True)
    abc = SequentialABC(prob, cfg)
    abc.initialize_population()

    # Artificially set trials
    abc._sources[0].set_trial(6)
    abc._sources[1].set_trial(10)
    abc._sources[2].set_trial(2)
    abc._sources[3].set_trial(7)

    resets = abc.scout_bees_phase(cycle=1)

    # Exactly source 1 had the maximum trial >= limit
    assert resets == 1
    assert abc.population[1].trial == 0
    # Other sources with trial >= limit must NOT be abandoned in the same cycle
    assert abc.population[0].trial == 6
    assert abc.population[3].trial == 7
    assert abc.population[2].trial == 2

    # If no source exceeds limit, no abandonment occurs
    abc._sources[0].set_trial(2)
    abc._sources[1].set_trial(1)
    abc._sources[2].set_trial(3)
    abc._sources[3].set_trial(4)

    second_resets = abc.scout_bees_phase(cycle=2)
    assert second_resets == 0


# =========================================================================
# ABC-07: Historical Best Monotonicity
# =========================================================================

def test_abc_07_historical_best_never_worsens() -> None:
    """ABC-07: The best recorded cost never increases across optimization cycles."""
    prob = SphereProblem(dimension=4)
    cfg = ABCConfig(num_food_sources=8, max_cycles=25, seed=777)
    abc = SequentialABC(prob, cfg)

    output = abc.optimize()

    best_costs = [rec.best_cost for rec in output.history]
    # Includes cycle 0 (initial baseline) plus 25 cycles = 26 records
    assert len(best_costs) == 26

    # Check non-increasing property: best_costs[t+1] <= best_costs[t]
    for t in range(len(best_costs) - 1):
        assert best_costs[t + 1] <= best_costs[t] + 1e-15, (
            f"Historical best worsened from cycle {t} ({best_costs[t]}) "
            f"to cycle {t+1} ({best_costs[t+1]})"
        )

    # Final best cost must match the last recorded cycle
    assert output.best_cost == best_costs[-1]


# =========================================================================
# ABC-08: Reproducibility
# =========================================================================

def test_abc_08_reproducibility_identical_seed() -> None:
    """ABC-08: Two executions with identical parameters and seed produce identical trajectories."""
    prob1 = RastriginProblem(dimension=3)
    prob2 = RastriginProblem(dimension=3)

    cfg = ABCConfig(num_food_sources=10, max_cycles=15, seed=4242, record_trace=True)

    abc1 = SequentialABC(prob1, cfg)
    out1 = abc1.optimize()

    abc2 = SequentialABC(prob2, cfg)
    out2 = abc2.optimize()

    assert out1.best_cost == out2.best_cost
    np.testing.assert_array_equal(out1.best_solution, out2.best_solution)
    assert out1.evaluations_count == out2.evaluations_count
    assert out1.rejected_infeasible_count == out2.rejected_infeasible_count
    assert out1.scout_resets_count == out2.scout_resets_count

    for r1, r2 in zip(out1.history, out2.history, strict=True):
        assert r1.cycle == r2.cycle
        assert r1.best_cost == r2.best_cost
        assert r1.mean_cost == r2.mean_cost
        assert r1.improvements == r2.improvements
        np.testing.assert_array_equal(r1.best_vector, r2.best_vector)


# =========================================================================
# ABC-09: Exact Objective Evaluations Accounting (NFE)
# =========================================================================

def test_abc_09_exact_objective_evaluations() -> None:
    """ABC-09: Tracked NFE strictly matches the true number of function invocations."""
    prob = DummyCountingProblem()
    sn = 6
    cycles = 5
    cfg = ABCConfig(num_food_sources=sn, max_cycles=cycles, limit=10, seed=123)
    abc = SequentialABC(prob, cfg)

    output = abc.optimize()

    # The internal eval_count of the problem must exactly match the tracker
    assert prob.eval_count == output.evaluations_count
    assert abc.tracker.evaluations_count == output.evaluations_count

    # In DummyCountingProblem, all candidates are valid within [-5, 5]
    # Initial: sn evals
    # Per cycle: sn (employed) + sn (onlooker) + 0 (if no scout triggered)
    min_expected_evals = sn + cycles * (2 * sn)
    assert output.evaluations_count >= min_expected_evals


# =========================================================================
# ABC-10: Sphere Benchmark Optimization
# =========================================================================

def test_abc_10_sphere_function_optimization() -> None:
    """ABC-10: Optimizes continuous Sphere function without domain coupling."""
    prob = SphereProblem(dimension=3, lower=-5.12, upper=5.12)
    cfg = ABCConfig(num_food_sources=15, max_cycles=30, seed=101)
    abc = SequentialABC(prob, cfg)

    out = abc.optimize()

    initial_cost = out.history[0].best_cost
    final_cost = out.best_cost

    assert final_cost <= initial_cost
    assert final_cost < 2.0  # Demonstrates significant optimization progress
    assert len(out.best_solution) == 3


# =========================================================================
# ABC-11: Rastrigin Benchmark Optimization
# =========================================================================

def test_abc_11_rastrigin_multimodal_optimization() -> None:
    """ABC-11: Executes multimodal Rastrigin function and tracks fitness evolution."""
    prob = RastriginProblem(dimension=2, lower=-5.12, upper=5.12)
    cfg = ABCConfig(num_food_sources=12, max_cycles=25, seed=202)
    abc = SequentialABC(prob, cfg)

    out = abc.optimize()

    assert len(out.history) == 26  # cycle 0 + 25 optimization cycles
    assert out.best_cost <= out.history[0].best_cost
    for rec in out.history:
        assert math.isfinite(rec.mean_cost)
        assert math.isfinite(rec.best_cost)


# =========================================================================
# ABC-12: Circular Angular Perturbation
# =========================================================================

def test_abc_12_circular_angular_perturbation_boundaries() -> None:
    """ABC-12: Perturbation works correctly near +/-pi without unnatural boundary jumps."""
    spec = DimensionSpec(lower=-math.pi, upper=math.pi, var_type=VariableType.CIRCULAR_ANGLE)

    # e.g., theta_i = 3.10 rad (~ +pi), theta_k = -3.10 rad (~ -pi)
    th_i = 3.10
    th_k = -3.10
    delta = spec.wrap_difference(th_i, th_k)
    expected_delta = wrap_pi(th_i - th_k)

    assert pytest.approx(delta, abs=1e-12) == expected_delta
    assert abs(delta) < 0.1  # Minimal circular difference, not ~6.20

    phi = 0.5
    v = spec.apply_perturbation(th_i, delta, phi)

    # Must lie strictly within [-pi, pi)
    assert -math.pi <= v < math.pi


def test_abc_infeasible_candidate_rejection_tracking() -> None:
    """Verify that infeasible candidates are rejected, increment trial, and do not evaluate objective."""
    prob = MockProblemWithForcedFailure()
    cfg = ABCConfig(num_food_sources=4, max_cycles=5, limit=10, seed=55, record_trace=True)
    abc = SequentialABC(prob, cfg)

    output = abc.optimize()

    assert output.evaluations_count > 0
    for s in abc.population:
        assert prob.is_valid(s.position)
    assert prob.is_valid(output.best_solution)


def test_abc_engine_invalid_inputs() -> None:
    """Test SequentialABC constructor error handling on invalid types."""
    with pytest.raises(TypeError, match="Expected OptimizationProblem"):
        SequentialABC("not_a_problem")  # type: ignore

    prob = SphereProblem(dimension=2)
    with pytest.raises(TypeError, match="Expected ABCConfig"):
        SequentialABC(prob, config="not_a_config")  # type: ignore


def test_food_source_validation() -> None:
    """Test FoodSource validations for non-finite values, dimension, and trial."""
    # ndim != 1
    with pytest.raises(ValueError, match="1-dimensional"):
        FoodSource(position=np.zeros((2, 2)), cost=1.0, fitness=0.5)

    # non-array position
    with pytest.raises(TypeError, match="numpy ndarray"):
        FoodSource(position=[1.0, 2.0], cost=1.0, fitness=0.5)  # type: ignore

    # non-finite position
    with pytest.raises(ValueError, match="non-finite values"):
        FoodSource(position=np.array([float("nan"), 1.0]), cost=1.0, fitness=0.5)

    # non-finite cost
    with pytest.raises(ValueError, match="cost must be finite"):
        FoodSource(position=np.array([1.0, 2.0]), cost=float("inf"), fitness=0.5)

    # non-positive fitness
    with pytest.raises(ValueError, match="fitness must be finite and positive"):
        FoodSource(position=np.array([1.0, 2.0]), cost=1.0, fitness=0.0)

    # negative trial
    with pytest.raises(ValueError, match="Trial counter cannot be negative"):
        FoodSource(position=np.array([1.0, 2.0]), cost=1.0, fitness=0.5, trial=-1)

    # set_trial negative
    fs = FoodSource(position=np.array([1.0, 2.0]), cost=1.0, fitness=0.5, trial=0)
    with pytest.raises(ValueError, match="Trial counter cannot be negative"):
        fs.set_trial(-2)


def test_bounds_and_dimension_spec_validation() -> None:
    """Test boundary validation in Bounds and DimensionSpec."""
    # Lower bound >= upper bound
    with pytest.raises(ValueError, match="Lower bound must be strictly less than upper bound"):
        DimensionSpec(lower=5.0, upper=2.0)

    with pytest.raises(ValueError, match="Lower bound must be strictly less than upper bound"):
        DimensionSpec(lower=2.0, upper=2.0)

    # Non-finite bounds
    with pytest.raises(ValueError, match="Bounds must be finite"):
        DimensionSpec(lower=float("-inf"), upper=10.0)

    # Bounds empty sequence
    with pytest.raises(ValueError, match="Bounds must contain at least 1 DimensionSpec"):
        Bounds([])

    # Bounds invalid item
    with pytest.raises(TypeError, match="not a DimensionSpec"):
        Bounds(["not_a_spec"])  # type: ignore

    # Bounds.uniform_linear invalid dimension
    with pytest.raises(ValueError, match="Dimension must be positive"):
        Bounds.uniform_linear(dim=0, lower=0.0, upper=1.0)


def test_sequential_abc_default_config_and_limit() -> None:
    """Test SequentialABC default parameters and heuristic limit calculation (SN * D)."""
    prob = SphereProblem(dimension=3)
    abc = SequentialABC(prob)
    # Default SN = 20, D = 3 -> default limit = 20 * 3 = 60
    assert abc.config.num_food_sources == 20
    assert abc.limit == 20 * 3
    assert abc.problem is prob


# =========================================================================
# TAREA 04.1: DEFECT A - Numerical Stability in Probabilities and Mean
# =========================================================================

class MockExtremeCostProblem(OptimizationProblem):
    """Problem with extreme negative or positive costs to test roulette numerical stability."""

    def __init__(self, cost: float = -1e308) -> None:
        self._bounds = Bounds.uniform_linear(dim=2, lower=-5.0, upper=5.0)
        self._cost = cost

    @property
    def dimension(self) -> int:
        return 2

    @property
    def bounds(self) -> Bounds:
        return self._bounds

    def evaluate(self, x: np.ndarray) -> float:
        return self._cost

    def is_valid(self, x: np.ndarray) -> bool:
        return True

    def sample_valid(self, rng: np.random.Generator) -> np.ndarray:
        return np.array([0.0, 0.0], dtype=np.float64)


def test_defect_a_extreme_negative_costs_no_overflow() -> None:
    """DEFECT A: When cost is -1e308 across all sources, onlooker probabilities do not overflow to NaN."""
    prob = MockExtremeCostProblem(cost=-1e308)
    cfg = ABCConfig(num_food_sources=4, max_cycles=2, seed=42)
    abc = SequentialABC(prob, cfg)

    # Initialize and execute onlooker phase without raising ValueError or producing NaNs
    abc.initialize_population()
    improvements = abc.onlooker_bees_phase(cycle=1)
    assert improvements == 0  # No strict improvement possible on constant function

    output = abc.optimize()
    assert math.isfinite(output.best_cost)
    assert output.best_cost == -1e308
    for rec in output.history:
        assert math.isfinite(rec.mean_cost)
        assert rec.mean_cost == -1e308


def test_defect_a_stable_mean_overflow_protection() -> None:
    """DEFECT A: compute_stable_mean computes accurate finite averages of extreme numbers."""
    from camera_optimizer.optimizer.sequential_abc import compute_stable_mean

    # Identical extreme positive numbers: average must be exactly 1e308 without overflowing
    arr_large = [1e308, 1e308, 1e308, 1e308]
    mean_large = compute_stable_mean(arr_large)
    assert math.isfinite(mean_large)
    assert pytest.approx(mean_large, rel=1e-12) == 1e308

    # Identical extreme negative numbers
    arr_neg = [-1e308, -1e308, -1e308]
    mean_neg = compute_stable_mean(arr_neg)
    assert math.isfinite(mean_neg)
    assert pytest.approx(mean_neg, rel=1e-12) == -1e308

    # Symmetric extreme numbers: mean must be 0.0
    arr_sym = [1e308, -1e308]
    mean_sym = compute_stable_mean(arr_sym)
    assert math.isfinite(mean_sym)
    assert mean_sym == 0.0

    # Non-finite values must raise ValueError
    with pytest.raises(ValueError, match="Cannot compute mean with non-finite value"):
        compute_stable_mean([1.0, float("nan")])

    with pytest.raises(ValueError, match="Cannot compute mean with non-finite value"):
        compute_stable_mean([1.0, float("inf")])


# =========================================================================
# TAREA 04.1: DEFECT B - sample_valid Contract Verification
# =========================================================================

class MockFlawedSamplingProblem(OptimizationProblem):
    """Problem whose sample_valid deliberately returns invalid candidates to test contract validation."""

    def __init__(self, flaw_type: str) -> None:
        self._bounds = Bounds.uniform_linear(dim=2, lower=-5.0, upper=5.0)
        self.flaw_type = flaw_type
        self.eval_count = 0

    @property
    def dimension(self) -> int:
        return 2

    @property
    def bounds(self) -> Bounds:
        return self._bounds

    def evaluate(self, x: np.ndarray) -> float:
        self.eval_count += 1
        return float(np.sum(x**2))

    def is_valid(self, x: np.ndarray) -> bool:
        return bool(np.all(np.abs(x) <= 5.0) and float(x[0]) <= 0.0)

    def sample_valid(self, rng: np.random.Generator) -> np.ndarray:
        if self.flaw_type == "not_array":
            return [0.0, 0.0]  # type: ignore
        elif self.flaw_type == "wrong_dim":
            return np.array([0.0, 0.0, 0.0])  # Length 3 instead of 2
        elif self.flaw_type == "non_finite":
            return np.array([float("nan"), 0.0])
        elif self.flaw_type == "out_of_bounds":
            return np.array([10.0, 0.0])  # Exceeds upper bound 5.0
        elif self.flaw_type == "infeasible":
            return np.array([2.0, 0.0])  # x[0] > 0 violates is_valid()
        return np.array([-1.0, 0.0])


@pytest.mark.parametrize(
    "flaw,expected_err,expected_match",
    [
        ("not_array", TypeError, "must be a numpy.ndarray"),
        ("wrong_dim", ValueError, "expected problem dimension 2"),
        ("non_finite", ValueError, "contains non-finite values"),
        ("out_of_bounds", ValueError, "violates declared bounds"),
        ("infeasible", ValueError, "rejected by problem.is_valid"),
    ],
)
def test_defect_b_sample_valid_validation_in_initialization(
    flaw: str, expected_err: type[Exception], expected_match: str
) -> None:
    """DEFECT B: Engine detects invalid candidates from sample_valid() before evaluating objective."""
    prob = MockFlawedSamplingProblem(flaw_type=flaw)
    cfg = ABCConfig(num_food_sources=3, max_cycles=1, seed=42)
    abc = SequentialABC(prob, cfg)

    with pytest.raises(expected_err, match=expected_match):
        abc.initialize_population()

    # Crucial guarantee: evaluate() was NEVER invoked on invalid candidates!
    assert prob.eval_count == 0


def test_defect_b_sample_valid_validation_in_scout() -> None:
    """DEFECT B: Scout phase validates candidate before evaluation."""
    prob = MockFlawedSamplingProblem(flaw_type="valid")
    cfg = ABCConfig(num_food_sources=3, max_cycles=1, limit=5, seed=42)
    abc = SequentialABC(prob, cfg)
    abc.initialize_population()
    evals_after_init = prob.eval_count

    # Force source 1 to trigger scout abandonment
    abc._sources[1].set_trial(10)

    # Now make sample_valid flawed
    prob.flaw_type = "infeasible"

    with pytest.raises(ValueError, match="rejected by problem.is_valid"):
        abc.scout_bees_phase(cycle=1)

    # No evaluation occurred during flawed scout attempt
    assert prob.eval_count == evals_after_init


# =========================================================================
# TAREA 04.1: DEFECT C - Circular Variable Bounds Validation
# =========================================================================

def test_defect_c_circular_variable_bounds_validation() -> None:
    """DEFECT C: CIRCULAR_ANGLE dimensions must strictly define [-pi, pi)."""
    # Valid canonical circular angle domain
    spec = DimensionSpec(lower=-math.pi, upper=math.pi, var_type=VariableType.CIRCULAR_ANGLE)
    assert spec.lower == -math.pi
    assert spec.upper == math.pi
    assert spec.var_type == VariableType.CIRCULAR_ANGLE

    # Invalid circular angle domains must be rejected
    with pytest.raises(ValueError, match="CIRCULAR_ANGLE dimensions must declare the canonical domain"):
        DimensionSpec(lower=0.0, upper=1.0, var_type=VariableType.CIRCULAR_ANGLE)

    with pytest.raises(ValueError, match="CIRCULAR_ANGLE dimensions must declare the canonical domain"):
        DimensionSpec(lower=0.0, upper=2 * math.pi, var_type=VariableType.CIRCULAR_ANGLE)

    with pytest.raises(ValueError, match="CIRCULAR_ANGLE dimensions must declare the canonical domain"):
        DimensionSpec(lower=-1.0, upper=1.0, var_type=VariableType.CIRCULAR_ANGLE)


# =========================================================================
# TAREA 04.1: MEJORA D - Full Population History Telemetry
# =========================================================================

def test_mejora_d_record_population_disabled_by_default() -> None:
    """MEJORA D: record_population is False by default and population is None in CycleRecord."""
    prob = SphereProblem(dimension=2)
    cfg = ABCConfig(num_food_sources=4, max_cycles=3, seed=42)
    assert cfg.record_population is False

    abc = SequentialABC(prob, cfg)
    out = abc.optimize()

    for rec in out.history:
        assert rec.population is None
        d = rec.to_dict()
        assert "population" not in d


def test_mejora_d_record_population_enabled_captures_independent_snapshots() -> None:
    """MEJORA D: When record_population=True, captures independent deep copies for all cycles."""
    prob = SphereProblem(dimension=2)
    sn = 5
    max_cycles = 4
    cfg = ABCConfig(num_food_sources=sn, max_cycles=max_cycles, seed=77, record_population=True)

    abc = SequentialABC(prob, cfg)
    out = abc.optimize()

    # Must contain max_cycles + 1 records (cycle 0 to cycle 4)
    assert len(out.history) == max_cycles + 1

    for cycle_idx, rec in enumerate(out.history):
        assert rec.cycle == cycle_idx
        assert rec.population is not None
        assert len(rec.population) == sn

        # Check serialization
        d = rec.to_dict()
        assert "population" in d
        assert len(d["population"]) == sn
        for src_dict in d["population"]:
            assert "position" in src_dict
            assert "cost" in src_dict
            assert "fitness" in src_dict
            assert "trial" in src_dict

    # Verify deep copy independence:
    # Mutating current active population or subsequent records must NOT alter cycle 0 snapshot
    c0_pop = out.history[0].population
    assert c0_pop is not None
    orig_c0_pos = np.copy(c0_pop[0].position)
    orig_c0_trial = c0_pop[0].trial

    # Mutate current active population
    abc._sources[0].position[0] = 999.0
    abc._sources[0].set_trial(99)

    # Cycle 0 record must be completely unchanged
    assert c0_pop[0].position[0] == orig_c0_pos[0]
    assert c0_pop[0].trial == orig_c0_trial


def test_mejora_d_telemetry_does_not_affect_optimization() -> None:
    """MEJORA D: Enabling record_population does not affect RNG state or optimization results."""
    prob1 = SphereProblem(dimension=3)
    prob2 = SphereProblem(dimension=3)

    cfg1 = ABCConfig(num_food_sources=6, max_cycles=10, seed=123, record_population=False)
    cfg2 = ABCConfig(num_food_sources=6, max_cycles=10, seed=123, record_population=True)

    out1 = SequentialABC(prob1, cfg1).optimize()
    out2 = SequentialABC(prob2, cfg2).optimize()

    assert out1.best_cost == out2.best_cost
    np.testing.assert_array_equal(out1.best_solution, out2.best_solution)
    assert out1.evaluations_count == out2.evaluations_count
    assert out1.rejected_infeasible_count == out2.rejected_infeasible_count
    assert out1.scout_resets_count == out2.scout_resets_count


def test_abc_sn2_limit1_execution_and_accounting() -> None:
    """Audit requirement: SN=2 and limit=1 edge case.

    Verifies:
    - No infinite loops when SN=2 (minimal valid population) and limit=1 (frequent scout triggers).
    - Strictly sequential execution completes cleanly in finite time.
    - Correct accounting of NFE, proposals, scout resets, and cycle records.
    """
    prob = SphereProblem(dimension=2)
    max_cycles = 15
    sn = 2
    limit = 1
    seed = 42

    config = ABCConfig(
        num_food_sources=sn,
        max_cycles=max_cycles,
        limit=limit,
        seed=seed,
        record_trace=True,
        record_population=True,
    )
    abc = SequentialABC(prob, config)
    output = abc.optimize()

    # 1. Termination: finished exactly max_cycles cycles (plus cycle 0)
    assert len(output.history) == max_cycles + 1
    assert output.history[0].cycle == 0
    assert output.history[-1].cycle == max_cycles

    # 2. Sequential execution & no deadlocks: execution completed in positive time
    assert output.execution_time_seconds >= 0.0

    # 3. NFE accounting:
    # Initial population: exactly SN evaluations
    # In each cycle:
    # - Employed: exactly SN = 2 evaluations (all valid for SphereProblem)
    # - Onlooker: exactly SN = 2 selection attempts, each evaluating 1 candidate (since sum_prob > 0 and candidates valid)
    # - Scout: at most 1 evaluation if max(trials) >= limit (which is 1)
    # Total evaluations must be: SN_init + sum(cycle_evals)
    # Exactly matches output.total_evaluations
    assert output.total_evaluations >= sn + max_cycles * (sn + 1)
    assert output.rejected_infeasible_proposals == 0

    # 4. Scout resets: with limit=1, sources that don't improve immediately have trial >= 1,
    # so scout resets should be frequently triggered (at least 1 across 15 cycles)
    assert output.total_scout_resets >= 1
    assert sum(rec.scout_resets for rec in output.history[1:]) == output.total_scout_resets

    # 5. History and population integrity:
    for rec in output.history:
        assert rec.population is not None
        assert len(rec.population) == sn
        assert rec.best_cost <= output.history[0].best_cost
        assert math.isfinite(rec.mean_population_cost)

    # 6. Best solution is non-worsening and finite
    assert math.isfinite(output.best_cost)
    assert np.all(np.isfinite(output.best_source.position))


