import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '../services/api'
import type { OptimizationRequest } from '../types/api'

describe('API Service Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('3. loads scenarios from backend API successfully', async () => {
    const mockCatalog = {
      scenarios: [
        {
          id: 'partitioned_office',
          name: 'Partitioned Office',
          description: 'Office with walls and server room',
          scenario: { xmax: 24, ymax: 16 },
          recommended_profile: { Rmin: 0.2, Rmax: 11, FOV: 1.57, p0: 1, beta_d: 0.4, beta_theta: 0.5 },
          recommended_config: { K: 3, SN: 10, max_cycles: 20, lambda_def: 1, Tcrit: 0.8, record_population: true },
        },
      ],
    }

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockCatalog,
    } as Response)

    const res = await api.getScenarios()
    expect(res.scenarios).toHaveLength(1)
    expect(res.scenarios[0].id).toBe('partitioned_office')
  })

  it('4. serializes optimization request with exact expected schema structure', async () => {
    let capturedBody = ''
    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(async (_url, init) => {
      capturedBody = init?.body as string
      return {
        ok: true,
        status: 200,
        json: async () => ({ status: 'ok' }),
      } as Response
    })

    const payload: OptimizationRequest = {
      scenario: { xmin: 0, xmax: 24, ymin: 0, ymax: 16, grid_resolution: 1.0 },
      profile: { Rmin: 0.2, Rmax: 11.0, FOV: Math.PI / 2, p0: 1.0, beta_d: 0.4, beta_theta: 0.5 },
      config: { K: 3, SN: 10, max_cycles: 15, limit: 45, seed: 42, lambda_def: 1.0, Tcrit: 0.8, record_population: true },
    }

    await api.runOptimization(payload)
    expect(capturedBody).toBeTruthy()

    const parsed = JSON.parse(capturedBody)
    expect(parsed.scenario.xmax).toBe(24)
    expect(parsed.config.K).toBe(3)
    expect(parsed.config.SN).toBe(10)
    expect(parsed.config.seed).toBe(42)
    expect(parsed.config.record_population).toBe(true)
  })

  it('10. handles HTTP 409 concurrency conflict with clear sequential message', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 409,
      statusText: 'Conflict',
      json: async () => ({ detail: 'Another optimization is currently running.' }),
    } as Response)

    await expect(api.runOptimization({} as OptimizationRequest)).rejects.toThrowError(
      /El motor ABC es estrictamente secuencial/
    )
  })

  it('10b. handles HTTP 422 validation errors with parsed detail fields', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      json: async () => ({
        detail: [
          { loc: ['body', 'config', 'seed'], msg: 'Input should be greater than or equal to 0', type: 'greater_than_equal' },
        ],
      }),
    } as Response)

    try {
      await api.runOptimization({} as OptimizationRequest)
      expect.unreachable()
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError)
      const apiErr = err as ApiError
      expect(apiErr.statusCode).toBe(422)
      expect(apiErr.message).toContain('config.seed')
    }
  })

  it('10c. handles server disconnected / network failure gracefully', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new TypeError('Failed to fetch'))

    try {
      await api.getHealth()
      expect.unreachable()
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError)
      const apiErr = err as ApiError
      expect(apiErr.statusCode).toBe(0)
      expect(apiErr.message).toContain('No se pudo conectar con el servidor backend')
    }
  })

  it('11. serializes coverage evaluation request and receives authentic response', async () => {
    let capturedBody = ''
    const mockCoverageResponse = {
      cell_width: 1.0,
      cell_height: 1.0,
      total_nodes: 2,
      nodes: [
        { x: 1.0, y: 1.0, probability: 0.95, binary_covered: true, risk_weight: 1.0 },
        { x: 2.0, y: 1.0, probability: 0.0, binary_covered: false, risk_weight: 1.0 },
      ],
      metrics: {
        num_eval_points: 2,
        num_covered_points: 1,
        geometric_coverage_ratio: 0.5,
        geometric_coverage_percent: 50.0,
        mean_probabilistic_coverage: 0.475,
        risk_weighted_coverage: 0.475,
        num_critical_points: 0,
        critical_deficit: 0.4,
      },
      objective_cost: 0.525,
      is_feasible: true,
    }

    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(async (_url, init) => {
      capturedBody = init?.body as string
      return {
        ok: true,
        status: 200,
        json: async () => mockCoverageResponse,
      } as Response
    })

    const payload = {
      scenario: { xmin: 0, xmax: 10, ymin: 0, ymax: 10, grid_resolution: 1.0 },
      profile: { Rmin: 0.2, Rmax: 10.0, FOV: Math.PI / 2, p0: 1.0, beta_d: 0.4, beta_theta: 0.5 },
      lambda_def: 1.0,
      Tcrit: 0.8,
      cameras: [{ x: 1.0, y: 1.0, theta: 0.0 }],
    }

    const res = await api.evaluateCoverage(payload)
    expect(capturedBody).toBeTruthy()
    const parsed = JSON.parse(capturedBody)
    expect(parsed.cameras).toHaveLength(1)
    expect(parsed.lambda_def).toBe(1.0)
    expect(parsed.Tcrit).toBe(0.8)
    expect(res.total_nodes).toBe(2)
    expect(res.nodes[0].probability).toBe(0.95)
    expect(res.nodes[0].binary_covered).toBe(true)
    expect(res.metrics.mean_probabilistic_coverage).toBe(0.475)
    expect(res.objective_cost).toBe(0.525)
  })

  it('12. handles coverage HTTP 400 validation error cleanly', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: async () => ({ detail: 'Camera 0 position (100.0, 100.0) is outside floorplan bounds' }),
    } as Response)

    const payload = {
      scenario: { xmin: 0, xmax: 10, ymin: 0, ymax: 10, grid_resolution: 1.0 },
      profile: { Rmin: 0.2, Rmax: 10.0, FOV: Math.PI / 2, p0: 1.0, beta_d: 0.4, beta_theta: 0.5 },
      lambda_def: 1.0,
      Tcrit: 0.8,
      cameras: [{ x: 100.0, y: 100.0, theta: 0.0 }],
    }

    await expect(api.evaluateCoverage(payload)).rejects.toThrowError(
      /Camera 0 position/
    )
  })
})

