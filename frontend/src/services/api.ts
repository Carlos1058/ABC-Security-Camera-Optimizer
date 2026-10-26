/**
 * API service for communicating with the FastAPI backend.
 * Consumes real endpoints with robust error handling for 400, 409, 422, and offline states.
 */

import type {
  CoverageEvaluationRequest,
  CoverageEvaluationResponse,
  HealthResponse,
  OptimizationRequest,
  OptimizationResult,
  PredefinedScenariosResponse,
  ValidationRequest,
  ValidationResponse,
} from '../types/api'

// Configurable base URL via environment variable
const getBaseUrl = (): string => {
  const envUrl = import.meta.env.VITE_API_BASE_URL
  if (envUrl) {
    return envUrl.endsWith('/') ? envUrl.slice(0, -1) : envUrl
  }
  // If running in development with Vite proxy, use relative /api/v1, otherwise direct to localhost:8000
  return '/api/v1'
}

export class ApiError extends Error {
  statusCode?: number
  details?: unknown

  constructor(message: string, statusCode?: number, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.statusCode = statusCode
    this.details = details
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const baseUrl = getBaseUrl()
  const url = `${baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`

  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(options.headers as Record<string, string>),
  }

  if (options.body && typeof options.body === 'string') {
    headers['Content-Type'] = 'application/json'
  }

  let response: Response
  try {
    response = await fetch(url, {
      ...options,
      headers,
    })
  } catch (err) {
    throw new ApiError(
      `No se pudo conectar con el servidor backend en ${url}. Verifique que el servicio FastAPI esté ejecutándose en http://localhost:8000.`,
      0,
      err
    )
  }

  if (!response.ok) {
    let errorDetail = `Error ${response.status}: ${response.statusText}`
    let rawJson: unknown = null

    try {
      rawJson = await response.json()
      if (rawJson && typeof rawJson === 'object' && 'detail' in rawJson) {
        const detail = (rawJson as { detail: unknown }).detail
        if (typeof detail === 'string') {
          errorDetail = detail
        } else if (Array.isArray(detail)) {
          // Pydantic validation errors (HTTP 422)
          errorDetail = detail
            .map((e: { loc?: unknown[]; msg?: string; type?: string }) => {
              const field = Array.isArray(e.loc) ? e.loc.slice(1).join('.') : 'campo'
              return `${field}: ${e.msg || 'valor inválido'}`
            })
            .join(' | ')
        } else {
          errorDetail = JSON.stringify(detail)
        }
      }
    } catch {
      // response wasn't JSON
    }

    if (response.status === 409) {
      errorDetail =
        'Otra optimización está actualmente en ejecución. El motor ABC es estrictamente secuencial y solo admite un proceso a la vez.'
    }

    throw new ApiError(errorDetail, response.status, rawJson)
  }

  return response.json() as Promise<T>
}

export const api = {
  /**
   * Check backend health and operational status.
   */
  async getHealth(): Promise<HealthResponse> {
    return request<HealthResponse>('/health')
  },

  /**
   * Retrieve catalog of standard predefined demonstration scenarios.
   */
  async getScenarios(): Promise<PredefinedScenariosResponse> {
    return request<PredefinedScenariosResponse>('/scenarios')
  },

  /**
   * Validate spatial scenario geometry, camera profile, and hyperparameters.
   */
  async validateScenario(req: ValidationRequest): Promise<ValidationResponse> {
    return request<ValidationResponse>('/scenarios/validate', {
      method: 'POST',
      body: JSON.stringify(req),
    })
  },

  /**
   * Execute real sequential ABC optimization.
   */
  async runOptimization(req: OptimizationRequest): Promise<OptimizationResult> {
    return request<OptimizationResult>('/optimize/run', {
      method: 'POST',
      body: JSON.stringify(req),
    })
  },

  /**
   * Evaluate spatial simulated detection coverage for a camera configuration.
   */
  async evaluateCoverage(req: CoverageEvaluationRequest): Promise<CoverageEvaluationResponse> {
    return request<CoverageEvaluationResponse>('/coverage/evaluate', {
      method: 'POST',
      body: JSON.stringify(req),
    })
  },
}

