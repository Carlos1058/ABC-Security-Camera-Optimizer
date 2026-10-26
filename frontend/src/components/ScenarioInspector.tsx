import React from 'react'
import {
  Box,
  Eye,
  EyeOff,
  Flame,
  Maximize2,
  Minus,
  Trash2,
  X,
} from 'lucide-react'
import { pointDistance, polygonArea } from '../renderer/geometryValidation'
import type { Scenario } from '../types/api'
import type { EditorTool, SelectedObject } from '../types/editor'

interface ScenarioInspectorProps {
  scenario: Scenario
  onUpdateScenario: (newScenario: Scenario) => void
  selectedObject: SelectedObject | null
  activeTool: EditorTool
  onClose: () => void
}

export const ScenarioInspector: React.FC<ScenarioInspectorProps> = ({
  scenario,
  onUpdateScenario,
  selectedObject,
  activeTool,
  onClose,
}) => {
  // Requirement 2: Contextual inspector only appears when an object or boundary is selected
  if (!selectedObject && activeTool !== 'boundary') {
    return null
  }

  // 1. Boundary Inspector
  const isInspectingBoundary = activeTool === 'boundary'
  if (isInspectingBoundary) {
    const xmin = scenario.xmin ?? 0.0
    const xmax = scenario.xmax
    const ymin = scenario.ymin ?? 0.0
    const ymax = scenario.ymax
    const gridRes = scenario.grid_resolution ?? 0.5
    const width = xmax - xmin
    const height = ymax - ymin
    const area = width * height

    const handleBoundaryChange = (field: 'xmin' | 'xmax' | 'ymin' | 'ymax' | 'grid_resolution', val: number) => {
      onUpdateScenario({
        ...scenario,
        [field]: val,
      })
    }

    return (
      <div className="scenario-inspector">
        <div className="inspector-header">
          <div className="inspector-title">
            <Maximize2 size={16} className="title-icon" />
            <span>Dimensiones del Recinto</span>
          </div>
          {activeTool !== 'boundary' && (
            <button type="button" className="btn-close-inspector" onClick={onClose}>
              <X size={14} />
            </button>
          )}
        </div>

        <div className="inspector-body">
          <div className="inspector-field-grid">
            <div className="inspector-field">
              <label>X Mínimo (m)</label>
              <input
                id="prop-xmin"
                type="number"
                step="0.5"
                value={xmin}
                onChange={e => handleBoundaryChange('xmin', parseFloat(e.target.value) || 0)}
              />
            </div>
            <div className="inspector-field">
              <label>X Máximo (m)</label>
              <input
                id="prop-xmax"
                type="number"
                step="0.5"
                value={xmax}
                onChange={e => handleBoundaryChange('xmax', Math.max(xmin + 1, parseFloat(e.target.value) || 10))}
              />
            </div>
            <div className="inspector-field">
              <label>Y Mínimo (m)</label>
              <input
                id="prop-ymin"
                type="number"
                step="0.5"
                value={ymin}
                onChange={e => handleBoundaryChange('ymin', parseFloat(e.target.value) || 0)}
              />
            </div>
            <div className="inspector-field">
              <label>Y Máximo (m)</label>
              <input
                id="prop-ymax"
                type="number"
                step="0.5"
                value={ymax}
                onChange={e => handleBoundaryChange('ymax', Math.max(ymin + 1, parseFloat(e.target.value) || 10))}
              />
            </div>
          </div>

          <div className="inspector-field">
            <label>Resolución de Malla de Evaluación (m)</label>
            <input
              id="prop-grid-resolution"
              type="number"
              step="0.1"
              min="0.1"
              max="2.0"
              value={gridRes}
              onChange={e =>
                handleBoundaryChange('grid_resolution', Math.max(0.1, parseFloat(e.target.value) || 0.5))
              }
            />
          </div>

          <div className="inspector-stats">
            <div className="stat-pill">
              <span>Ancho:</span> <strong>{width.toFixed(2)} m</strong>
            </div>
            <div className="stat-pill">
              <span>Alto:</span> <strong>{height.toFixed(2)} m</strong>
            </div>
            <div className="stat-pill">
              <span>Área:</span> <strong>{area.toFixed(1)} m²</strong>
            </div>
            <div className="stat-pill">
              <span>Aspecto:</span> <strong>{(width / Math.max(0.01, height)).toFixed(2)}:1</strong>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (!selectedObject) return null

  // 2. Wall Inspector
  if (selectedObject.type === 'wall') {
    const walls = scenario.walls || []
    const wall = walls[selectedObject.index]
    if (!wall) return null

    const length = pointDistance(wall.start, wall.end)

    const handleUpdateWall = (updated: typeof wall) => {
      const next = [...walls]
      next[selectedObject.index] = updated
      onUpdateScenario({ ...scenario, walls: next })
    }

    const handleDeleteWall = () => {
      const next = walls.filter((_, i) => i !== selectedObject.index)
      onUpdateScenario({ ...scenario, walls: next })
      onClose()
    }

    return (
      <div className="scenario-inspector">
        <div className="inspector-header">
          <div className="inspector-title">
            <Minus size={16} className="title-icon" />
            <span>Pared #{selectedObject.index + 1}</span>
          </div>
          <button type="button" className="btn-close-inspector" onClick={onClose}>
            <X size={14} />
          </button>
        </div>

        <div className="inspector-body">
          <div className="inspector-stat-highlight">
            <span>Longitud Real:</span>
            <strong>{length.toFixed(2)} m</strong>
          </div>

          <div className="inspector-field-grid">
            <div className="inspector-field">
              <label>Inicio X (m)</label>
              <input
                type="number"
                step="0.25"
                value={wall.start.x}
                onChange={e =>
                  handleUpdateWall({
                    ...wall,
                    start: { ...wall.start, x: parseFloat(e.target.value) || 0 },
                  })
                }
              />
            </div>
            <div className="inspector-field">
              <label>Inicio Y (m)</label>
              <input
                type="number"
                step="0.25"
                value={wall.start.y}
                onChange={e =>
                  handleUpdateWall({
                    ...wall,
                    start: { ...wall.start, y: parseFloat(e.target.value) || 0 },
                  })
                }
              />
            </div>
            <div className="inspector-field">
              <label>Fin X (m)</label>
              <input
                type="number"
                step="0.25"
                value={wall.end.x}
                onChange={e =>
                  handleUpdateWall({
                    ...wall,
                    end: { ...wall.end, x: parseFloat(e.target.value) || 0 },
                  })
                }
              />
            </div>
            <div className="inspector-field">
              <label>Fin Y (m)</label>
              <input
                type="number"
                step="0.25"
                value={wall.end.y}
                onChange={e =>
                  handleUpdateWall({
                    ...wall,
                    end: { ...wall.end, y: parseFloat(e.target.value) || 0 },
                  })
                }
              />
            </div>
          </div>

          <div className="inspector-checkbox-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={wall.is_opaque !== false}
                onChange={e => handleUpdateWall({ ...wall, is_opaque: e.target.checked })}
              />
              {wall.is_opaque !== false ? (
                <span>
                  <EyeOff size={14} /> Opaca (Bloquea línea de visión)
                </span>
              ) : (
                <span>
                  <Eye size={14} /> Transparente (Vidrio / Mirador)
                </span>
              )}
            </label>
          </div>

          <button type="button" className="btn-delete-item" onClick={handleDeleteWall}>
            <Trash2 size={14} />
            <span>Eliminar Pared</span>
          </button>
        </div>
      </div>
    )
  }

  // 3. Obstacle Inspector
  if (selectedObject.type === 'obstacle') {
    const obstacles = scenario.obstacles || []
    const obs = obstacles[selectedObject.index]
    if (!obs) return null

    const area = Math.abs(polygonArea(obs.vertices))

    const handleUpdateVertex = (vIdx: number, coord: 'x' | 'y', val: number) => {
      const nextVertices = obs.vertices.map((v, i) => (i === vIdx ? { ...v, [coord]: val } : v))
      const nextObs = [...obstacles]
      nextObs[selectedObject.index] = { ...obs, vertices: nextVertices }
      onUpdateScenario({ ...scenario, obstacles: nextObs })
    }

    const handleDeleteObstacle = () => {
      const next = obstacles.filter((_, i) => i !== selectedObject.index)
      onUpdateScenario({ ...scenario, obstacles: next })
      onClose()
    }

    return (
      <div className="scenario-inspector">
        <div className="inspector-header">
          <div className="inspector-title">
            <Box size={16} className="title-icon" />
            <span>Obstáculo #{selectedObject.index + 1}</span>
          </div>
          <button type="button" className="btn-close-inspector" onClick={onClose}>
            <X size={14} />
          </button>
        </div>

        <div className="inspector-body">
          <div className="inspector-stat-highlight">
            <span>Área Poligonal:</span>
            <strong>{area.toFixed(2)} m²</strong>
          </div>

          <div className="vertices-header">Vértices ({obs.vertices.length})</div>
          <div className="vertices-list">
            {obs.vertices.map((v, vIdx) => (
              <div key={vIdx} className="vertex-row">
                <span className="vertex-num">V{vIdx + 1}</span>
                <input
                  type="number"
                  step="0.25"
                  value={v.x}
                  onChange={e => handleUpdateVertex(vIdx, 'x', parseFloat(e.target.value) || 0)}
                  placeholder="X"
                />
                <input
                  type="number"
                  step="0.25"
                  value={v.y}
                  onChange={e => handleUpdateVertex(vIdx, 'y', parseFloat(e.target.value) || 0)}
                  placeholder="Y"
                />
              </div>
            ))}
          </div>

          <button type="button" className="btn-delete-item" onClick={handleDeleteObstacle}>
            <Trash2 size={14} />
            <span>Eliminar Obstáculo</span>
          </button>
        </div>
      </div>
    )
  }

  // 4. Risk Zone Inspector
  if (selectedObject.type === 'risk_zone') {
    const riskZones = scenario.risk_zones || []
    const rz = riskZones[selectedObject.index]
    if (!rz) return null

    const area = Math.abs(polygonArea(rz.vertices))

    const handleUpdateRisk = (updated: Partial<typeof rz>) => {
      const next = [...riskZones]
      next[selectedObject.index] = { ...rz, ...updated }
      onUpdateScenario({ ...scenario, risk_zones: next })
    }

    const handleDeleteRisk = () => {
      const next = riskZones.filter((_, i) => i !== selectedObject.index)
      onUpdateScenario({ ...scenario, risk_zones: next })
      onClose()
    }

    return (
      <div className="scenario-inspector">
        <div className="inspector-header">
          <div className="inspector-title">
            <Flame size={16} className="title-icon icon-risk" />
            <span>Zona de Riesgo #{selectedObject.index + 1}</span>
          </div>
          <button type="button" className="btn-close-inspector" onClick={onClose}>
            <X size={14} />
          </button>
        </div>

        <div className="inspector-body">
          <div className="inspector-field">
            <label>Nombre / Etiqueta</label>
            <input
              id="prop-risk-name"
              type="text"
              value={rz.name || ''}
              onChange={e => handleUpdateRisk({ name: e.target.value })}
              placeholder="Ej. Servidores, Caja Fuerte"
            />
          </div>

          <div className="inspector-field">
            <div className="field-label-row">
              <label>Peso de Criticidad (w ≥ 1.0)</label>
              <strong>{rz.weight.toFixed(1)}×</strong>
            </div>
            <input
              id="prop-risk-weight-slider"
              type="range"
              min="1.0"
              max="10.0"
              step="0.5"
              value={rz.weight}
              onChange={e => handleUpdateRisk({ weight: parseFloat(e.target.value) || 1.0 })}
              className="weight-slider"
            />
            <input
              id="prop-risk-weight"
              type="number"
              min="1.0"
              max="50.0"
              step="0.5"
              value={rz.weight}
              onChange={e => handleUpdateRisk({ weight: Math.max(1.0, parseFloat(e.target.value) || 1.0) })}
            />
          </div>

          <div className="inspector-stat-highlight">
            <span>Área:</span>
            <strong>{area.toFixed(2)} m²</strong>
          </div>

          <div className="vertices-header">Vértices ({rz.vertices.length})</div>
          <div className="vertices-list">
            {rz.vertices.map((v, vIdx) => (
              <div key={vIdx} className="vertex-row">
                <span className="vertex-num">V{vIdx + 1}</span>
                <input
                  type="number"
                  step="0.25"
                  value={v.x}
                  onChange={e => {
                    const nextVertices = rz.vertices.map((pt, i) =>
                      i === vIdx ? { ...pt, x: parseFloat(e.target.value) || 0 } : pt
                    )
                    handleUpdateRisk({ vertices: nextVertices })
                  }}
                  placeholder="X"
                />
                <input
                  type="number"
                  step="0.25"
                  value={v.y}
                  onChange={e => {
                    const nextVertices = rz.vertices.map((pt, i) =>
                      i === vIdx ? { ...pt, y: parseFloat(e.target.value) || 0 } : pt
                    )
                    handleUpdateRisk({ vertices: nextVertices })
                  }}
                  placeholder="Y"
                />
              </div>
            ))}
          </div>

          <button type="button" className="btn-delete-item" onClick={handleDeleteRisk}>
            <Trash2 size={14} />
            <span>Eliminar Zona de Riesgo</span>
          </button>
        </div>
      </div>
    )
  }

  return null
}
