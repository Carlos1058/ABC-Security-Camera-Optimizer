import React, { useState } from 'react'
import { ChevronDown, ChevronUp, Maximize, X } from 'lucide-react'
import type { Scenario } from '../types/api'

interface NewScenarioModalProps {
  isOpen: boolean
  onClose: () => void
  onCreateScenario: (scenario: Scenario) => void
}

export const NewScenarioModal: React.FC<NewScenarioModalProps> = ({
  isOpen,
  onClose,
  onCreateScenario,
}) => {
  const [width, setWidth] = useState<number>(20.0)
  const [height, setHeight] = useState<number>(15.0)
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false)
  const [originX, setOriginX] = useState<number>(0.0)
  const [originY, setOriginY] = useState<number>(0.0)
  const [gridResolution, setGridResolution] = useState<number>(1.0)
  const [error, setError] = useState<string | null>(null)

  if (!isOpen) return null

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    if (isNaN(width) || width <= 1.0) {
      setError('El ancho debe ser mayor a 1.0 metro.')
      return
    }
    if (isNaN(height) || height <= 1.0) {
      setError('El alto debe ser mayor a 1.0 metro.')
      return
    }
    if (isNaN(gridResolution) || gridResolution <= 0.05) {
      setError('La resolución de malla debe ser de al menos 0.05 m.')
      return
    }

    const newScenario: Scenario = {
      xmin: originX,
      xmax: originX + width,
      ymin: originY,
      ymax: originY + height,
      walls: [],
      obstacles: [],
      risk_zones: [],
      grid_resolution: gridResolution,
    }

    setError(null)
    onCreateScenario(newScenario)
    onClose()
  }

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="new-scenario-title">
      <div className="modal-card" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-group">
            <div className="modal-icon-badge">
              <Maximize className="icon-sm text-gold" />
            </div>
            <div>
              <h2 id="new-scenario-title" className="modal-title">Nuevo Escenario</h2>
              <p className="modal-subtitle">Configure las dimensiones del recinto rectangular para comenzar.</p>
            </div>
          </div>
          <button type="button" className="btn-icon-close" onClick={onClose} aria-label="Cerrar modal">
            <X className="icon-sm" />
          </button>
        </div>

        <form onSubmit={handleCreate} className="modal-body">
          {error && <div className="modal-error-banner">{error}</div>}

          <div className="form-grid-2">
            <div className="form-group">
              <label htmlFor="new-width" className="form-label">
                Ancho (m)
              </label>
              <input
                id="new-width"
                type="number"
                min="2.0"
                max="200.0"
                step="0.5"
                value={width}
                onChange={e => setWidth(parseFloat(e.target.value))}
                className="form-input"
                required
                autoFocus
              />
              <span className="form-hint">Dimensión en el eje X</span>
            </div>

            <div className="form-group">
              <label htmlFor="new-height" className="form-label">
                Alto (m)
              </label>
              <input
                id="new-height"
                type="number"
                min="2.0"
                max="200.0"
                step="0.5"
                value={height}
                onChange={e => setHeight(parseFloat(e.target.value))}
                className="form-input"
                required
              />
              <span className="form-hint">Dimensión en el eje Y</span>
            </div>
          </div>

          <div className="advanced-toggle-section">
            <button
              type="button"
              className="btn-toggle-advanced"
              onClick={() => setShowAdvanced(prev => !prev)}
            >
              <span>Opciones avanzadas</span>
              {showAdvanced ? <ChevronUp className="icon-xs" /> : <ChevronDown className="icon-xs" />}
            </button>

            {showAdvanced && (
              <div className="advanced-fields-box">
                <div className="form-grid-3">
                  <div className="form-group">
                    <label htmlFor="new-origin-x" className="form-label">
                      Origen X (m)
                    </label>
                    <input
                      id="new-origin-x"
                      type="number"
                      step="0.5"
                      value={originX}
                      onChange={e => setOriginX(parseFloat(e.target.value) || 0)}
                      className="form-input"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="new-origin-y" className="form-label">
                      Origen Y (m)
                    </label>
                    <input
                      id="new-origin-y"
                      type="number"
                      step="0.5"
                      value={originY}
                      onChange={e => setOriginY(parseFloat(e.target.value) || 0)}
                      className="form-input"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="new-grid-res" className="form-label">
                      Malla (m)
                    </label>
                    <input
                      id="new-grid-res"
                      type="number"
                      min="0.1"
                      max="5.0"
                      step="0.1"
                      value={gridResolution}
                      onChange={e => setGridResolution(parseFloat(e.target.value) || 1.0)}
                      className="form-input"
                    />
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancelar
            </button>
            <button type="submit" className="btn-primary-yellow">
              Crear Escenario
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
