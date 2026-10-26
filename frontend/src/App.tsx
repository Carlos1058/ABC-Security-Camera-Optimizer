import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertCircle,
  Camera,
  CheckCircle2,
  FolderOpen,
  Info,
  Plus,
  X,
} from 'lucide-react'
import { AdvancedConfigModal } from './components/AdvancedConfigModal'
import { AnalysisDrawer } from './components/AnalysisDrawer'
import { FloatingActionDock } from './components/FloatingActionDock'
import { FloatingEditorDock } from './components/FloatingEditorDock'
import { FloorplanCanvas } from './components/FloorplanCanvas'
import { NewScenarioModal } from './components/NewScenarioModal'
import { ScenarioInspector } from './components/ScenarioInspector'
import { TemplatesModal } from './components/TemplatesModal'
import { TopBar } from './components/TopBar'
import { api, ApiError } from './services/api'
import { isPolygonSelfIntersecting } from './renderer/geometryValidation'
import { useScenarioEditor } from './renderer/useScenarioEditor'
import { exportScenarioToJson, parseAndValidateScenarioJson } from './services/scenarioIO'
import { buildCanonicalCoverageKey } from './renderer/coverageKey'
import type {
  CameraPose,
  CameraProfile,
  CanvasViewMode,
  CoverageEvaluationResponse,
  OptimizationConfig,
  OptimizationResult,
  PredefinedScenarioItem,
  Scenario,
} from './types/api'

// Fallback clean initial scenario: empty room with clean boundaries
const DEFAULT_CLEAN_SCENARIO: Scenario = {
  xmin: 0.0,
  xmax: 20.0,
  ymin: 0.0,
  ymax: 14.0,
  walls: [],
  obstacles: [],
  risk_zones: [],
  grid_resolution: 0.5,
}

const DEFAULT_FALLBACK_PROFILE: CameraProfile = {
  Rmin: 0.2,
  Rmax: 11.0,
  FOV: Math.PI / 2.0,
  p0: 1.0,
  beta_d: 0.4,
  beta_theta: 0.5,
}

const DEFAULT_FALLBACK_CONFIG: OptimizationConfig = {
  K: 3,
  SN: 10,
  max_cycles: 20,
  limit: 45,
  seed: '42',
  lambda_def: 1.0,
  Tcrit: 0.8,
  record_population: true,
}

