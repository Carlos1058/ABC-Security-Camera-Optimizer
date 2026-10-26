import React from 'react'
import {
  AlertTriangle,
  Box,
  Check,
  FolderOpen,
  Layers,
  X,
} from 'lucide-react'
import type { PredefinedScenarioItem } from '../types/api'

interface TemplatesModalProps {
  isOpen: boolean
  onClose: () => void
  templates: PredefinedScenarioItem[]
  selectedTemplateId?: string
  onSelectTemplate: (template: PredefinedScenarioItem) => void
}

const TEMPLATE_NAMES_ES: Record<string, string> = {
  partitioned_office: 'Oficina Compartimentada',
  l_shaped_warehouse: 'Almacén en Forma de L',
  art_gallery: 'Galería de Arte con Columnas',
  empty_warehouse: 'Nave Industrial Diáfana',
  complex_retail: 'Centro Comercial / Retail',
}

export const TemplatesModal: React.FC<TemplatesModalProps> = ({
  isOpen,
  onClose,
  templates,
  selectedTemplateId,
  onSelectTemplate,
}) => {
  if (!isOpen) return null

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="templates-title">
      <div className="modal-card modal-card-wide" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-group">
            <div className="modal-icon-badge">
              <FolderOpen className="icon-sm text-gold" />
            </div>
            <div>
              <h2 id="templates-title" className="modal-title">Plantillas de Escenarios</h2>
              <p className="modal-subtitle">Seleccione un escenario predefinido registrado en el backend.</p>
            </div>
          </div>
          <button type="button" className="btn-icon-close" onClick={onClose} aria-label="Cerrar modal">
            <X className="icon-sm" />
          </button>
        </div>

        <div className="modal-body">
          {templates.length === 0 ? (
            <div className="empty-templates-state">
              <p>No se encontraron plantillas disponibles en el servidor.</p>
            </div>
          ) : (
            <div className="templates-grid">
              {templates.map(tmpl => {
                const sc = tmpl.scenario
                const width = ((sc.xmax || 0) - (sc.xmin || 0)).toFixed(1)
                const height = ((sc.ymax || 0) - (sc.ymin || 0)).toFixed(1)
                const wallsCount = sc.walls?.length ?? 0
                const obstaclesCount = sc.obstacles?.length ?? 0
                const riskZonesCount = sc.risk_zones?.length ?? 0
                const isSelected = tmpl.id === selectedTemplateId
                const displayName = TEMPLATE_NAMES_ES[tmpl.id] || tmpl.name

                return (
                  <div
                    key={tmpl.id}
                    className={`template-card ${isSelected ? 'template-card-selected' : ''}`}
                    onClick={() => {
                      onSelectTemplate(tmpl)
                      onClose()
                    }}
                    role="button"
                    tabIndex={0}
                    onKeyDown={e => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        onSelectTemplate(tmpl)
                        onClose()
                      }
                    }}
                  >
                    <div className="template-card-header">
                      <h3 className="template-card-title">{displayName}</h3>
                      {isSelected && (
                        <span className="template-selected-badge" title="Plantilla activa">
                          <Check className="icon-xs" /> Activa
                        </span>
                      )}
                    </div>

                    <p className="template-card-desc">{tmpl.description}</p>

                    <div className="template-card-meta">
                      <div className="meta-tag" title="Dimensiones del recinto">
                        <span className="meta-tag-label">Dim:</span>
                        <strong className="meta-tag-value">{width} × {height} m</strong>
                      </div>

                      <div className="meta-badges-row">
                        <span className="spec-badge" title="Paredes interiores">
                          <Layers className="icon-xxs" /> {wallsCount} paredes
                        </span>
                        {obstaclesCount > 0 && (
                          <span className="spec-badge" title="Obstáculos sólidos">
                            <Box className="icon-xxs" /> {obstaclesCount} obst.
                          </span>
                        )}
                        {riskZonesCount > 0 && (
                          <span className="spec-badge text-gold" title="Zonas de riesgo">
                            <AlertTriangle className="icon-xxs" /> {riskZonesCount} riesgo
                          </span>
                        )}
                      </div>
                    </div>

                    <button
                      type="button"
                      className="btn-select-template"
                      onClick={e => {
                        e.stopPropagation()
                        onSelectTemplate(tmpl)
                        onClose()
                      }}
                    >
                      Cargar plantilla
                    </button>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
