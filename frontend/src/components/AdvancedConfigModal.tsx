import React, { useId, useState } from 'react'
import {
  Camera,
  CheckSquare,
  RotateCw,
  Settings2,
  Shield,
  Sliders,
  Square,
  X,
} from 'lucide-react'
import type { CameraProfile, OptimizationConfig, Scenario } from '../types/api'

interface AdvancedConfigModalProps {
  isOpen: boolean
  onClose: () => void
  config: OptimizationConfig
  onUpdateConfig: (config: OptimizationConfig) => void
  profile: CameraProfile
  onUpdateProfile: (profile: CameraProfile) => void
  scenario: Scenario
  onUpdateScenario: (scenario: Scenario) => void
  disabled?: boolean
}

export const AdvancedConfigModal: React.FC<AdvancedConfigModalProps> = ({
  isOpen,
  onClose,
  config,
  onUpdateConfig,
  profile,
  onUpdateProfile,
  scenario,
  onUpdateScenario,
  disabled = false,
}) => {
  const [activeTab, setActiveTab] = useState<'abc' | 'optical' | 'objective'>('abc')
  const fovId = useId()

  if (!isOpen) return null

  const fovDegrees = Math.round((profile.FOV * 180) / Math.PI)

  // Estimated resource calculations
  const roomW = (scenario.xmax ?? 20) - (scenario.xmin ?? 0)
  const roomH = (scenario.ymax ?? 15) - (scenario.ymin ?? 0)
  const res = scenario.grid_resolution ?? 1.0
  const estGridCells = Math.ceil(roomW / res) * Math.ceil(roomH / res)
  const estNFE = config.SN + 2 * config.SN * config.max_cycles + config.max_cycles
  const estWork = estNFE * config.K * estGridCells

  const handleRandomSeed = () => {
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
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="adv-config-title">
      <div className="modal-card modal-card-wide" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-group">
            <div className="modal-icon-badge">
              <Settings2 className="icon-sm text-gold" />
            </div>
            <div>
              <h2 id="adv-config-title" className="modal-title">Configuración Avanzada</h2>
              <p className="modal-subtitle">Hiperparámetros del optimizador ABC, modelo sensorial y función objetivo.</p>
            </div>
          </div>
          <button type="button" className="btn-icon-close" onClick={onClose} aria-label="Cerrar modal">
            <X className="icon-sm" />
          </button>
        </div>

        {/* Modal Navigation Tabs */}
        <div className="modal-tabs-bar" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'abc'}
            className={`modal-tab-btn ${activeTab === 'abc' ? 'active' : ''}`}
            onClick={() => setActiveTab('abc')}
          >
            <Sliders className="icon-xs" />
            <span>Motor ABC</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'optical'}
            className={`modal-tab-btn ${activeTab === 'optical' ? 'active' : ''}`}
            onClick={() => setActiveTab('optical')}
          >
            <Camera className="icon-xs" />
            <span>Perfil Óptico</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'objective'}
            className={`modal-tab-btn ${activeTab === 'objective' ? 'active' : ''}`}
            onClick={() => setActiveTab('objective')}
          >
            <Shield className="icon-xs" />
            <span>Objetivo y Malla</span>
          </button>
        </div>

        <div className="modal-body">
          {/* TAB 1: ABC ENGINE HYPERPARAMETERS */}
          {activeTab === 'abc' && (
            <div className="config-tab-pane">
              <div className="form-grid-2">
                <div className="form-group">
                  <label htmlFor="cfg-sn" className="form-label">
                    Fuentes de Alimento (SN)
                  </label>
                  <input
                    id="cfg-sn"
                    type="number"
                    min="2"
                    max="100"
                    value={config.SN}
                    onChange={e =>
                      onUpdateConfig({
                        ...config,
                        SN: Math.max(2, Math.min(100, parseInt(e.target.value, 10) || 2)),
                      })
                    }
                    className="form-input"
                    disabled={disabled}
                  />
                  <span className="form-hint">Población activa de soluciones (mitad de colonia).</span>
                </div>

                <div className="form-group">
                  <label htmlFor="cfg-max-cycles" className="form-label">
                    Ciclos Máximos (M)
                  </label>
                  <input
                    id="cfg-max-cycles"
                    type="number"
                    min="1"
                    max="500"
                    value={config.max_cycles}
                    onChange={e =>
                      onUpdateConfig({
                        ...config,
                        max_cycles: Math.max(1, Math.min(500, parseInt(e.target.value, 10) || 1)),
                      })
                    }
                    className="form-input"
                    disabled={disabled}
                  />
                  <span className="form-hint">Iteraciones completas del ciclo de abejas.</span>
                </div>
              </div>

              <div className="form-grid-2">
                <div className="form-group">
                  <label htmlFor="cfg-limit" className="form-label">
                    Límite de Abandono (Limit)
                  </label>
                  <input
                    id="cfg-limit"
                    type="number"
                    min="1"
                    max="2000"
                    placeholder={`Auto (${config.SN * 3 * config.K})`}
                    value={config.limit ?? ''}
                    onChange={e =>
                      onUpdateConfig({
                        ...config,
                        limit: e.target.value ? Math.max(1, parseInt(e.target.value, 10)) : null,
                      })
                    }
                    className="form-input"
                    disabled={disabled}
                  />
                  <span className="form-hint">Ensayos sin mejora antes de scout aleatorio.</span>
                </div>

                <div className="form-group">
                  <div className="label-with-action">
                    <label htmlFor="cfg-seed" className="form-label">
                      Semilla Pseudoaleatoria
                    </label>
                    <div className="seed-btn-group">
                      <button
                        type="button"
                        className="btn-tiny-action"
                        onClick={handleRandomSeed}
                        disabled={disabled}
                        title="Generar semilla aleatoria de 64 bits"
                      >
                        <RotateCw className="icon-xxs" /> Aleatoria
                      </button>
                      {config.seed != null && (
                        <button
                          type="button"
                          className="btn-tiny-action text-muted"
                          onClick={handleClearSeed}
                          disabled={disabled}
                        >
                          Limpiar
                        </button>
                      )}
                    </div>
                  </div>
                  <input
                    id="cfg-seed"
                    type="text"
                    inputMode="numeric"
                    placeholder="Automática (sin semilla fija)"
                    value={config.seed != null ? String(config.seed) : ''}
                    onChange={e => {
                      const val = e.target.value.trim()
                      if (!val) {
                        onUpdateConfig({ ...config, seed: null })
                      } else if (/^\d+$/.test(val)) {
                        onUpdateConfig({ ...config, seed: val })
                      }
                    }}
                    className="form-input"
                    disabled={disabled}
                  />
                  <span className="form-hint">Entero no negativo de 64 bits para reproducibilidad exacta.</span>
                </div>
              </div>

              <div
                className="config-toggle-card"
                onClick={() => !disabled && onUpdateConfig({ ...config, record_population: !config.record_population })}
              >
                {config.record_population ? (
                  <CheckSquare className="icon-sm text-gold" />
                ) : (
                  <Square className="icon-sm text-muted" />
                )}
                <div>
                  <div className="toggle-title">Registrar Historial de Población Completo</div>
                  <div className="toggle-subtitle">
                    Guarda las {config.SN} fuentes en cada ciclo para análisis y reproducción en el panel de telemetría.
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: OPTICAL PROFILE */}
          {activeTab === 'optical' && (
            <div className="config-tab-pane">
              <div className="form-grid-2">
                <div className="form-group">
                  <label htmlFor="opt-rmin" className="form-label">
                    Radio Mínimo R_min (m)
                  </label>
                  <input
                    id="opt-rmin"
                    type="number"
                    step="0.1"
                    min="0"
                    max={profile.Rmax - 0.1}
                    value={profile.Rmin}
                    onChange={e =>
                      onUpdateProfile({
                        ...profile,
                        Rmin: Math.max(0, Number(e.target.value) || 0),
                      })
                    }
                    className="form-input"
                    disabled={disabled}
                  />
                  <span className="form-hint">Punto ciego inmediato bajo la cámara.</span>
                </div>

                <div className="form-group">
                  <label htmlFor="opt-rmax" className="form-label">
                    Alcance Máximo R_max (m)
                  </label>
                  <input
                    id="opt-rmax"
                    type="number"
                    step="0.5"
                    min={profile.Rmin + 0.1}
                    max="100"
                    value={profile.Rmax}
                    onChange={e =>
                      onUpdateProfile({
                        ...profile,
                        Rmax: Math.max(profile.Rmin + 0.1, Number(e.target.value) || 10),
                      })
                    }
                    className="form-input"
                    disabled={disabled}
                  />
                  <span className="form-hint">Límite exterior de visión nominal.</span>
                </div>
              </div>

              <div className="form-group">
                <div className="label-with-badge">
                  <label htmlFor={fovId} className="form-label">
                    Campo de Visión Angular (FOV)
                  </label>
                  <span className="value-pill">{fovDegrees}° ({profile.FOV.toFixed(2)} rad)</span>
                </div>
                <input
                  id={fovId}
                  type="range"
                  min="30"
                  max="180"
                  step="5"
                  value={fovDegrees}
                  onChange={e => {
                    const deg = Number(e.target.value)
                    onUpdateProfile({
                      ...profile,
                      FOV: (deg * Math.PI) / 180,
                    })
                  }}
                  className="range-input"
                  disabled={disabled}
                />
                <span className="form-hint">Amplitud angular horizontal del lente.</span>
              </div>

              <div className="form-grid-3">
                <div className="form-group">
                  <label htmlFor="opt-p0" className="form-label">
                    Probabilidad Base p_0
                  </label>
                  <input
                    id="opt-p0"
                    type="number"
                    step="0.05"
                    min="0.1"
                    max="1.0"
                    value={profile.p0 ?? 1.0}
                    onChange={e =>
                      onUpdateProfile({
                        ...profile,
                        p0: Math.max(0.05, Math.min(1.0, Number(e.target.value) || 1.0)),
                      })
                    }
                    className="form-input"
                    disabled={disabled}
                  />
                  <span className="form-hint">Detección axial a distancia nula.</span>
                </div>

                <div className="form-group">
                  <label htmlFor="opt-betad" className="form-label">
                    Atenuación Radial β_dist
                  </label>
                  <input
                    id="opt-betad"
                    type="number"
                    step="0.05"
                    min="0.0"
                    max="5.0"
                    value={profile.beta_d}
                    onChange={e =>
                      onUpdateProfile({
                        ...profile,
                        beta_d: Math.max(0, Number(e.target.value) || 0),
                      })
                    }
                    className="form-input"
                    disabled={disabled}
                  />
                  <span className="form-hint">Caída exponencial por distancia.</span>
                </div>

                <div className="form-group">
                  <label htmlFor="opt-betatheta" className="form-label">
                    Atenuación Angular β_theta
                  </label>
                  <input
                    id="opt-betatheta"
                    type="number"
                    step="0.05"
                    min="0.0"
                    max="5.0"
                    value={profile.beta_theta}
                    onChange={e =>
                      onUpdateProfile({
                        ...profile,
                        beta_theta: Math.max(0, Number(e.target.value) || 0),
                      })
                    }
                    className="form-input"
                    disabled={disabled}
                  />
                  <span className="form-hint">Caída hacia los bordes del FOV.</span>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: OBJECTIVE FUNCTION & GRID */}
          {activeTab === 'objective' && (
            <div className="config-tab-pane">
              <div className="form-grid-2">
                <div className="form-group">
                  <label htmlFor="cfg-lambda" className="form-label">
                    Penalización Déficit Crítico (λ_def)
                  </label>
                  <input
                    id="cfg-lambda"
                    type="number"
                    step="0.25"
                    min="0"
                    max="10"
                    value={config.lambda_def}
                    onChange={e =>
                      onUpdateConfig({
                        ...config,
                        lambda_def: Math.max(0, Number(e.target.value) || 0),
                      })
                    }
                    className="form-input"
                    disabled={disabled}
                  />
                  <span className="form-hint">Multiplicador de penalización para puntos bajo el umbral crítico.</span>
                </div>

                <div className="form-group">
                  <div className="label-with-badge">
                    <label htmlFor="cfg-tcrit" className="form-label">
                      Umbral de Detección Crítica (T_crit)
                    </label>
                    <span className="value-pill">{Math.round(config.Tcrit * 100)}%</span>
                  </div>
                  <input
                    id="cfg-tcrit"
                    type="range"
                    min="0.1"
                    max="0.99"
                    step="0.05"
                    value={config.Tcrit}
                    onChange={e =>
                      onUpdateConfig({
                        ...config,
                        Tcrit: Math.max(0.01, Math.min(1.0, Number(e.target.value))),
                      })
                    }
                    className="range-input"
                    disabled={disabled}
                  />
                  <span className="form-hint">Probabilidad mínima requerida en zonas de alto riesgo.</span>
                </div>
              </div>

              <div className="form-group">
                <div className="label-with-badge">
                  <label htmlFor="cfg-resolution" className="form-label">
                    Resolución de Malla de Muestreo (m)
                  </label>
                  <span className="value-pill">{scenario.grid_resolution?.toFixed(2) ?? '1.00'} m</span>
                </div>
                <input
                  id="cfg-resolution"
                  type="number"
                  step="0.1"
                  min="0.1"
                  max="5.0"
                  value={scenario.grid_resolution ?? 1.0}
                  onChange={e =>
                    onUpdateScenario({
                      ...scenario,
                      grid_resolution: Math.max(0.1, Number(e.target.value) || 0.1),
                    })
                  }
                  className="form-input"
                  disabled={disabled}
                />
                <span className="form-hint">
                  Espaciado entre nodos de cálculo óptico (~{estGridCells} nodos en este recinto).
                </span>
              </div>

              <div className="telemetry-estimate-box">
                <div className="estimate-title">Estimación de Carga Computacional:</div>
                <div className="estimate-metrics-row">
                  <div>NFE Estimadas: <strong>~{estNFE.toLocaleString()}</strong></div>
                  <div>Celdas: <strong>~{estGridCells.toLocaleString()}</strong></div>
                  <div>Costo relativo: <strong>{estWork > 50_000_000 ? 'Alto' : 'Normal'}</strong></div>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="modal-actions">
          <button type="button" className="btn-primary-yellow" onClick={onClose}>
            Listo
          </button>
        </div>
      </div>
    </div>
  )
}