export const App: React.FC = () => {
  // Requirement 4: Clean initial product state with clear entry actions
  const [isCleanInitialState, setIsCleanInitialState] = useState<boolean>(true)

  // Catalog and connection
  const [scenarios, setScenarios] = useState<PredefinedScenarioItem[]>([])
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('custom')
  const [serverConnected, setServerConnected] = useState<boolean | null>(null)
  const [isServerBusy, setIsServerBusy] = useState(false)
  const [serverVersion, setServerVersion] = useState<string>('0.4.0')

  // Problem parameters - start with clean empty scenario
  const [scenario, setScenario] = useState<Scenario>(DEFAULT_CLEAN_SCENARIO)
  const [profile, setProfile] = useState<CameraProfile>(DEFAULT_FALLBACK_PROFILE)
  const [config, setConfig] = useState<OptimizationConfig>(DEFAULT_FALLBACK_CONFIG)

  // Optimization execution & telemetry state
  const [isOptimizing, setIsOptimizing] = useState(false)
  const [optimizationResult, setOptimizationResult] = useState<OptimizationResult | null>(null)

  // Requirement 2: Monotonic execution tracking to prevent stale async responses
  const optimizationRequestIdRef = useRef<number>(0)
  const configVersionRef = useRef<number>(0)

  // Playback & telemetry inspection
  const [currentCycleIndex, setCurrentCycleIndex] = useState<number>(0)
  const [isPlaying, setIsPlaying] = useState<boolean>(false)
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1)
  const [inspectionMode, setInspectionMode] = useState<'best' | 'individual'>('best')
  const [selectedSourceIndex, setSelectedSourceIndex] = useState<number>(0)
  const [selectedCameraIndex, setSelectedCameraIndex] = useState<number | null>(null)

  // Coverage Heatmap state, caching and request versioning
  const [viewMode, setViewMode] = useState<CanvasViewMode>('floorplan')
  const [coverageOpacity, setCoverageOpacity] = useState<number>(0.75)
  const [coverageData, setCoverageData] = useState<CoverageEvaluationResponse | null>(null)
  const [coverageCamerasKey, setCoverageCamerasKey] = useState<string>('')
  const [isLoadingCoverage, setIsLoadingCoverage] = useState<boolean>(false)
  const coverageRequestIdRef = useRef<number>(0)
  const coverageCacheRef = useRef<Map<string, CoverageEvaluationResponse>>(new Map())

  // Floating Notification Toast with auto-dismiss
  const [notification, setNotification] = useState<{
    type: 'success' | 'error' | 'info'
    message: string
  } | null>(null)

  // Auto-dismiss non-critical toast notifications after 4 seconds
  useEffect(() => {
    if (!notification) return
    if (notification.type === 'error') {
      // Errors remain visible until explicitly dismissed by user
      return
    }

    const timer = setTimeout(() => {
      setNotification(null)
    }, 4000)

    return () => clearTimeout(timer)
  }, [notification])

  // Check health and fetch scenario catalog on mount
  useEffect(() => {
    let isMounted = true

    const checkServer = async () => {
      try {
        const health = await api.getHealth()
        if (!isMounted) return
        setServerConnected(true)
        setIsServerBusy(health.is_busy)
        if (health.version) setServerVersion(health.version)

        // Fetch authentic predefined benchmark scenarios from FastAPI catalog
        const catalog = await api.getScenarios()
        if (!isMounted) return
        setScenarios(catalog.scenarios)

        // Note: Do NOT auto-load partitioned_office or any complex scenario;
        // keep clean initial state with catalog available for user selection.
      } catch {
        if (!isMounted) return
        setServerConnected(false)
        setNotification({
          type: 'info',
          message:
            'Servidor FastAPI desconectado en http://localhost:8000. Inicie el backend con "python3 -m camera_optimizer.main" para optimizaciones reales.',
        })
      }
    }

    checkServer()
    // Periodic light heartbeat check
    const interval = setInterval(async () => {
      try {
        const h = await api.getHealth()
        setServerConnected(true)
        setIsServerBusy(h.is_busy)
      } catch {
        setServerConnected(false)
      }
    }, 8000)

    return () => {
      isMounted = false
      clearInterval(interval)
    }
  }, [])

  // Auto-advance playback loop
  useEffect(() => {
    if (!isPlaying || !optimizationResult) return

    const total = optimizationResult.history.length
    if (total <= 1) return

    const delay = Math.max(80, Math.floor(600 / playbackSpeed))
    const timer = setInterval(() => {
      setCurrentCycleIndex(prev => {
        if (prev >= total - 1) {
          setIsPlaying(false)
          return prev
        }
        return prev + 1
      })
    }, delay)

    return () => clearInterval(timer)
  }, [isPlaying, playbackSpeed, optimizationResult])

  // Invalidation strategy: modifying any input that affects the optimization invalidates prior results
  // and discards any in-flight asynchronous optimization calculations.
  const invalidateResult = useCallback(() => {
    configVersionRef.current += 1
    coverageRequestIdRef.current += 1
    optimizationRequestIdRef.current += 1
    setIsOptimizing(false)
    setOptimizationResult(null)
    setCoverageData(null)
    setCoverageCamerasKey('')
    coverageCacheRef.current.clear()
    setCurrentCycleIndex(0)
    setIsPlaying(false)
    setSelectedCameraIndex(null)
    setSelectedSourceIndex(0)
    setInspectionMode('best')
    setIsLoadingCoverage(false)
  }, [])

  const handleUpdateScenario = useCallback(
    (newScenario: Scenario) => {
      setScenario(newScenario)
      setSelectedScenarioId('custom')
      setIsCleanInitialState(false)
      invalidateResult()
    },
    [invalidateResult]
  )

  // Minimalist modal and drawer visibility states
  const [isNewScenarioOpen, setIsNewScenarioOpen] = useState(false)
  const [isTemplatesOpen, setIsTemplatesOpen] = useState(false)
  const [isAdvancedConfigOpen, setIsAdvancedConfigOpen] = useState(false)
  const [isAnalysisDrawerOpen, setIsAnalysisDrawerOpen] = useState(false)

  // Interactive Scenario Editor state hook
  const {
    activeTool,
    setActiveTool,
    selectedObject,
    setSelectedObject,
    snapToGrid,
    toggleSnap,
    snapSize,
    setSnapSize,
    doorWidth,
    setDoorWidth,
    draftPoints,
    setDraftPoints,
    cancelDraft,
    canUndo,
    canRedo,
    undo,
    redo,
    commitScenario,
    startDragTransaction,
    updateTransient,
    commitDragTransaction,
    cancelDragTransaction,
    deleteSelected,
  } = useScenarioEditor({
    scenario,
    onUpdateScenario: handleUpdateScenario,
    onInvalidate: invalidateResult,
  })

  // Editor polygon closure handler
  const handleFinishPolygon = useCallback(() => {
    if (draftPoints.length < 3) {
      setNotification({
        type: 'error',
        message: 'Un polígono debe tener al menos 3 vértices para cerrarse.',
      })
      return
    }
    if (isPolygonSelfIntersecting(draftPoints)) {
      setNotification({
        type: 'error',
        message: 'El polígono se autointerseca (no es simple). Reorganice los vértices.',
      })
      return
    }

    if (activeTool === 'risk_zone') {
      const nextRz = [
        ...(scenario.risk_zones || []),
        {
          vertices: [...draftPoints],
          weight: 2.0,
          name: `Zona de Riesgo #${(scenario.risk_zones?.length || 0) + 1}`,
        },
      ]
      commitScenario({ ...scenario, risk_zones: nextRz })
      setNotification({
        type: 'success',
        message: 'Zona de riesgo creada exitosamente.',
      })
    } else {
      const nextObs = [
        ...(scenario.obstacles || []),
        {
          vertices: [...draftPoints],
        },
      ]
      commitScenario({ ...scenario, obstacles: nextObs })
      setNotification({
        type: 'success',
        message: 'Obstáculo poligonal agregado exitosamente.',
      })
    }
    setDraftPoints([])
  }, [draftPoints, activeTool, scenario, commitScenario, setDraftPoints])

  // JSON Import & Export handlers
  const handleExportScenario = useCallback(() => {
    exportScenarioToJson(scenario)
    setNotification({
      type: 'success',
      message: 'Escenario exportado exitosamente como archivo JSON.',
    })
  }, [scenario])

  const handleImportScenario = useCallback(
    async (file: File) => {
      try {
        const text = await file.text()
        const { scenario: importedScenario, errors } = parseAndValidateScenarioJson(text)
        if (errors.length > 0 || !importedScenario) {
          setNotification({
            type: 'error',
            message: `Error al importar escenario: ${errors.join(', ')}`,
          })
          return
        }
        setIsCleanInitialState(false)
        commitScenario(importedScenario)
        setSelectedScenarioId('custom')
        setNotification({
          type: 'success',
          message: 'Escenario importado correctamente desde archivo JSON.',
        })
      } catch (err) {
        setNotification({
          type: 'error',
          message: `Error al leer el archivo: ${err instanceof Error ? err.message : String(err)}`,
        })
      }
    },
    [commitScenario]
  )

  const handleUpdateProfile = useCallback(
    (newProfile: CameraProfile) => {
      setProfile(newProfile)
      invalidateResult()
    },
    [invalidateResult]
  )

  const handleUpdateConfig = useCallback(
    (newConfig: OptimizationConfig) => {
      setConfig(newConfig)
      invalidateResult()
    },
    [invalidateResult]
  )

  // Handle switching predefined scenario
  const handleSelectScenario = (id: string) => {
    setSelectedScenarioId(id)
    setIsCleanInitialState(false)
    const item = scenarios.find(s => s.id === id)
    if (item) {
      setScenario(item.scenario)
      setProfile(item.recommended_profile)
      setConfig(item.recommended_config)
      setSelectedObject(null)
      setDraftPoints([])
      invalidateResult()
    }
  }

  // Handle creating a clean new scenario from modal
  const handleCreateScenario = (newScenario: Scenario) => {
    setIsCleanInitialState(false)
    setScenario(newScenario)
    setSelectedScenarioId('custom')
    setSelectedObject(null)
    setDraftPoints([])
    invalidateResult()
    setNotification({
      type: 'success',
      message: `Nuevo escenario de ${((newScenario.xmax ?? 0) - (newScenario.xmin ?? 0)).toFixed(1)} × ${((newScenario.ymax ?? 0) - (newScenario.ymin ?? 0)).toFixed(1)} m creado exitosamente.`,
    })
  }

  // Handle selecting a predefined template from modal
  const handleSelectTemplate = (template: PredefinedScenarioItem) => {
    setIsCleanInitialState(false)
    handleSelectScenario(template.id)
    setNotification({
      type: 'success',
      message: `Plantilla «${template.name}» cargada correctamente.`,
    })
  }

  // Handle Scenario Validation
  const handleValidate = async () => {
    setNotification(null)
    try {
      const res = await api.validateScenario({ scenario, profile, config })
      if (res.is_valid) {
        setNotification({
          type: 'success',
          message: 'Escenario e hiperparámetros validados exitosamente por FastAPI.',
        })
      } else {
        setNotification({
          type: 'error',
          message: `El escenario presenta ${res.errors.length} error(es) de validación: ${res.errors.join('; ')}`,
        })
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Error inesperado durante la validación'
      setNotification({ type: 'error', message: msg })
    }
  }

  // Handle Real ABC Optimization Execution with Stale Async Protection
  const handleRunOptimization = async () => {
    const reqId = ++optimizationRequestIdRef.current
    const capturedConfigVersion = configVersionRef.current

    setIsOptimizing(true)
    setIsPlaying(false)
    setNotification(null)

    try {
      const result = await api.runOptimization({ scenario, profile, config })

      // Requirement 2: Discard stale responses if configuration or scenario changed during in-flight execution
      if (
        reqId !== optimizationRequestIdRef.current ||
        capturedConfigVersion !== configVersionRef.current
      ) {
        console.warn(
          'Optimización asíncrona descartada: el escenario o configuración cambiaron durante el cálculo.'
        )
        return
      }

      setOptimizationResult(result)

      // Jump to final cycle on completion
      const lastCycle = Math.max(0, result.history.length - 1)
      setCurrentCycleIndex(lastCycle)

      setNotification({
        type: 'success',
        message: `Optimización finalizada exitosamente en ${result.execution_time_seconds.toFixed(2)}s (NFE: ${result.total_evaluations}, Costo Final: ${result.final_best_cost.toFixed(4)}).`,
      })
    } catch (err) {
      if (
        reqId !== optimizationRequestIdRef.current ||
        capturedConfigVersion !== configVersionRef.current
      ) {
        return
      }
      const msg = err instanceof ApiError ? err.message : 'Error de comunicación con el optimizador'
      setNotification({ type: 'error', message: msg })
    } finally {
      if (
        reqId === optimizationRequestIdRef.current &&
        capturedConfigVersion === configVersionRef.current
      ) {
        setIsOptimizing(false)
      }
    }
  }

  // Playback Navigation Handlers
  const handleTogglePlay = useCallback(() => {
    if (!optimizationResult || optimizationResult.history.length <= 1) return
    if (currentCycleIndex >= optimizationResult.history.length - 1) {
      setCurrentCycleIndex(0)
    }
    setIsPlaying(prev => !prev)
  }, [optimizationResult, currentCycleIndex])

  const handleStepForward = useCallback(() => {
    if (!optimizationResult) return
    setCurrentCycleIndex(prev => Math.min(optimizationResult.history.length - 1, prev + 1))
  }, [optimizationResult])

  const handleStepBackward = useCallback(() => {
    setCurrentCycleIndex(prev => Math.max(0, prev - 1))
  }, [])

  const handleResetPlayback = useCallback(() => {
    setCurrentCycleIndex(0)
    setIsPlaying(false)
  }, [])

  const handleSeekCycle = useCallback((cycle: number) => {
    setCurrentCycleIndex(cycle)
  }, [])

  // Resolve currently active camera poses for Canvas display
  const currentSnapshot = optimizationResult?.history[currentCycleIndex]

  const activeCameras: CameraPose[] = React.useMemo(() => {
    if (!optimizationResult || !currentSnapshot) {
      // If no optimization yet, generate dummy initial visual preview along boundary
      return []
    }

    if (inspectionMode === 'individual' && currentSnapshot.population) {
      const src = currentSnapshot.population[selectedSourceIndex]
      return src ? src.poses : currentSnapshot.best_poses
    }

    return currentSnapshot.best_poses
  }, [optimizationResult, currentSnapshot, inspectionMode, selectedSourceIndex])

  const currentCycleCost = currentSnapshot ? currentSnapshot.best_cost : null

  const activeScenario = optimizationResult ? optimizationResult.scenario : scenario
  const activeProfile = optimizationResult ? optimizationResult.profile : profile
  const activeConfig = optimizationResult ? optimizationResult.config : config

  // Compute deterministic canonical key for active cameras and all problem parameters
  const activeCamerasKey = useMemo(() => {
    return buildCanonicalCoverageKey(
      activeScenario,
      activeProfile,
      activeConfig.lambda_def,
      activeConfig.Tcrit,
      activeCameras
    )
  }, [activeScenario, activeProfile, activeConfig, activeCameras])

  // Asynchronous coverage fetcher with exact local cache and monotonic out-of-order discard
  const fetchCoverage = useCallback(
    async (targetCameras: CameraPose[], targetKey: string) => {
      if (targetCameras.length === 0 || !targetKey) {
        setCoverageData(null)
        setCoverageCamerasKey('')
        setIsLoadingCoverage(false)
        return
      }

      // 1. Check local cache first
      if (coverageCacheRef.current.has(targetKey)) {
        // Invalidate any older in-flight network requests so they do not overwrite the cached view
        coverageRequestIdRef.current += 1
        setCoverageData(coverageCacheRef.current.get(targetKey)!)
        setCoverageCamerasKey(targetKey)
        setIsLoadingCoverage(false)
        return
      }

      // 2. Fetch from backend with monotonic request tracking
      const reqId = ++coverageRequestIdRef.current
      setIsLoadingCoverage(true)

      try {
        const res = await api.evaluateCoverage({
          scenario: activeScenario,
          profile: activeProfile,
          cameras: targetCameras,
          lambda_def: activeConfig.lambda_def,
          t_crit: activeConfig.Tcrit,
        })

        // Always store in cache under exact canonical targetKey
        coverageCacheRef.current.set(targetKey, res)

        // Only present the response if this response corresponds to the latest requested ID
        if (reqId === coverageRequestIdRef.current) {
          setCoverageData(res)
          setCoverageCamerasKey(targetKey)
          setIsLoadingCoverage(false)
        }
      } catch (err) {
        if (reqId === coverageRequestIdRef.current) {
          setIsLoadingCoverage(false)
          console.warn('Error evaluating spatial coverage:', err)
        }
      }
    },
    [activeScenario, activeProfile, activeConfig]
  )

  // Auto-fetch coverage when paused or cycle selected, without hammering every animation frame
  useEffect(() => {
    if (viewMode === 'floorplan' || activeCameras.length === 0) return
    if (isPlaying) return
    if (coverageCamerasKey === activeCamerasKey) return

    let isSubscribed = true
    const timer = setTimeout(() => {
      if (isSubscribed) {
        void fetchCoverage(activeCameras, activeCamerasKey)
      }
    }, 0)

    return () => {
      isSubscribed = false
      clearTimeout(timer)
    }
  }, [viewMode, activeCameras, activeCamerasKey, isPlaying, coverageCamerasKey, fetchCoverage])

  return (
    <div className="app-layout">
      {/* 1. Compact Top Bar */}
      <TopBar
        onNewScenario={() => setIsNewScenarioOpen(true)}
        onOpenTemplates={() => setIsTemplatesOpen(true)}
        onExportJson={handleExportScenario}
        onImportJson={handleImportScenario}
        onValidateScenario={handleValidate}
        onOpenAdvancedConfig={() => setIsAdvancedConfigOpen(true)}
        serverConnected={serverConnected}
        isBusy={isServerBusy || isOptimizing}
        serverVersion={serverVersion}
      />

      {/* 2. Global Non-displacing Floating Notification Toast */}
      {notification && (
        <aside
          role="status"
          aria-live="polite"
          className={`notification-toast notification-${notification.type}`}
          data-testid="notification-toast"
        >
          <div className="notification-content">
            {notification.type === 'success' && <CheckCircle2 className="icon-sm text-success" />}
            {notification.type === 'error' && <AlertCircle className="icon-sm text-danger" />}
            {notification.type === 'info' && <Info className="icon-sm text-cyan" />}
            <span>{notification.message}</span>
          </div>
          <button
            type="button"
            className="notification-close"
            onClick={() => setNotification(null)}
            aria-label="Cerrar notificación"
          >
            <X className="icon-xs" />
          </button>
        </aside>
      )}

      {/* 3. Central Canvas Viewport (The absolute visual protagonist) */}
      <main className="canvas-main-viewport">
        {/* Clean Initial State Hero Overlay */}
        {isCleanInitialState && (
          <div className="clean-hero-overlay" data-testid="clean-hero-overlay">
            <div className="clean-hero-card">
              <div className="clean-hero-badge">
                <Camera className="icon-sm text-yellow" />
                <span>ABC Camera Optimizer</span>
              </div>
              <h1 className="clean-hero-title">Diseño y Optimización de Cobertura</h1>
              <p className="clean-hero-desc">
                Diseñe un nuevo plano arquitectónico interactivo o explore las plantillas estandarizadas de referencia para calcular posiciones y orientaciones óptimas de cámaras con colonias artificiales de abejas.
              </p>
              <div className="clean-hero-actions">
                <button
                  type="button"
                  id="btn-hero-create"
                  className="clean-btn-primary"
                  onClick={() => {
                    setIsCleanInitialState(false)
                    setIsNewScenarioOpen(true)
                  }}
                  aria-label="Crear nuevo escenario"
                >
                  <Plus className="icon-sm" />
                  <span>Crear escenario</span>
                </button>
                <button
                  type="button"
                  id="btn-hero-templates"
                  className="clean-btn-secondary"
                  onClick={() => {
                    setIsCleanInitialState(false)
                    setIsTemplatesOpen(true)
                  }}
                  aria-label="Abrir plantilla"
                >
                  <FolderOpen className="icon-sm" />
                  <span>Abrir plantilla</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Floating Editor Dock (Top Left) */}
        <FloatingEditorDock
          activeTool={activeTool}
          onChangeTool={setActiveTool}
          snapToGrid={snapToGrid}
          onToggleSnap={toggleSnap}
          snapSize={snapSize}
          onChangeSnapSize={setSnapSize}
          doorWidth={doorWidth}
          onChangeDoorWidth={setDoorWidth}
          canUndo={canUndo}
          canRedo={canRedo}
          onUndo={undo}
          onRedo={redo}
          selectedObject={selectedObject}
          onDeleteSelected={deleteSelected}
          draftPointsCount={draftPoints.length}
          onFinishPolygon={handleFinishPolygon}
          onCancelDraft={cancelDraft}
        />

        {/* 2D Floorplan Canvas (Occupies full viewport) */}
        <FloorplanCanvas
          scenario={activeScenario}
          cameras={activeCameras}
          profile={activeProfile}
          cameraColorMode={inspectionMode === 'individual' ? 'individual' : 'best'}
          selectedCameraIndex={selectedCameraIndex}
          onSelectCameraIndex={setSelectedCameraIndex}
          coverageData={coverageCamerasKey === activeCamerasKey ? coverageData : null}
          viewMode={viewMode}
          onChangeViewMode={setViewMode}
          coverageOpacity={coverageOpacity}
          onChangeCoverageOpacity={setCoverageOpacity}
          onRequestRefreshCoverage={() => fetchCoverage(activeCameras, activeCamerasKey)}
          isLoadingCoverage={isLoadingCoverage}
          isEditorMode={true}
          activeTool={activeTool}
          selectedObject={selectedObject}
          onSelectObject={setSelectedObject}
          snapToGrid={snapToGrid}
          snapSize={snapSize}
          doorWidth={doorWidth}
          draftPoints={draftPoints}
          onUpdateDraftPoints={setDraftPoints}
          onCommitScenario={commitScenario}
          onStartDragTransaction={startDragTransaction}
          onUpdateTransientScenario={updateTransient}
          onCommitDragTransaction={commitDragTransaction}
          onCancelDragTransaction={cancelDragTransaction}
          onNotify={setNotification}
        />

        {/* Contextual Inspector (Only shown when an object or boundary is selected) */}
        {(selectedObject || activeTool === 'boundary') && (
          <ScenarioInspector
            scenario={scenario}
            onUpdateScenario={commitScenario}
            selectedObject={selectedObject}
            activeTool={activeTool}
            onClose={() => setSelectedObject(null)}
          />
        )}

        {/* Floating Action Dock (Bottom Center) */}
        <FloatingActionDock
          cameraCount={config.K}
          onChangeCameraCount={k => handleUpdateConfig({ ...config, K: k })}
          onRunOptimization={handleRunOptimization}
          isOptimizing={isOptimizing}
          onOpenAdvancedConfig={() => setIsAdvancedConfigOpen(true)}
          result={optimizationResult}
          onOpenAnalysis={() => setIsAnalysisDrawerOpen(true)}
        />
      </main>

      {/* 4. Modals & Drawers */}
      <NewScenarioModal
        isOpen={isNewScenarioOpen}
        onClose={() => setIsNewScenarioOpen(false)}
        onCreateScenario={handleCreateScenario}
      />

      <TemplatesModal
        isOpen={isTemplatesOpen}
        onClose={() => setIsTemplatesOpen(false)}
        templates={scenarios}
        selectedTemplateId={selectedScenarioId}
        onSelectTemplate={handleSelectTemplate}
      />

      <AdvancedConfigModal
        isOpen={isAdvancedConfigOpen}
        onClose={() => setIsAdvancedConfigOpen(false)}
        config={config}
        onUpdateConfig={handleUpdateConfig}
        profile={profile}
        onUpdateProfile={handleUpdateProfile}
        scenario={scenario}
        onUpdateScenario={handleUpdateScenario}
        disabled={isOptimizing}
      />

      <AnalysisDrawer
        isOpen={isAnalysisDrawerOpen}
        onClose={() => setIsAnalysisDrawerOpen(false)}
        result={optimizationResult}
        currentCycleIndex={currentCycleIndex}
        currentCycleCost={currentCycleCost}
        isPlaying={isPlaying}
        playbackSpeed={playbackSpeed}
        onTogglePlay={handleTogglePlay}
        onStepForward={handleStepForward}
        onStepBackward={handleStepBackward}
        onReset={handleResetPlayback}
        onSetSpeed={setPlaybackSpeed}
        onSeekCycle={handleSeekCycle}
        inspectionMode={inspectionMode}
        onSetInspectionMode={setInspectionMode}
        selectedSourceIndex={selectedSourceIndex}
        onSelectSourceIndex={setSelectedSourceIndex}
        currentSnapshot={currentSnapshot}
      />
    </div>
  )
}
