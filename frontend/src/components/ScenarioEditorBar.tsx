import React, { useRef } from 'react'
import {
  Box,
  CheckCircle2,
  DoorOpen,
  Download,
  Flame,
  Grid,
  Magnet,
  Maximize2,
  Minus,
  MousePointer,
  Redo2,
  Trash2,
  Undo2,
  Upload,
} from 'lucide-react'
import type { EditorTool, SelectedObject } from '../types/editor'

interface ScenarioEditorBarProps {
  activeTool: EditorTool
  onChangeTool: (tool: EditorTool) => void
  snapToGrid: boolean
  onToggleSnap: () => void
  snapSize: number
  onChangeSnapSize: (size: number) => void
  doorWidth: number
  onChangeDoorWidth: (width: number) => void
  canUndo: boolean
  canRedo: boolean
  onUndo: () => void
  onRedo: () => void
  selectedObject: SelectedObject | null
  onDeleteSelected: () => void
  onExportJson: () => void
  onImportJson: (file: File) => void
  onValidate: () => void
  mouseCoords: { x: number; y: number } | null
  draftPointsCount: number
  onFinishPolygon?: () => void
  onCancelDraft?: () => void
}

export const ScenarioEditorBar: React.FC<ScenarioEditorBarProps> = ({
  activeTool,
  onChangeTool,
  snapToGrid,
  onToggleSnap,
  snapSize,
  onChangeSnapSize,
  doorWidth,
  onChangeDoorWidth,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  selectedObject,
  onDeleteSelected,
  onExportJson,
  onImportJson,
  onValidate,
  mouseCoords,
  draftPointsCount,
  onFinishPolygon,
  onCancelDraft,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      onImportJson(file)
    }
    // reset input so the same file can be reloaded if needed
    if (e.target) e.target.value = ''
  }

  return (
    <div className="scenario-editor-bar">
      {/* Tool Selection Group */}
      <div className="editor-group tools-group">
        <span className="editor-group-label">Herramientas</span>
        <div className="editor-btn-group">
          <button
            id="tool-select"
            type="button"
            className={`editor-btn ${activeTool === 'select' ? 'active' : ''}`}
            onClick={() => onChangeTool('select')}
            title="Seleccionar y modificar objetos existentes (S)"
          >
            <MousePointer size={16} />
            <span>Seleccionar</span>
          </button>

          <button
            id="tool-wall"
            type="button"
            className={`editor-btn ${activeTool === 'wall' ? 'active' : ''}`}
            onClick={() => onChangeTool('wall')}
            title="Dibujar pared interior mediante 2 clics (W)"
          >
            <Minus size={16} />
            <span>Pared</span>
          </button>

          <button
            id="tool-door"
            type="button"
            className={`editor-btn ${activeTool === 'door' ? 'active' : ''}`}
            onClick={() => onChangeTool('door')}
            title="Crear abertura / puerta sobre una pared existente (D)"
          >
            <DoorOpen size={16} />
            <span>Abertura</span>
          </button>

          <button
            id="tool-obstacle"
            type="button"
            className={`editor-btn ${activeTool === 'obstacle' ? 'active' : ''}`}
            onClick={() => onChangeTool('obstacle')}
            title="Dibujar obstáculo poligonal sólido (O)"
          >
            <Box size={16} />
            <span>Obstáculo</span>
          </button>

          <button
            id="tool-risk-zone"
            type="button"
            className={`editor-btn ${activeTool === 'risk_zone' ? 'active' : ''}`}
            onClick={() => onChangeTool('risk_zone')}
            title="Dibujar zona de riesgo prioritario (R)"
          >
            <Flame size={16} />
            <span>Zona Riesgo</span>
          </button>

          <button
            id="tool-boundary"
            type="button"
            className={`editor-btn ${activeTool === 'boundary' ? 'active' : ''}`}
            onClick={() => onChangeTool('boundary')}
            title="Configurar dimensiones y origen del recinto (B)"
          >
            <Maximize2 size={16} />
            <span>Recinto</span>
          </button>
        </div>
      </div>

      {/* Precision & Snapping Controls */}
      <div className="editor-group precision-group">
        <span className="editor-group-label">Precisión</span>
        <div className="editor-btn-group">
          <button
            id="btn-snap"
            type="button"
            className={`editor-btn ${snapToGrid ? 'active snap-active' : ''}`}
            onClick={onToggleSnap}
            title="Ajustar automáticamente a la cuadrícula métrica (G)"
          >
            <Magnet size={15} />
            <span>Snap</span>
          </button>

          <select
            id="select-snap-size"
            className="editor-select"
            value={snapSize}
            onChange={e => onChangeSnapSize(parseFloat(e.target.value))}
            title="Paso de la cuadrícula de ajuste"
          >
            <option value={0.1}>0.10 m</option>
            <option value={0.25}>0.25 m</option>
            <option value={0.5}>0.50 m</option>
            <option value={1.0}>1.00 m</option>
          </select>

          {activeTool === 'door' && (
            <div className="door-width-control" title="Ancho de la abertura">
              <span className="door-label">Ancho:</span>
              <input
                id="input-door-width"
                type="number"
                step="0.1"
                min="0.5"
                max="5.0"
                value={doorWidth}
                onChange={e => onChangeDoorWidth(Math.max(0.4, parseFloat(e.target.value) || 1.0))}
                className="door-input"
              />
              <span className="door-unit">m</span>
            </div>
          )}
        </div>
      </div>

      {/* Draft In-Progress Actions */}
      {draftPointsCount > 0 && (
        <div className="editor-group draft-actions">
          <span className="editor-group-label">Dibujo en curso ({draftPointsCount} pts)</span>
          <div className="editor-btn-group">
            {draftPointsCount >= 3 && onFinishPolygon && (
              <button
                id="btn-finish-polygon"
                type="button"
                className="editor-btn btn-finish-poly"
                onClick={onFinishPolygon}
                title="Cerrar el polígono actual"
              >
                <CheckCircle2 size={15} />
                <span>Cerrar Polígono</span>
              </button>
            )}
            {onCancelDraft && (
              <button
                id="btn-cancel-draft"
                type="button"
                className="editor-btn btn-cancel-draft"
                onClick={onCancelDraft}
                title="Cancelar dibujo actual (Esc)"
              >
                <span>Cancelar (Esc)</span>
              </button>
            )}
          </div>
        </div>
      )}

      {/* History & Deletion */}
      <div className="editor-group history-group">
        <span className="editor-group-label">Edición</span>
        <div className="editor-btn-group">
          <button
            id="btn-undo"
            type="button"
            className="editor-btn"
            disabled={!canUndo}
            onClick={onUndo}
            title="Deshacer última acción (Ctrl+Z / Cmd+Z)"
          >
            <Undo2 size={15} />
            <span>Deshacer</span>
          </button>

          <button
            id="btn-redo"
            type="button"
            className="editor-btn"
            disabled={!canRedo}
            onClick={onRedo}
            title="Rehacer acción (Ctrl+Y / Cmd+Shift+Z)"
          >
            <Redo2 size={15} />
            <span>Rehacer</span>
          </button>

          <button
            id="btn-delete-selected"
            type="button"
            className="editor-btn btn-danger"
            disabled={!selectedObject}
            onClick={onDeleteSelected}
            title="Eliminar objeto seleccionado (Supr / Delete)"
          >
            <Trash2 size={15} />
            <span>Eliminar</span>
          </button>
        </div>
      </div>

      {/* Import / Export / Validate */}
      <div className="editor-group io-group">
        <span className="editor-group-label">Escenario</span>
        <div className="editor-btn-group">
          <button
            id="btn-export-scenario"
            type="button"
            className="editor-btn"
            onClick={onExportJson}
            title="Exportar escenario como archivo JSON auténtico"
          >
            <Download size={15} />
            <span>Exportar</span>
          </button>

          <button
            id="btn-import-scenario"
            type="button"
            className="editor-btn"
            onClick={() => fileInputRef.current?.click()}
            title="Importar escenario desde archivo JSON"
          >
            <Upload size={15} />
            <span>Importar</span>
          </button>
          <input
            id="file-input-scenario"
            ref={fileInputRef}
            type="file"
            accept=".json,application/json"
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />

          <button
            id="btn-validate-scenario"
            type="button"
            className="editor-btn btn-validate"
            onClick={onValidate}
            title="Validar geometría directamente contra el backend FastAPI"
          >
            <CheckCircle2 size={15} />
            <span>Validar</span>
          </button>
        </div>
      </div>

      {/* Real-time Cursor Coordinates Readout */}
      <div className="editor-coords-badge" title="Coordenadas físicas actuales del cursor">
        <Grid size={13} className="coords-icon" />
        {mouseCoords ? (
          <span>
            X: <strong>{mouseCoords.x.toFixed(2)}</strong> m &nbsp;|&nbsp; Y:{' '}
            <strong>{mouseCoords.y.toFixed(2)}</strong> m
          </span>
        ) : (
          <span className="coords-inactive">Cursor fuera del lienzo</span>
        )}
      </div>
    </div>
  )
}
