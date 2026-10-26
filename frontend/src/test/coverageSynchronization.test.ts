import { describe, expect, it } from 'vitest'
import { buildCanonicalCoverageKey } from '../renderer/coverageKey'
import type { CameraPose, CameraProfile, CoverageEvaluationResponse, Scenario } from '../types/api'

describe('Coverage Cache Identity & Synchronization Tests (TAREA 07.1)', () => {
  const baseScenario: Scenario = {
    xmin: 0,
    xmax: 10,
    ymin: 0,
    ymax: 10,
    grid_resolution: 1.0,
    walls: [],
    obstacles: [],
    risk_zones: [],
  }

  const baseProfile: CameraProfile = {
    Rmin: 0,
    Rmax: 10,
    FOV: 2 * (Math.atan2(0.5, 2.5) - 0.10025),
    p0: 1,
    beta_d: 0.5,
    beta_theta: 0.5,
  }

  it('1. DEFECTO ALTO: Cache identity differentiates close camera orientations without rounding collisions', () => {
    // Technical Lead Audit Case:
    // Room 10x10m, Camera at (5, 5)
    // Orientation A: theta = 0.1001 rad
    // Orientation B: theta = 0.1004 rad
    // At cell (7.5, 5.5), Config A has prob 0, while Config B has prob ~0.588.
    const camerasA: CameraPose[] = [{ x: 5.0, y: 5.0, theta: 0.1001 }]
    const camerasB: CameraPose[] = [{ x: 5.0, y: 5.0, theta: 0.1004 }]

    const keyA = buildCanonicalCoverageKey(baseScenario, baseProfile, 1.0, 0.8, camerasA)
    const keyB = buildCanonicalCoverageKey(baseScenario, baseProfile, 1.0, 0.8, camerasB)

    // Must be completely distinct strings without lossy quantization
    expect(keyA).not.toBe(keyB)
    expect(keyA).toContain('0.1001')
    expect(keyB).toContain('0.1004')

    // Storing A in cache must not hit for B
    const cache = new Map<string, CoverageEvaluationResponse>()
    const mockCoverageA = { total_nodes: 100, objective_cost: 0.8 } as CoverageEvaluationResponse
    cache.set(keyA, mockCoverageA)

    expect(cache.has(keyA)).toBe(true)
    expect(cache.has(keyB)).toBe(false)
    expect(cache.get(keyB)).toBeUndefined()
  })

  it('2. Cache identity differentiates positions with sub-centimeter shifts (< 0.01 m)', () => {
    const camerasA: CameraPose[] = [{ x: 5.001, y: 5.0, theta: 1.57 }]
    const camerasB: CameraPose[] = [{ x: 5.009, y: 5.0, theta: 1.57 }]

    const keyA = buildCanonicalCoverageKey(baseScenario, baseProfile, 1.0, 0.8, camerasA)
    const keyB = buildCanonicalCoverageKey(baseScenario, baseProfile, 1.0, 0.8, camerasB)

    expect(keyA).not.toBe(keyB)
    expect(keyA).toContain('5.001')
    expect(keyB).toContain('5.009')
  })

  it('3. Cache identity incorporates full geometry including interior walls, obstacles, and risk zones', () => {
    const cameras: CameraPose[] = [{ x: 5.0, y: 5.0, theta: 0.0 }]

    const scenarioWithWall: Scenario = {
      ...baseScenario,
      walls: [{ start: { x: 2, y: 5 }, end: { x: 8, y: 5 }, is_opaque: true }],
    }

    const keyEmpty = buildCanonicalCoverageKey(baseScenario, baseProfile, 1.0, 0.8, cameras)
    const keyWall = buildCanonicalCoverageKey(scenarioWithWall, baseProfile, 1.0, 0.8, cameras)

    expect(keyEmpty).not.toBe(keyWall)
    expect(keyWall).toContain('"is_opaque":true')
  })

  it('4. DEFECTO MEDIO: Monotonic request ID correctly discards out-of-order asynchronous responses', () => {
    // Simulate App state tracking
    let latestRequestId = 0
    let activeCoverage: CoverageEvaluationResponse | null = null
    let activeKey = ''
    let isLoading = false
    const cache = new Map<string, CoverageEvaluationResponse>()

    // Simulate initiating Request 1 (e.g. user selects Cycle 1)
    const key1 = 'key_cycle_1'
    const reqId1 = ++latestRequestId
    isLoading = true

    // User immediately clicks Cycle 2 while Request 1 is still in-flight
    const key2 = 'key_cycle_2'
    const reqId2 = ++latestRequestId
    isLoading = true

    // Suppose Request 2 finishes FIRST (network latency variance)
    const result2 = { total_nodes: 400, objective_cost: 0.35 } as CoverageEvaluationResponse
    cache.set(key2, result2)
    if (reqId2 === latestRequestId) {
      activeCoverage = result2
      activeKey = key2
      isLoading = false
    }

    expect(activeCoverage).toBe(result2)
    expect(activeKey).toBe(key2)
    expect(isLoading).toBe(false)

    // Now Request 1 arrives LATER (out-of-order)
    const result1 = { total_nodes: 400, objective_cost: 0.72 } as CoverageEvaluationResponse
    cache.set(key1, result1) // Cached for future navigation!

    if (reqId1 === latestRequestId) {
      activeCoverage = result1
      activeKey = key1
      isLoading = false
    }

    // Active coverage MUST NOT be overwritten by the stale Request 1
    expect(activeCoverage).toBe(result2)
    expect(activeKey).toBe(key2)
    expect(isLoading).toBe(false)

    // Result 1 is still preserved in cache for instant recall
    expect(cache.get(key1)).toBe(result1)
  })

  it('5. Switching between historical best and individual food source updates configuration key deterministically', () => {
    const bestPoses: CameraPose[] = [
      { x: 3.0, y: 3.0, theta: 0.5 },
      { x: 7.0, y: 7.0, theta: -0.5 },
    ]
    const individualPoses: CameraPose[] = [
      { x: 2.0, y: 4.0, theta: 1.0 },
      { x: 8.0, y: 6.0, theta: -1.0 },
    ]

    const keyBest = buildCanonicalCoverageKey(baseScenario, baseProfile, 1.0, 0.8, bestPoses)
    const keyInd = buildCanonicalCoverageKey(baseScenario, baseProfile, 1.0, 0.8, individualPoses)

    expect(keyBest).not.toBe(keyInd)
  })
})
