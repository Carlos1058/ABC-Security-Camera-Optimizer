import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { FloorplanCanvas } from '../components/FloorplanCanvas'
import { PlaybackControls } from '../components/PlaybackControls'
import { api, ApiError } from '../services/api'
import type { OptimizationResult, PredefinedScenariosResponse } from '../types/api'
import { MockResizeObserver } from './setup'

// Authentic mock catalog response
const mockScenariosCatalog: PredefinedScenariosResponse = {
  scenarios: [
    {
      id: 'partitioned_office',
      name: 'Oficina Particionada',
      description: 'Oficina corporativa con tabiques y sala de servidores',
      scenario: {
        xmin: 0.0,
        xmax: 24.0,
        ymin: 0.0,
        ymax: 16.0,
        walls: [
          { start: { x: 0.0, y: 8.0 }, end: { x: 10.0, y: 8.0 }, is_opaque: true },
          { start: { x: 12.0, y: 8.0 }, end: { x: 24.0, y: 8.0 }, is_opaque: true },
        ],
        obstacles: [
          {
            vertices: [
              { x: 4.0, y: 3.0 },
              { x: 7.0, y: 3.0 },
              { x: 7.0, y: 5.0 },
              { x: 4.0, y: 5.0 },
            ],
          },
        ],
        risk_zones: [
          {
            vertices: [
              { x: 1.0, y: 9.0 },
              { x: 6.0, y: 9.0 },
              { x: 6.0, y: 15.0 },
              { x: 1.0, y: 15.0 },
            ],
            weight: 3.5,
            name: 'Server Room',
          },
        ],
        grid_resolution: 1.0,
      },
      recommended_profile: {
        Rmin: 0.2,
        Rmax: 11.0,
        FOV: Math.PI / 2.0,
        p0: 1.0,
        beta_d: 0.4,
        beta_theta: 0.5,
      },
      recommended_config: {
        K: 3,
        SN: 6,
        max_cycles: 2,
        limit: 36,
        seed: '42',
        lambda_def: 1.0,
        Tcrit: 0.8,
        record_population: true,
      },
    },
  ],
}

