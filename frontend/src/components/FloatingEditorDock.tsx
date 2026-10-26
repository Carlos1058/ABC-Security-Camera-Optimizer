import React, { useState } from 'react'
import {
  AlertTriangle,
  Box,
  Check,
  DoorOpen,
  Magnet,
  Minus,
  MousePointer,
  Redo2,
  Trash2,
  Undo2,
  X,
} from 'lucide-react'
import type { EditorTool, SelectedObject } from '../types/editor'

interface FloatingEditorDockProps {
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
  draftPointsCount: number
  onFinishPolygon?: () => void
  onCancelDraft?: () => void
}

export const FloatingEditorDock: React.FC<FloatingEditorDockProps> = ({
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
  draftPointsCount,
  onFinishPolygon,
  onCancelDraft,
}) => {
  const [showSnapMenu, setShowSnapMenu] = useState(false)

  return (
    <div className="floating-editor-dock-container">
      {/* Primary Floating Toolbar */}
      <div className="floating-dock-bar" role="toolbar" aria-label="Herramientas del editor">
        {/* Tool: Seleccionar */}
        <button
          id="tool-select"
          type="button"
          className={`dock-btn ${activeTool === 'select' ? 'active' : ''}`}
          onClick={() => onChangeTool('select')}
          title="Seleccionar elemento (S)"
          aria-label="Herramienta Seleccionar"
        >
          <MousePointer className="icon-xs" />
          <span className="dock-btn-text">Seleccionar</span>
        </button>

        {/* Tool: Pared */}
        <button
          id="tool-wall"
          type="button"
          className={`dock-btn ${activeTool === 'wall' ? 'active' : ''}`}
          onClick={() => onChangeTool('wall')}
          title="Dibujar pared interior (W) — 2 clics"
          aria-label="Herramienta Pared"
        >
          <Minus className="icon-xs stroke-2" />
          <span className="dock-btn-text">Pared</span>
        </button>

        {/* Tool: Abertura / Puerta */}
        <button
          id="tool-door"
          type="button"
          className={`dock-btn ${activeTool === 'door' ? 'active' : ''}`}
          onClick={() => onChangeTool('door')}
          title="Crear abertura o puerta en una pared existente (D)"
          aria-label="Herramienta Abertura"
        >
          <DoorOpen className="icon-xs" />
          <span className="dock-btn-text">Abertura</span>
        </button>

        {/* Tool: Obstáculo */}
        <button
          id="tool-obstacle"
          type="button"
          className={`dock-btn ${activeTool === 'obstacle' ? 'active' : ''}`}
          onClick={() => onChangeTool('obstacle')}
          title="Dibujar obstáculo poligonal sólido (O) — ≥3 clics"
          aria-label="Herramienta Obstáculo"
        >
          <Box className="icon-xs" />
          <span className="dock-btn-text">Obstáculo</span>
        </button>

        {/* Tool: Zona de Riesgo */}
        <button
          id="tool-risk"
          type="button"
          className={`dock-btn ${activeTool === 'risk_zone' ? 'active' : ''}`}
          onClick={() => onChangeTool('risk_zone')}
          title="Dibujar zona de riesgo prioritario (R) — ≥3 clics"
          aria-label="Herramienta Zona de Riesgo"
        >
          <AlertTriangle className="icon-xs" />
          <span className="dock-btn-text">Zona Riesgo</span>
        </button>

        <div className="dock-divider" />

        {/* Quick action: Undo */}
        <button
          type="button"
          className="dock-icon-btn"
          onClick={onUndo}
          disabled={!canUndo}
          title="Deshacer (Ctrl+Z)"
          aria-label="Deshacer"
        >
          <Undo2 className="icon-xs" />
        </button>

        {/* Quick action: Redo */}
        <button
          type="button"
          className="dock-icon-btn"
          onClick={onRedo}
          disabled={!canRedo}
          title="Rehacer (Ctrl+Y)"
          aria-label="Rehacer"
        >
          <Redo2 className="icon-xs" />
        </button>

        {/* Quick action: Delete selected */}
        <button
          type="button"
          className={`dock-icon-btn ${selectedObject ? 'text-danger' : ''}`}
          onClick={onDeleteSelected}
          disabled={!selectedObject}
          title={selectedObject ? 'Eliminar elemento seleccionado (Supr / Backspace)' : 'Seleccione un objeto para eliminar'}
          aria-label="Eliminar seleccionado"
        >
          <Trash2 className="icon-xs" />
        </button>

        <div className="dock-divider" />

        {/* Snap to grid with dropdown */}
        <div className="dock-snap-wrapper">
          <button
            type="button"
            className={`dock-icon-btn ${snapToGrid ? 'active text-gold' : ''}`}
            onClick={onToggleSnap}
            title={snapToGrid ? `Snap a rejilla activado (${snapSize}m)` : 'Snap desactivado'}
            aria-label="Alternar snap a rejilla"
          >
            <Magnet className="icon-xs" />
          </button>
          <button
            type="button"
            className="dock-snap-size-btn"
            onClick={() => setShowSnapMenu(prev => !prev)}
            title="Cambiar paso de rejilla"
          >
            <span>{snapSize}m</span>
          </button>

          {showSnapMenu && (
            <div className="dock-popover-menu" onClick={() => setShowSnapMenu(false)}>
              {[0.1, 0.25, 0.5, 1.0].map(sz => (
                <button
                  key={sz}
                  type="button"
                  className={`dock-popover-item ${snapSize === sz ? 'active' : ''}`}
                  onClick={() => onChangeSnapSize(sz)}
                >
                  {sz} metro{sz !== 1 ? 's' : ''}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Door width input if door tool active */}
        {activeTool === 'door' && (
          <>
            <div className="dock-divider" />
            <div className="dock-inline-input" title="Ancho de la abertura">
              <span className="dock-input-label">Ancho:</span>
              <input
                type="number"
                min="0.5"
                max="5.0"
                step="0.1"
                value={doorWidth}
                onChange={e => onChangeDoorWidth(Math.max(0.2, Number(e.target.value) || 1.0))}
                className="dock-number-field"
              />
              <span className="dock-input-suffix">m</span>
            </div>
          </>
        )}
      </div>

      {/* Draft Polygon Floating Status Banner */}
      {draftPointsCount > 0 && (
        <div className="draft-polygon-pill">
          <span className="draft-count-text">
            Polígono en curso: <strong>{draftPointsCount}</strong> punto{draftPointsCount > 1 ? 's' : ''}
          </span>
          <div className="draft-actions">
            {draftPointsCount >= 3 && onFinishPolygon && (
              <button
                type="button"
                className="btn-finish-draft"
                onClick={onFinishPolygon}
                title="Cerrar y guardar polígono (Intro)"
              >
                <Check className="icon-xs" />
                <span>Completar</span>
              </button>
            )}
            {onCancelDraft && (
              <button
                type="button"
                className="btn-cancel-draft"
                onClick={onCancelDraft}
                title="Cancelar dibujo (Escape)"
              >
                <X className="icon-xs" />
                <span>Cancelar</span>
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
