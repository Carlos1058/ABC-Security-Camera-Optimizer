import React from 'react'
import {
  Activity,
  Minus,
  Play,
  Plus,
  RotateCw,
  SlidersHorizontal,
} from 'lucide-react'
import type { OptimizationResult } from '../types/api'

interface FloatingActionDockProps {
  cameraCount: number
  onChangeCameraCount: (k: number) => void
  onRunOptimization: () => void
  isOptimizing: boolean
  onOpenAdvancedConfig: () => void
  result: OptimizationResult | null
  onOpenAnalysis: () => void
  disabled?: boolean
}

export const FloatingActionDock: React.FC<FloatingActionDockProps> = ({
  cameraCount,
  onChangeCameraCount,
  onRunOptimization,
  isOptimizing,
  onOpenAdvancedConfig,
  result,
  onOpenAnalysis,
  disabled = false,
}) => {
  const handleDecrement = () => {
    if (cameraCount > 1 && !isOptimizing) {
      onChangeCameraCount(cameraCount - 1)
    }
  }

  const handleIncrement = () => {
    if (cameraCount < 20 && !isOptimizing) {
      onChangeCameraCount(cameraCount + 1)
    }
  }

  return (
    <div className="floating-action-dock" role="region" aria-label="Zona de optimización principal">
      {/* 1. Compact Camera Stepper */}
      <div className="dock-camera-stepper">
        <span className="stepper-label">Cámaras:</span>
        <div className="stepper-controls">
          <button
            type="button"
            className="stepper-btn"
            onClick={handleDecrement}
            disabled={cameraCount <= 1 || isOptimizing || disabled}
            aria-label="Disminuir cámaras"
          >
            <Minus className="icon-xxs" />
          </button>
          <span className="stepper-value" title={`Configurar ${cameraCount} cámaras`}>
            {cameraCount}
          </span>
          <button
            type="button"
            className="stepper-btn"
            onClick={handleIncrement}
            disabled={cameraCount >= 20 || isOptimizing || disabled}
            aria-label="Aumentar cámaras"
          >
            <Plus className="icon-xxs" />
          </button>
        </div>
      </div>

      {/* 2. Advanced Config Shortcut */}
      <button
        type="button"
        className="btn-dock-icon"
        onClick={onOpenAdvancedConfig}
        disabled={isOptimizing}
        title="Configuración avanzada de algoritmos y ópticas"
        aria-label="Abrir configuración avanzada"
      >
        <SlidersHorizontal className="icon-xs" />
      </button>

      {/* 3. Primary Yellow Action Button */}
      <button
        id="btn-optimize"
        type="button"
        className="btn-primary-yellow btn-optimize-main"
        onClick={onRunOptimization}
        disabled={isOptimizing || disabled}
      >
        {isOptimizing ? (
          <>
            <RotateCw className="icon-xs spin-animation" />
            <span>Optimizando...</span>
          </>
        ) : (
          <>
            <Play className="icon-xs fill-current" />
            <span>Optimizar</span>
          </>
        )}
      </button>

      {/* 4. Compact Post-Optimization Results Summary Pill */}
      {result && (
        <>
          <div className="dock-divider" />
          <div className="dock-results-pill" title="Resumen de la última optimización" aria-label="Resumen de optimización">
            <div className="dock-metric-item">
              <span className="metric-tag">Geom:</span>
              <strong className="metric-val">
                {result.coverage_metrics.geometric_coverage_percent.toFixed(1)}%
              </strong>
            </div>
            <div className="dock-metric-item">
              <span className="metric-tag">Riesgo:</span>
              <strong className="metric-val">
                {(result.coverage_metrics.risk_weighted_coverage * 100).toFixed(1)}%
              </strong>
            </div>
            <div className="dock-metric-item">
              <span className="metric-tag">Costo:</span>
              <strong className="metric-val">{result.final_best_cost.toFixed(4)}</strong>
            </div>
            <div className="dock-metric-item">
              <span className="metric-tag">Tiempo:</span>
              <strong className="metric-val">{result.execution_time_seconds.toFixed(2)}s</strong>
            </div>

            <button
              id="btn-open-analysis"
              type="button"
              className="btn-dock-analysis"
              onClick={onOpenAnalysis}
              title="Abrir panel completo de análisis, convergencia y reproducción"
            >
              <Activity className="icon-xs" />
              <span>Análisis</span>
            </button>
          </div>
        </>
      )}
    </div>
  )
}