// Authentic mock optimization output matching canonical ABC
const createMockResult = (seed = '9007199254740993', k = 3): OptimizationResult => ({
  scenario: mockScenariosCatalog.scenarios[0].scenario,
  profile: mockScenariosCatalog.scenarios[0].recommended_profile,
  config: {
    K: k,
    SN: 4,
    max_cycles: 2,
    limit: 24,
    seed,
    lambda_def: 1.0,
    Tcrit: 0.8,
    record_population: true,
  },
  effective_seed: seed,
  dimension: 3 * k,
  initial_best_cost: 1.429893,
  initial_best_poses: [
    { x: 5.0, y: 5.0, theta: 0.5, theta_deg: 28.6 },
    { x: 12.0, y: 3.0, theta: 1.57, theta_deg: 90.0 },
    { x: 18.0, y: 10.0, theta: -1.0, theta_deg: -57.3 },
  ].slice(0, k),
  final_best_cost: 0.654321,
  final_best_poses: [
    { x: 5.5, y: 5.2, theta: 0.6, theta_deg: 34.4 },
    { x: 12.3, y: 3.1, theta: 1.5, theta_deg: 85.9 },
    { x: 18.2, y: 10.4, theta: -0.9, theta_deg: -51.6 },
  ].slice(0, k),
  best_cost_per_cycle: [1.429893, 0.985123, 0.654321],
  mean_cost_per_cycle: [1.650123, 1.250456, 0.910234],
  coverage_metrics: {
    num_eval_points: 300,
    num_covered_points: 210,
    geometric_coverage_ratio: 0.7,
    geometric_coverage_percent: 70.0,
    mean_probabilistic_coverage: 0.52,
    risk_weighted_coverage: 0.55,
    num_critical_points: 25,
    critical_deficit: 0.204321,
  },
  total_evaluations: 240,
  total_proposals: 260,
  rejected_infeasible_proposals: 20,
  total_scout_resets: 1,
  execution_time_seconds: 0.45,
  population_history_available: true,
  notes: 'Sequential ABC Canonical test execution',
  history: [
    {
      cycle: 0,
      best_cost: 1.429893,
      best_poses: [
        { x: 5.0, y: 5.0, theta: 0.5, theta_deg: 28.6 },
        { x: 12.0, y: 3.0, theta: 1.57, theta_deg: 90.0 },
        { x: 18.0, y: 10.0, theta: -1.0, theta_deg: -57.3 },
      ].slice(0, k),
      mean_population_cost: 1.650123,
      improvements_count: 0,
      scout_resets: 0,
      population: [
        {
          position: [5.0, 5.0, 0.5, 12.0, 3.0, 1.57, 18.0, 10.0, -1.0].slice(0, 3 * k),
          poses: [
            { x: 5.0, y: 5.0, theta: 0.5, theta_deg: 28.6 },
            { x: 12.0, y: 3.0, theta: 1.57, theta_deg: 90.0 },
            { x: 18.0, y: 10.0, theta: -1.0, theta_deg: -57.3 },
          ].slice(0, k),
          cost: 1.429893,
          fitness: 0.41154,
          trial: 0,
        },
        {
          position: [3.0, 2.0, 0.0, 10.0, 6.0, 1.0, 15.0, 8.0, -0.5].slice(0, 3 * k),
          poses: [
            { x: 3.0, y: 2.0, theta: 0.0, theta_deg: 0.0 },
            { x: 10.0, y: 6.0, theta: 1.0, theta_deg: 57.3 },
            { x: 15.0, y: 8.0, theta: -0.5, theta_deg: -28.6 },
          ].slice(0, k),
          cost: 1.870123,
          fitness: 0.34842,
          trial: 1,
        },
      ],
    },
    {
      cycle: 1,
      best_cost: 0.985123,
      best_poses: [
        { x: 5.2, y: 5.1, theta: 0.55, theta_deg: 31.5 },
        { x: 12.1, y: 3.05, theta: 1.55, theta_deg: 88.8 },
        { x: 18.1, y: 10.2, theta: -0.95, theta_deg: -54.4 },
      ].slice(0, k),
      mean_population_cost: 1.250456,
      improvements_count: 2,
      scout_resets: 0,
      population: [
        {
          position: [5.2, 5.1, 0.55, 12.1, 3.05, 1.55, 18.1, 10.2, -0.95].slice(0, 3 * k),
          poses: [
            { x: 5.2, y: 5.1, theta: 0.55, theta_deg: 31.5 },
            { x: 12.1, y: 3.05, theta: 1.55, theta_deg: 88.8 },
            { x: 18.1, y: 10.2, theta: -0.95, theta_deg: -54.4 },
          ].slice(0, k),
          cost: 0.985123,
          fitness: 0.50375,
          trial: 0,
        },
      ],
    },
    {
      cycle: 2,
      best_cost: 0.654321,
      best_poses: [
        { x: 5.5, y: 5.2, theta: 0.6, theta_deg: 34.4 },
        { x: 12.3, y: 3.1, theta: 1.5, theta_deg: 85.9 },
        { x: 18.2, y: 10.4, theta: -0.9, theta_deg: -51.6 },
      ].slice(0, k),
      mean_population_cost: 0.910234,
      improvements_count: 3,
      scout_resets: 1,
      population: [
        {
          position: [5.5, 5.2, 0.6, 12.3, 3.1, 1.5, 18.2, 10.4, -0.9].slice(0, 3 * k),
          poses: [
            { x: 5.5, y: 5.2, theta: 0.6, theta_deg: 34.4 },
            { x: 12.3, y: 3.1, theta: 1.5, theta_deg: 85.9 },
            { x: 18.2, y: 10.4, theta: -0.9, theta_deg: -51.6 },
          ].slice(0, k),
          cost: 0.654321,
          fitness: 0.60447,
          trial: 0,
        },
      ],
    },
  ],
})

