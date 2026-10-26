import React, { useId, useState } from 'react'
import {
  AlertCircle,
  Camera,
  CheckCircle2,
  CheckSquare,
  ChevronDown,
  ChevronUp,
  Clock,
  Eye,
  Play,
  RotateCw,
  Settings,
  Shield,
  Sliders,
  Square,
  Target,
} from 'lucide-react'
import type {
  CameraProfile,
  OptimizationConfig,
  PredefinedScenarioItem,
  Scenario,
  ValidationResponse,
} from '../types/api'

interface ConfigPanelProps {
  scenarios: PredefinedScenarioItem[]
  selectedScenarioId: string
  onSelectScenario: (scenarioId: string) => void
  scenario: Scenario
  onUpdateScenario: (scenario: Scenario) => void
  profile: CameraProfile
  onUpdateProfile: (profile: CameraProfile) => void
  config: OptimizationConfig
  onUpdateConfig: (config: OptimizationConfig) => void
  onValidate: () => Promise<void>
  onRunOptimization: () => Promise<void>
  isValidating: boolean
  isOptimizing: boolean
  validationResult: ValidationResponse | null
  serverConnected: boolean | null
}

export const ConfigPanel: React.FC<ConfigPanelProps> = ({
  scenarios,
  selectedScenarioId,
  onSelectScenario,
  scenario,
  onUpdateScenario,
  profile,
  onUpdateProfile,
  config,
  onUpdateConfig,
  onValidate,
  onRunOptimization,
  isValidating,
  isOptimizing,
  validationResult,
  serverConnected,
}) => {
  // Collapsible accordion sections
  const [openSection, setOpenSection] = useState<'meta' | 'profile' | 'objective' | null>('meta')

  const fovId = useId()
  const fovDegrees = ((profile.FOV * 180) / Math.PI).toFixed(0)

  // Estimated resource calculations
  const roomW = scenario.xmax - (scenario.xmin ?? 0)
  const roomH = scenario.ymax - (scenario.ymin ?? 0)
  const res = scenario.grid_resolution ?? 1.0
  const estGridCells = Math.ceil(roomW / res) * Math.ceil(roomH / res)
  const estNFE = config.SN + 2 * config.SN * config.max_cycles + config.max_cycles
  const estWork = estNFE * config.K * estGridCells
  const isBudgetWarning = estWork > 80_000_000

  const toggleSection = (s: 'meta' | 'profile' | 'objective') => {
    setOpenSection(prev => (prev === s ? null : s))
  }

  const handleRandomSeed = () => {
    // Generate a 63-bit positive integer represented losslessly as a decimal string
    if (typeof window !== 'undefined' && window.crypto && typeof window.BigUint64Array !== 'undefined') {
      const buffer = new BigUint64Array(1)
      window.crypto.getRandomValues(buffer)
      const randomSeed = (buffer[0] & 0x7fffffffffffffffn).toString()
      onUpdateConfig({ ...config, seed: randomSeed })
    } else {
      const fallback = Math.floor(Math.random() * 2147483647).toString()
      onUpdateConfig({ ...config, seed: fallback })
    }
  }

  const handleClearSeed = () => {
    onUpdateConfig({ ...config, seed: null })
  }

  return (
    <aside className="config-sidebar">
      <div className="sidebar-header">
        <Sliders className="icon-sm text-gold" />
        <h2 className="sidebar-title">Configuración del Problema</h2>
      </div>

      <div className="config-scroll-area">
        {/* 1. Predefined Scenario Selector */}
        <div className="form-group">
          <label htmlFor="scenario-select" className="input-label">
            <Target className="icon-xs text-cyan" />
            <span>Escenario Arquitectónico:</span>
          </label>
          <select
            id="scenario-select"
            className="select-input"
            value={selectedScenarioId}
            onChange={e => onSelectScenario(e.target.value)}
            disabled={isOptimizing}
          >
            {scenarios.map(scn => (
              <option key={scn.id} value={scn.id}>
                {scn.name}
              </option>
            ))}
            {selectedScenarioId === 'custom' && (
              <option value="custom">★ Escenario Personalizado (Editado)</option>
            )}
          </select>
          {selectedScenarioId === 'custom' ? (
            <p className="field-hint text-gold font-medium">
              Escenario modificado por el usuario mediante el editor visual.
            </p>
          ) : (
            scenarios.find(s => s.id === selectedScenarioId) && (
              <p className="field-hint">
                {scenarios.find(s => s.id === selectedScenarioId)?.description}
              </p>
            )
          )}
        </div>

        {/* 2. Grid Resolution */}
        <div className="form-group">
          <div className="input-label-row">
            <label htmlFor="grid-resolution" className="input-label">
              Resolución de Malla (m):
            </label>
            <span className="value-badge">{scenario.grid_resolution?.toFixed(2) ?? '1.00'} m</span>
          </div>
          <input
            id="grid-resolution"
            type="number"
            step="0.1"
            min="0.1"
            max="5.0"
            className="text-input"
            value={scenario.grid_resolution ?? 1.0}
            onChange={e =>
              onUpdateScenario({
                ...scenario,
                grid_resolution: Math.max(0.1, Number(e.target.value) || 0.1),
              })
            }
            disabled={isOptimizing}
          />
          <span className="field-hint">~{estGridCells} celdas de muestreo estimadas.</span>
        </div>

        {/* 3. Section: ABC Metaheuristic Parameters */}
        <div className="accordion-section">
          <button
            type="button"
            className="accordion-header"
            onClick={() => toggleSection('meta')}
          >
            <div className="accordion-title-group">
              <Settings className="icon-xs text-gold" />
              <span>Hiperparámetros ABC</span>
            </div>
            {openSection === 'meta' ? <ChevronUp className="icon-xs" /> : <ChevronDown className="icon-xs" />}
          </button>

          {openSection === 'meta' && (
            <div className="accordion-content">
              {/* K cameras */}
              <div className="form-row">
                <div className="form-col">
                  <label htmlFor="cameras-k" className="input-label">
                    Cámaras (K):
                  </label>
                  <input
                    id="cameras-k"
                    type="number"
                    min="1"
                    max="20"
                    className="text-input"
                    value={config.K}
                    onChange={e =>
                      onUpdateConfig({
                        ...config,
                        K: Math.max(1, Math.min(30, parseInt(e.target.value, 10) || 1)),
                      })
                    }
                    disabled={isOptimizing}
                  />
                </div>

                {/* SN food sources */}
                <div className="form-col">
                  <label htmlFor="food-sources-sn" className="input-label">
                    Población (SN):
                  </label>
                  <input
                    id="food-sources-sn"
                    type="number"
                    min="2"
                    max="100"
                    className="text-input"
                    value={config.SN}
                    onChange={e =>
                      onUpdateConfig({
                        ...config,
                        SN: Math.max(2, Math.min(100, parseInt(e.target.value, 10) || 2)),
                      })
                    }
                    disabled={isOptimizing}
                  />
                </div>
              </div>

              {/* Max cycles & Limit */}
              <div className="form-row">
                <div className="form-col">
                  <label htmlFor="max-cycles" className="input-label">
                    Ciclos Máximos:
                  </label>
                  <input
                    id="max-cycles"
                    type="number"
                    min="1"
                    max="300"
                    className="text-input"
                    value={config.max_cycles}
                    onChange={e =>
                      onUpdateConfig({
                        ...config,
                        max_cycles: Math.max(1, Math.min(500, parseInt(e.target.value, 10) || 1)),
                      })
                    }
                    disabled={isOptimizing}
                  />
                </div>

                <div className="form-col">
                  <label htmlFor="limit-abandon" className="input-label">
                    Límite Scout:
                  </label>
                  <input
                    id="limit-abandon"
                    type="number"
                    min="1"
                    max="2000"
                    placeholder={`Auto (${config.SN * 3 * config.K})`}
                    className="text-input"
                    value={config.limit ?? ''}
                    onChange={e =>
                      onUpdateConfig({
                        ...config,
                        limit: e.target.value ? Math.max(1, parseInt(e.target.value, 10)) : null,
                      })
                    }
                    disabled={isOptimizing}
                  />
                </div>
              </div>

              {/* Seed */}
              <div className="form-group">
                <div className="input-label-row">
                  <label htmlFor="seed-input" className="input-label">
                    Semilla PRNG (Opcional):
                  </label>
                  <div className="seed-actions">
                    <button
                      type="button"
                      className="mini-btn"
                      onClick={handleRandomSeed}
                      disabled={isOptimizing}
                      title="Generar semilla aleatoria"
                    >
                      <RotateCw className="icon-xs" />
                      <span>Aleatoria</span>
                    </button>
                    {config.seed != null && (
                      <button
                        type="button"
                        className="mini-btn text-muted"
                        onClick={handleClearSeed}
                        disabled={isOptimizing}
                        title="Borrar semilla (generación automática)"
                      >
                        Limpiar
                      </button>
                    )}
                  </div>
                </div>
                <input
                  id="seed-input"
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  placeholder="Automática (secrets.randbits)"
                  className="text-input"
                  value={config.seed != null ? String(config.seed) : ''}
                  onChange={e => {
                    const raw = e.target.value.trim()
                    if (!raw) {
                      onUpdateConfig({
                        ...config,
                        seed: null,
                      })
                    } else if (/^\d+$/.test(raw)) {
                      onUpdateConfig({
                        ...config,
                        seed: raw,
                      })
                    }
                  }}
                  disabled={isOptimizing}
                />
              </div>

              {/* Record population toggle */}
              <div className="toggle-wrapper" onClick={() => !isOptimizing && onUpdateConfig({ ...config, record_population: !config.record_population })}>
                {config.record_population ? (
                  <CheckSquare className="icon-sm text-gold" />
                ) : (
                  <Square className="icon-sm text-muted" />
                )}
                <div className="toggle-label-group">
                  <span className="toggle-title">Grabar Historial Poblacional</span>
                  <span className="toggle-hint">
                    Instantáneas de las {config.SN} fuentes para inspección interactiva.
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 4. Section: Optical Camera Profile */}
        <div className="accordion-section">
          <button
            type="button"
            className="accordion-header"
            onClick={() => toggleSection('profile')}
          >
            <div className="accordion-title-group">
              <Camera className="icon-xs text-cyan" />
              <span>Perfil Óptico de Cámara</span>
            </div>
            {openSection === 'profile' ? <ChevronUp className="icon-xs" /> : <ChevronDown className="icon-xs" />}
          </button>

          {openSection === 'profile' && (
            <div className="accordion-content">
              {/* Rmin and Rmax */}
              <div className="form-row">
                <div className="form-col">
                  <label htmlFor="rmin" className="input-label">
                    Rmin (m):
                  </label>
                  <input
                    id="rmin"
                    type="number"
                    step="0.1"
                    min="0"
                    max={profile.Rmax - 0.1}
                    className="text-input"
                    value={profile.Rmin}
                    onChange={e =>
                      onUpdateProfile({
                        ...profile,
                        Rmin: Math.max(0, Number(e.target.value) || 0),
                      })
                    }
                    disabled={isOptimizing}
                  />
                </div>
                <div className="form-col">
                  <label htmlFor="rmax" className="input-label">
                    Rmax (m):
                  </label>
                  <input
                    id="rmax"
                    type="number"
                    step="0.5"
                    min={profile.Rmin + 0.1}
                    max="50"
                    className="text-input"
                    value={profile.Rmax}
                    onChange={e =>
                      onUpdateProfile({
                        ...profile,
                        Rmax: Math.max(profile.Rmin + 0.1, Number(e.target.value) || 10),
                      })
                    }
                    disabled={isOptimizing}
                  />
                </div>
              </div>

              {/* FOV Aperture */}
              <div className="form-group">
                <div className="input-label-row">
                  <label htmlFor={fovId} className="input-label">
                    Apertura Angular (FOV):
                  </label>
                  <span className="value-badge">{fovDegrees}° ({profile.FOV.toFixed(2)} rad)</span>
                </div>
                <input
                  id={fovId}
                  type="range"
                  min="30"
                  max="180"
                  step="5"
                  className="range-slider"
                  value={fovDegrees}
                  onChange={e => {
                    const deg = Number(e.target.value)
                    onUpdateProfile({
                      ...profile,
                      FOV: (deg * Math.PI) / 180,
                    })
                  }}
                  disabled={isOptimizing}
                />
              </div>

              {/* Decay exponents */}
              <div className="form-row">
                <div className="form-col">
                  <label htmlFor="beta-d" className="input-label">
                    β_dist:
                  </label>
                  <input
                    id="beta-d"
                    type="number"
                    step="0.05"
                    min="0"
                    max="5"
                    className="text-input"
                    value={profile.beta_d}
                    onChange={e =>
                      onUpdateProfile({
                        ...profile,
                        beta_d: Math.max(0, Number(e.target.value) || 0),
                      })
                    }
                    disabled={isOptimizing}
                  />
                </div>
                <div className="form-col">
                  <label htmlFor="beta-theta" className="input-label">
                    β_theta:
                  </label>
                  <input
                    id="beta-theta"
                    type="number"
                    step="0.05"
                    min="0"
                    max="5"
                    className="text-input"
                    value={profile.beta_theta}
                    onChange={e =>
                      onUpdateProfile({
                        ...profile,
                        beta_theta: Math.max(0, Number(e.target.value) || 0),
                      })
                    }
                    disabled={isOptimizing}
                  />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 5. Section: Objective Function Weights */}
        <div className="accordion-section">
          <button
            type="button"
            className="accordion-header"
            onClick={() => toggleSection('objective')}
          >
            <div className="accordion-title-group">
              <Shield className="icon-xs text-gold" />
              <span>Función Objetivo y Riesgo</span>
            </div>
            {openSection === 'objective' ? <ChevronUp className="icon-xs" /> : <ChevronDown className="icon-xs" />}
          </button>

          {openSection === 'objective' && (
            <div className="accordion-content">
              {/* Lambda Deficit Penalty */}
              <div className="form-group">
                <div className="input-label-row">
                  <label htmlFor="lambda-def" className="input-label">
                    Penalización Déficit Crítico (λ):
                  </label>
                  <span className="value-badge">{config.lambda_def.toFixed(2)}</span>
                </div>
                <input
                  id="lambda-def"
                  type="number"
                  step="0.25"
                  min="0"
                  max="10"
                  className="text-input"
                  value={config.lambda_def}
                  onChange={e =>
                    onUpdateConfig({
                      ...config,
                      lambda_def: Math.max(0, Number(e.target.value) || 0),
                    })
                  }
                  disabled={isOptimizing}
                />
              </div>

              {/* Tcrit threshold */}
              <div className="form-group">
                <div className="input-label-row">
                  <label htmlFor="t-crit" className="input-label">
                    Umbral Crítico Detección (Tcrit):
                  </label>
                  <span className="value-badge">{(config.Tcrit * 100).toFixed(0)}%</span>
                </div>
                <input
                  id="t-crit"
                  type="range"
                  min="0.1"
                  max="0.99"
                  step="0.05"
                  className="range-slider"
                  value={config.Tcrit}
                  onChange={e =>
                    onUpdateConfig({
                      ...config,
                      Tcrit: Math.max(0.01, Math.min(1.0, Number(e.target.value))),
                    })
                  }
                  disabled={isOptimizing}
                />
              </div>
            </div>
          )}
        </div>

        {/* Resource Budget Warning */}
        {isBudgetWarning && (
          <div className="budget-warning-banner">
            <AlertCircle className="icon-xs text-gold" />
            <span>
              Carga estimada alta (~{(estWork / 1e6).toFixed(1)}M ops). Puede demorar varios segundos.
            </span>
          </div>
        )}

        {/* Validation Result Banner */}
        {validationResult && (
          <div
            className={`validation-banner ${
              validationResult.is_valid ? 'validation-valid' : 'validation-invalid'
            }`}
          >
            <div className="validation-banner-header">
              {validationResult.is_valid ? (
                <>
                  <CheckCircle2 className="icon-xs text-success" />
                  <span>Escenario Válido para Optimización</span>
                </>
              ) : (
                <>
                  <AlertCircle className="icon-xs text-danger" />
                  <span>Errores de Validación Detectados</span>
                </>
              )}
            </div>

            {validationResult.errors.length > 0 && (
              <ul className="validation-error-list">
                {validationResult.errors.map((err, i) => (
                  <li key={i}>{err}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {/* Sidebar Action Buttons */}
      <div className="sidebar-actions">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={onValidate}
          disabled={isValidating || isOptimizing || serverConnected === false}
          title="Verificar geometría e hiperparámetros antes de ejecutar"
        >
          {isValidating ? (
            <RotateCw className="icon-sm icon-spin" />
          ) : (
            <Eye className="icon-sm" />
          )}
          <span>Validar Escenario</span>
        </button>

        <button
          type="button"
          className="btn btn-primary"
          onClick={onRunOptimization}
          disabled={isOptimizing || isValidating || serverConnected === false}
          title="Ejecutar algoritmo Artificial Bee Colony secuencial en el backend"
        >
          {isOptimizing ? (
            <>
              <Clock className="icon-sm icon-spin" />
              <span>Optimizando ({config.SN} fuentes)...</span>
            </>
          ) : (
            <>
              <Play className="icon-sm" />
              <span>Ejecutar Optimización ABC</span>
            </>
          )}
        </button>
      </div>
    </aside>
  )
}
