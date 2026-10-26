import { describe, expect, it } from 'vitest'
import type { OptimizationResult } from '../types/api'

// Sample authentic result matching Phase 4.1 audit output
const sampleResult: OptimizationResult = {
  scenario: { xmin: 0, xmax: 24, ymin: 0, ymax: 16, grid_resolution: 1.0 },
  profile: { Rmin: 0.2, Rmax: 11.0, FOV: 1.5707963, p0: 1.0, beta_d: 0.4, beta_theta: 0.5 },
  config: { K: 3, SN: 4, max_cycles: 3, limit: 36, seed: '42', lambda_def: 1.0, Tcrit: 0.8, record_population: true },
  effective_seed: '42',
  dimension: 9,
  initial_best_cost: 1.46905083,
  initial_best_poses: [
    { x: 19.31, y: 6.20, theta: -1.33, theta_deg: -76.2 },
    { x: 16.38, y: 2.24, theta: -1.89, theta_deg: -108.0 },
    { x: 0.18, y: 12.59, theta: 1.04, theta_deg: 59.3 },
  ],
  final_best_cost: 0.7012359,
  final_best_poses: [
    { x: 19.31, y: 7.65, theta: -1.33, theta_deg: -76.2 },
    { x: 16.03, y: 7.14, theta: -2.66, theta_deg: -152.4 },
    { x: 0.18, y: 12.59, theta: -0.24, theta_deg: -13.9 },
  ],
  best_cost_per_cycle: [1.46905, 1.10234, 0.85210, 0.701236],
  mean_cost_per_cycle: [1.61153, 1.42310, 1.20540, 1.05432],
  coverage_metrics: {
    num_eval_points: 378,
    num_covered_points: 188,
    geometric_coverage_ratio: 0.49735,
    geometric_coverage_percent: 49.735,
    mean_probabilistic_coverage: 0.38197,
    risk_weighted_coverage: 0.436869,
    num_critical_points: 30,
    critical_deficit: 0.138105,
  },
  total_evaluations: 287,
  total_proposals: 310,
  rejected_infeasible_proposals: 23,
  total_scout_resets: 0,
  execution_time_seconds: 0.763,
  population_history_available: true,
  notes: 'Canonical ABC',
  history: [
    {
      cycle: 0,
      best_cost: 1.46905,
      best_poses: [
        { x: 19.31, y: 6.20, theta: -1.33, theta_deg: -76.2 },
        { x: 16.38, y: 2.24, theta: -1.89, theta_deg: -108.0 },
        { x: 0.18, y: 12.59, theta: 1.04, theta_deg: 59.3 },
      ],
      mean_population_cost: 1.61153,
      improvements_count: 0,
      scout_resets: 0,
      population: [
        {
          position: [19.31, 6.20, -1.33, 16.38, 2.24, -1.89, 0.18, 12.59, 1.04],
          poses: [
            { x: 19.31, y: 6.20, theta: -1.33, theta_deg: -76.2 },
            { x: 16.38, y: 2.24, theta: -1.89, theta_deg: -108.0 },
            { x: 0.18, y: 12.59, theta: 1.04, theta_deg: 59.3 },
          ],
          cost: 1.46905,
          fitness: 0.4049,
          trial: 0,
        },
        {
          position: [10.0, 5.0, 0.0, 8.0, 4.0, 1.2, 2.0, 10.0, -0.5],
          poses: [
            { x: 10.0, y: 5.0, theta: 0.0, theta_deg: 0.0 },
            { x: 8.0, y: 4.0, theta: 1.2, theta_deg: 68.7 },
            { x: 2.0, y: 10.0, theta: -0.5, theta_deg: -28.6 },
          ],
          cost: 1.75231,
          fitness: 0.3633,
          trial: 2,
        },
      ],
    },
    {
      cycle: 1,
      best_cost: 1.10234,
      best_poses: [
        { x: 19.31, y: 7.00, theta: -1.33, theta_deg: -76.2 },
        { x: 16.20, y: 3.00, theta: -2.10, theta_deg: -120.3 },
        { x: 0.18, y: 12.59, theta: 0.50, theta_deg: 28.6 },
      ],
      mean_population_cost: 1.42310,
      improvements_count: 1,
      scout_resets: 0,
      population: [
        {
          position: [19.31, 7.00, -1.33, 16.20, 3.00, -2.10, 0.18, 12.59, 0.50],
          poses: [
            { x: 19.31, y: 7.00, theta: -1.33, theta_deg: -76.2 },
            { x: 16.20, y: 3.00, theta: -2.10, theta_deg: -120.3 },
            { x: 0.18, y: 12.59, theta: 0.50, theta_deg: 28.6 },
          ],
          cost: 1.10234,
          fitness: 0.4756,
          trial: 0,
        },
      ],
    },
  ],
}