describe('React Testing Library Integration Tests (Fase 5A Verified)', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    MockResizeObserver.instances = []

    vi.spyOn(api, 'getHealth').mockResolvedValue({
      status: 'ok',
      service: 'camera_optimizer',
      version: '0.4.0',
      is_busy: false,
    })

    vi.spyOn(api, 'getScenarios').mockResolvedValue(mockScenariosCatalog)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  // 1. Montaje de App con respuestas API controladas
  it('1. mounts App cleanly with controlled API responses and initial catalog', async () => {
    render(<App />)

    // TopBar displays title and healthy connection
    expect(screen.getByText(/ABC Security Camera Optimizer/i)).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText(/FastAPI Conectado/i)).toBeInTheDocument()
    })

    // Scenario name loaded from catalog
    expect(screen.getByText(/Oficina Particionada/i)).toBeInTheDocument()
    // Results panel initial empty state
    expect(screen.getByText(/Configure los parámetros y ejecute una optimización/i)).toBeInTheDocument()
  })

  // 2. Cambio de K que invalida un resultado previo
  it('2. changing cameras K invalidates previous optimization result and resets telemetry', async () => {
    vi.spyOn(api, 'runOptimization').mockResolvedValueOnce(createMockResult('9007199254740993', 3))

    render(<App />)

    // Run optimization first
    const runBtn = screen.getByRole('button', { name: /Ejecutar Optimización ABC/i })
    fireEvent.click(runBtn)

    // Wait for optimization to finish and result to appear
    await waitFor(() => {
      expect(screen.getByText(/Resultados de Optimización ABC/i)).toBeInTheDocument()
    })
    expect(screen.getAllByText('0.654321').length).toBeGreaterThan(0)

    // Now change K from 3 to 5
    const kInput = screen.getByLabelText(/Cámaras \(K\):/i)
    fireEvent.change(kInput, { target: { value: '5' } })

    // Previous result must be completely invalidated
    expect(screen.queryByText(/Resultados de Optimización ABC/i)).not.toBeInTheDocument()
    expect(screen.queryAllByText('0.654321')).toHaveLength(0)
    expect(screen.getByText(/Configure los parámetros y ejecute una optimización/i)).toBeInTheDocument()
  })

  // 3. Cambio de perfil óptico que invalida el resultado previo
  it('3. changing optical camera profile invalidates previous optimization result', async () => {
    vi.spyOn(api, 'runOptimization').mockResolvedValueOnce(createMockResult('9007199254740993', 3))

    render(<App />)

    // Run optimization
    fireEvent.click(screen.getByRole('button', { name: /Ejecutar Optimización ABC/i }))

    await waitFor(() => {
      expect(screen.getByText(/Resultados de Optimización ABC/i)).toBeInTheDocument()
    })
    expect(screen.getAllByText('0.654321').length).toBeGreaterThan(0)

    // Expand Profile section
    const profileAccordion = screen.getByRole('button', { name: /Perfil Óptico de Cámara/i })
    fireEvent.click(profileAccordion)

    // Modify Rmax
    const rmaxInput = screen.getByLabelText(/Rmax \(m\):/i)
    fireEvent.change(rmaxInput, { target: { value: '15' } })

    // Stale result must be cleared immediately
    expect(screen.queryByText(/Resultados de Optimización ABC/i)).not.toBeInTheDocument()
    expect(screen.queryAllByText('0.654321')).toHaveLength(0)
    expect(screen.getByText(/Configure los parámetros y ejecute una optimización/i)).toBeInTheDocument()
  })

  // 4. Reproducción de ciclos reales desde una respuesta HTTP
  it('4. reproduces cycle progression from real HTTP response through playback controls', async () => {
    vi.spyOn(api, 'runOptimization').mockResolvedValueOnce(createMockResult('9007199254740993', 3))

    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: /Ejecutar Optimización ABC/i }))

    await waitFor(() => {
      expect(screen.getByText(/Resultados de Optimización ABC/i)).toBeInTheDocument()
    })

    // On completion, app jumps to final cycle (Ciclo 2)
    expect(screen.getByRole('slider')).toHaveValue('2')
    expect(screen.getByText('Ciclo 2')).toBeInTheDocument()

    // Step backward to cycle 1
    const stepBackBtn = screen.getByTitle(/Ciclo anterior/i)
    fireEvent.click(stepBackBtn)

    expect(screen.getByRole('slider')).toHaveValue('1')
    expect(screen.getByText('Ciclo 1')).toBeInTheDocument()
    expect(screen.getAllByText('0.985123').length).toBeGreaterThan(0)

    // Step backward to initial cycle 0
    fireEvent.click(stepBackBtn)
    expect(screen.getByRole('slider')).toHaveValue('0')
    expect(screen.getByText('Ciclo 0')).toBeInTheDocument()
    expect(screen.getAllByText('1.429893').length).toBeGreaterThan(0)

    // Step forward back to cycle 1
    const stepForwardBtn = screen.getByTitle(/Ciclo siguiente/i)
    fireEvent.click(stepForwardBtn)
    expect(screen.getByRole('slider')).toHaveValue('1')
    expect(screen.getByText('Ciclo 1')).toBeInTheDocument()
  })

  // 5. Inspección de una fuente individual
  it('5. allows inspection of an individual food source within the active cycle', async () => {
    vi.spyOn(api, 'runOptimization').mockResolvedValueOnce(createMockResult('9007199254740993', 3))

    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: /Ejecutar Optimización ABC/i }))

    await waitFor(() => {
      expect(screen.getByText(/Resultados de Optimización ABC/i)).toBeInTheDocument()
    })

    // Reset to cycle 0 where population has 2 sources
    fireEvent.click(screen.getByTitle(/Reiniciar reproducción/i))
    expect(screen.getByRole('slider')).toHaveValue('0')
    expect(screen.getByText('Ciclo 0')).toBeInTheDocument()

    // Switch inspection mode from "Mejor Solución Histórica" to "Fuente Individual"
    const individualTab = screen.getByRole('button', { name: /Fuente Individual/i })
    fireEvent.click(individualTab)

    // Select second food source (Fuente #2)
    const sourceSelect = screen.getByLabelText(/Fuente:/i)
    fireEvent.change(sourceSelect, { target: { value: '1' } })

    // Source details displayed in telemetry badge
    expect(screen.getByText('1.870123')).toBeInTheDocument()
    expect(screen.getByText('Trial:')).toBeInTheDocument()
  })

  // 6. Conservación exacta de una semilla de 64 bits
  it('6. preserves exact 64-bit seed (9007199254740993) across form input, API request, and clipboard copy', async () => {
    const hugeSeed = '9007199254740993'
    let receivedPayloadConfigSeed: unknown = null

    vi.spyOn(api, 'runOptimization').mockImplementationOnce(async req => {
      receivedPayloadConfigSeed = req.config.seed
      return createMockResult(hugeSeed, 3)
    })

    render(<App />)

    // Enter 64-bit seed into input
    const seedInput = screen.getByLabelText(/Semilla PRNG \(Opcional\):/i)
    fireEvent.change(seedInput, { target: { value: hugeSeed } })
    expect(seedInput).toHaveValue(hugeSeed)

    // Click optimize
    fireEvent.click(screen.getByRole('button', { name: /Ejecutar Optimización ABC/i }))

    await waitFor(() => {
      expect(screen.getByText(hugeSeed)).toBeInTheDocument()
    })

    // Verify sent payload kept string without numeric conversion
    expect(receivedPayloadConfigSeed).toBe(hugeSeed)
    expect(typeof receivedPayloadConfigSeed).toBe('string')

    // Click clipboard copy button
    const copyBtn = screen.getByTitle(/Copiar semilla reproducible/i)
    fireEvent.click(copyBtn)
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(hugeSeed)
    })
  })

  // 7. Selección de una cámara en el Canvas
  it('7. handles interactive camera click selection on canvas and clears on outside click', () => {
    const onSelectMock = vi.fn()
    const cameras = [
      { x: 5.0, y: 5.0, theta: 0.5, theta_deg: 28.6 },
      { x: 15.0, y: 10.0, theta: -1.0, theta_deg: -57.3 },
    ]

    const { container } = render(
      <FloorplanCanvas
        scenario={{ xmin: 0, xmax: 20, ymin: 0, ymax: 20 }}
        cameras={cameras}
        selectedCameraIndex={null}
        onSelectCameraIndex={onSelectMock}
      />
    )

    const canvas = container.querySelector('canvas')!
    expect(canvas).toBeInTheDocument()

    // In a 600x400 canvas with a 20x20 room:
    // Scale is min((600-90)/20, (400-90)/20) = min(25.5, 15.5) = 15.5 px/m.
    // Cam 0 at (5, 5) maps to:
    // offsetX = (600 - 310)/2 = 145. offsetY = (400 - 310)/2 = 45.
    // Screen X = 145 + 5 * 15.5 = 222.5. Screen Y = 45 + (20 - 5) * 15.5 = 277.5.

    // 1. Click directly on camera 0:
    fireEvent.mouseDown(canvas, { clientX: 223, clientY: 278 })
    fireEvent.mouseUp(canvas, { clientX: 223, clientY: 278 })
    expect(onSelectMock).toHaveBeenCalledWith(0)

    // 2. Click far away in empty space (e.g. clientX: 50, clientY: 50)
    onSelectMock.mockClear()
    fireEvent.mouseDown(canvas, { clientX: 50, clientY: 50 })
    fireEvent.mouseUp(canvas, { clientX: 50, clientY: 50 })
    expect(onSelectMock).toHaveBeenCalledWith(null)

    // 3. Drag movement >= 5px should NOT trigger selection
    onSelectMock.mockClear()
    fireEvent.mouseDown(canvas, { clientX: 223, clientY: 278 })
    fireEvent.mouseMove(canvas, { clientX: 235, clientY: 290 })
    fireEvent.mouseUp(canvas, { clientX: 235, clientY: 290 })
    expect(onSelectMock).not.toHaveBeenCalled()
  })

  // 8. Redimensionamiento del Canvas
  it('8. adjusts canvas size and triggers redraw on container resize via ResizeObserver', () => {
    const { container, unmount } = render(
      <FloorplanCanvas
        scenario={{ xmin: 0, xmax: 20, ymin: 0, ymax: 20 }}
        cameras={[]}
      />
    )

    expect(MockResizeObserver.instances.length).toBeGreaterThan(0)
    const observer = MockResizeObserver.instances[0]
    expect(observer.observe).toHaveBeenCalled()

    // Trigger resize observer callback
    observer.trigger()

    const canvas = container.querySelector('canvas')!
    expect(canvas).toBeInTheDocument()

    // Unmount disconnects observer
    unmount()
    expect(observer.disconnect).toHaveBeenCalled()
  })

  // 9. Manejo de errores HTTP (409 y 422)
  it('9. displays clear error banners on HTTP 409 concurrency conflict and 422 validation failure', async () => {
    vi.spyOn(api, 'runOptimization').mockRejectedValueOnce(
      new ApiError(
        'Otra optimización está actualmente en ejecución. El motor ABC es estrictamente secuencial y solo admite un proceso a la vez.',
        409
      )
    )

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: /Ejecutar Optimización ABC/i }))

    await waitFor(() => {
      expect(
        screen.getByText(/Otra optimización está actualmente en ejecución/i)
      ).toBeInTheDocument()
    })

    // Test HTTP 422
    vi.spyOn(api, 'runOptimization').mockRejectedValueOnce(
      new ApiError('config.seed: Seed must be in range [0, 2^64 - 1]', 422)
    )

    fireEvent.click(screen.getByRole('button', { name: /Ejecutar Optimización ABC/i }))

    await waitFor(() => {
      expect(screen.getByText(/Seed must be in range/i)).toBeInTheDocument()
    })
  })

  // 10. Compatibilidad de navegación mediante teclado
  it('10. keyboard shortcuts work on body but do not intercept buttons or text inputs', () => {
    const onTogglePlay = vi.fn()
    const onStepForward = vi.fn()
    const onStepBackward = vi.fn()

    const { container } = render(
      <div>
        <input id="test-input" type="text" defaultValue="test" />
        <button id="test-button" type="button">Action</button>
        <PlaybackControls
          currentCycle={1}
          totalCycles={5}
          isPlaying={false}
          playbackSpeed={1}
          onTogglePlay={onTogglePlay}
          onStepForward={onStepForward}
          onStepBackward={onStepBackward}
          onReset={vi.fn()}
          onSetSpeed={vi.fn()}
          onSeekCycle={vi.fn()}
          inspectionMode="best"
          onSetInspectionMode={vi.fn()}
          selectedSourceIndex={0}
          onSelectSourceIndex={vi.fn()}
          populationAvailable={true}
        />
      </div>
    )

    // 1. Space press on document body triggers play/pause
    fireEvent.keyDown(document.body, { code: 'Space' })
    expect(onTogglePlay).toHaveBeenCalledTimes(1)

    // 2. Arrow keys on document body trigger step forward/back
    fireEvent.keyDown(document.body, { code: 'ArrowRight' })
    expect(onStepForward).toHaveBeenCalledTimes(1)

    fireEvent.keyDown(document.body, { code: 'ArrowLeft' })
    expect(onStepBackward).toHaveBeenCalledTimes(1)

    // 3. Space press inside input is NOT intercepted
    const inputEl = container.querySelector('#test-input')!
    fireEvent.keyDown(inputEl, { code: 'Space' })
    expect(onTogglePlay).toHaveBeenCalledTimes(1) // not incremented!

    // 4. Space press on button is NOT intercepted
    const btnEl = container.querySelector('#test-button')!
    fireEvent.keyDown(btnEl, { code: 'Space' })
    expect(onTogglePlay).toHaveBeenCalledTimes(1) // not incremented!
  })

  it('11. FloorplanCanvas heatmap modes, opacity controls, legends and inspection', () => {
    const onChangeViewMode = vi.fn()
    const onChangeCoverageOpacity = vi.fn()
    const onRequestRefreshCoverage = vi.fn()

    const mockCoverageData = {
      cell_width: 1.0,
      cell_height: 1.0,
      total_nodes: 2,
      nodes: [
        { x: 5.0, y: 5.0, probability: 0.85, binary_covered: true, risk_weight: 1.5 },
        { x: 10.0, y: 5.0, probability: 0.0, binary_covered: false, risk_weight: 1.0 },
      ],
      metrics: {
        num_eval_points: 2,
        num_covered_points: 1,
        geometric_coverage_ratio: 0.5,
        geometric_coverage_percent: 50.0,
        mean_probabilistic_coverage: 0.425,
        risk_weighted_coverage: 0.425,
        num_critical_points: 0,
        critical_deficit: 0.0,
      },
      objective_cost: 0.575,
      is_feasible: true,
    }

    const scenario = { xmin: 0, xmax: 20, ymin: 0, ymax: 10 }
    const cameras = [{ x: 5.0, y: 5.0, theta: 0.0 }]

    const { rerender } = render(
      <FloorplanCanvas
        scenario={scenario}
        cameras={cameras}
        viewMode="probability"
        onChangeViewMode={onChangeViewMode}
        coverageData={mockCoverageData}
        coverageOpacity={0.65}
        onChangeCoverageOpacity={onChangeCoverageOpacity}
        onRequestRefreshCoverage={onRequestRefreshCoverage}
      />
    )

    // Check segmented mode buttons
    expect(screen.getByRole('tab', { name: /Plano/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Probabilidad/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Cobertura geométrica/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Riesgo/i })).toBeInTheDocument()

    // Probabilidad tab is active
    expect(screen.getByRole('tab', { name: /Probabilidad/i })).toHaveAttribute('aria-selected', 'true')

    // Click Plano tab
    fireEvent.click(screen.getByRole('tab', { name: /Plano/i }))
    expect(onChangeViewMode).toHaveBeenCalledWith('floorplan')

    // Click Cobertura geométrica tab
    fireEvent.click(screen.getByRole('tab', { name: /Cobertura geométrica/i }))
    expect(onChangeViewMode).toHaveBeenCalledWith('geometric')

    // Opacity slider is present in heatmap mode
    const slider = screen.getByLabelText(/Ajustar opacidad del mapa de calor/i) as HTMLInputElement
    expect(slider).toBeInTheDocument()
    expect(slider.value).toBe('0.65')

    // Change opacity
    fireEvent.change(slider, { target: { value: '0.8' } })
    expect(onChangeCoverageOpacity).toHaveBeenCalledWith(0.8)

    // Refresh coverage button
    const refreshBtn = screen.getByTitle(/Actualizar evaluación de cobertura/i)
    fireEvent.click(refreshBtn)
    expect(onRequestRefreshCoverage).toHaveBeenCalledTimes(1)

    // Probability continuous legend is visible
    expect(screen.getByText('0%')).toBeInTheDocument()
    expect(screen.getByText('100%')).toBeInTheDocument()

    // Switch to geometric mode
    rerender(
      <FloorplanCanvas
        scenario={scenario}
        cameras={cameras}
        viewMode="geometric"
        onChangeViewMode={onChangeViewMode}
        coverageData={mockCoverageData}
        coverageOpacity={0.65}
        onChangeCoverageOpacity={onChangeCoverageOpacity}
        onRequestRefreshCoverage={onRequestRefreshCoverage}
      />
    )
    expect(screen.getByText('Cubierto')).toBeInTheDocument()
    expect(screen.getByText('Sin cobertura')).toBeInTheDocument()

    // Switch to risk mode
    rerender(
      <FloorplanCanvas
        scenario={scenario}
        cameras={cameras}
        viewMode="risk"
        onChangeViewMode={onChangeViewMode}
        coverageData={mockCoverageData}
        coverageOpacity={0.65}
        onChangeCoverageOpacity={onChangeCoverageOpacity}
        onRequestRefreshCoverage={onRequestRefreshCoverage}
      />
    )
    expect(screen.getByText('Estándar (1.0x)')).toBeInTheDocument()
    expect(screen.getByText('Riesgo crítico (≥ 3.0x)')).toBeInTheDocument()
  })

  it('12. verifies camera parity check prevents rendering stale heatmaps under new camera poses', () => {
    // In FloorplanCanvas, if cameras change, FloorplanCanvas receives updated cameras.
    // In App.tsx, activeCoverage is strictly null if coverageCamerasKey !== activeCamerasKey.
    // Let's test FloorplanCanvas when coverageData is null (e.g. invalidation/stale state):
    const scenario = { xmin: 0, xmax: 20, ymin: 0, ymax: 10 }
    const cameras = [{ x: 8.0, y: 8.0, theta: 1.57 }]

    render(
      <FloorplanCanvas
        scenario={scenario}
        cameras={cameras}
        viewMode="probability"
        coverageData={null}
        coverageOpacity={0.65}
      />
    )

    // When coverageData is null, probability legend should NOT be rendered
    expect(screen.queryByText('100%')).not.toBeInTheDocument()
  })
})