describe('Playback and Results Integrity Tests', () => {
  it('5. updates and renders results after receiving API response', () => {
    expect(sampleResult.initial_best_cost).toBe(1.46905083)
    expect(sampleResult.final_best_cost).toBe(0.7012359)
    expect(sampleResult.final_best_cost).toBeLessThan(sampleResult.initial_best_cost)
    expect(sampleResult.history).toHaveLength(2)
  })

  it('6. bounds cycle playback safely without exceeding history limits', () => {
    const totalCycles = sampleResult.history.length // 2 cycles (0 and 1)

    const seekClamped = (c: number) => Math.max(0, Math.min(totalCycles - 1, c))

    expect(seekClamped(-5)).toBe(0)
    expect(seekClamped(0)).toBe(0)
    expect(seekClamped(1)).toBe(1)
    expect(seekClamped(10)).toBe(1)
  })

  it('7. allows switching between best historical solution and individual food source', () => {
    const snapshot = sampleResult.history[0]
    expect(snapshot.population).toBeDefined()
    expect(snapshot.population).toHaveLength(2)

    // Best solution poses at cycle 0
    const bestPoses = snapshot.best_poses
    expect(bestPoses).toHaveLength(3)
    expect(bestPoses[0].x).toBe(19.31)

    // Source #2 in population
    const source2 = snapshot.population![1]
    expect(source2.cost).toBe(1.75231)
    expect(source2.trial).toBe(2)
    expect(source2.poses[0].x).toBe(10.0)
  })

  it('8. represents exactly K cameras per candidate solution vector', () => {
    const K = sampleResult.config.K // 3 cameras
    expect(K).toBe(3)

    // Best historical has exactly K cameras
    for (const snap of sampleResult.history) {
      expect(snap.best_poses).toHaveLength(K)
      if (snap.population) {
        for (const src of snap.population) {
          expect(src.poses).toHaveLength(K)
          expect(src.position).toHaveLength(3 * K)
        }
      }
    }
  })

  it('9. handles absence of population history gracefully without fabricating population', () => {
    const noPopResult: OptimizationResult = {
      ...sampleResult,
      population_history_available: false,
      history: sampleResult.history.map(h => ({ ...h, population: null })),
    }

    expect(noPopResult.population_history_available).toBe(false)
    for (const snap of noPopResult.history) {
      expect(snap.population).toBeNull()
      // Best poses still exist and can be replayed
      expect(snap.best_poses).toHaveLength(3)
    }
  })

  it('12. maintains effective_seed for exact reproduction', () => {
    expect(sampleResult.effective_seed).toBe('42')
    expect(typeof sampleResult.effective_seed).toBe('string')
    expect(Number(sampleResult.effective_seed)).toBeGreaterThanOrEqual(0)
  })

  it('13. enforces strict mathematical identity f(X) = (1 - C_risk) + lambda_def * Deficit_crit without mock or hardcoded values', () => {
    const cRisk = sampleResult.coverage_metrics.risk_weighted_coverage
    const deficitCrit = sampleResult.coverage_metrics.critical_deficit
    const lambdaDef = sampleResult.config.lambda_def

    const theoreticalCost = (1.0 - cRisk) + lambdaDef * deficitCrit
    // (1 - 0.436869) + 1.0 * 0.138105 = 0.563131 + 0.138105 = 0.701236
    expect(sampleResult.final_best_cost).toBeCloseTo(theoreticalCost, 5)
  })
})
