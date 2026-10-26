import React, { useEffect } from 'react'
import {
  ChevronLeft,
  ChevronRight,
  Info,
  Pause,
  Play,
  RotateCcw,
  Sparkles,
  Users,
} from 'lucide-react'
import type { FoodSource } from '../types/api'

interface PlaybackControlsProps {
  currentCycle: number
  totalCycles: number
  isPlaying: boolean
  playbackSpeed: number
  onTogglePlay: () => void
  onStepForward: () => void
  onStepBackward: () => void
  onReset: () => void
  onSetSpeed: (speed: number) => void
  onSeekCycle: (cycle: number) => void
  inspectionMode: 'best' | 'individual'
  onSetInspectionMode: (mode: 'best' | 'individual') => void
  selectedSourceIndex: number
  onSelectSourceIndex: (index: number) => void
  currentPopulation?: FoodSource[] | null
  populationAvailable: boolean
  disabled?: boolean
}

export const PlaybackControls: React.FC<PlaybackControlsProps> = ({
  currentCycle,
  totalCycles,
  isPlaying,
  playbackSpeed,
  onTogglePlay,
  onStepForward,
  onStepBackward,
  onReset,
  onSetSpeed,
  onSeekCycle,
  inspectionMode,
  onSetInspectionMode,
  selectedSourceIndex,
  onSelectSourceIndex,
  currentPopulation,
  populationAvailable,
  disabled = false,
}) => {
  // Keyboard navigation shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (disabled || totalCycles <= 1) return

      const target = e.target as HTMLElement | null
      if (target) {
        const tagName = target.tagName
        if (
          tagName === 'BUTTON' ||
          tagName === 'INPUT' ||
          tagName === 'SELECT' ||
          tagName === 'TEXTAREA' ||
          target.isContentEditable ||
          target.getAttribute('role') === 'button' ||
          target.getAttribute('role') === 'slider' ||
          target.getAttribute('role') === 'tab' ||
          target.getAttribute('role') === 'combobox' ||
          target.getAttribute('role') === 'menuitem'
        ) {
          return
        }
      }

      if (e.code === 'Space') {
        e.preventDefault()
        onTogglePlay()
      } else if (e.code === 'ArrowRight') {
        e.preventDefault()
        onStepForward()
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault()
        onStepBackward()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [disabled, totalCycles, onTogglePlay, onStepForward, onStepBackward])

  const maxIndex = Math.max(0, totalCycles - 1)
  const activeSource = currentPopulation && currentPopulation[selectedSourceIndex]

  return (
    <div className="playback-controls-card">
      {/* Top Bar: Play/Pause, Step, Speed, Scrubber */}
      <div className="playback-main-row">
        <div className="btn-group">
          <button
            type="button"
            className="ctrl-btn"
            onClick={onReset}
            disabled={disabled || currentCycle === 0}
            title="Reiniciar reproducción (Ciclo 0)"
          >
            <RotateCcw className="icon-sm" />
          </button>
          <button
            type="button"
            className="ctrl-btn"
            onClick={onStepBackward}
            disabled={disabled || currentCycle === 0}
            title="Ciclo anterior (Flecha Izquierda)"
          >
            <ChevronLeft className="icon-sm" />
          </button>
          <button
            type="button"
            className={`ctrl-btn ctrl-btn-primary ${isPlaying ? 'playing' : ''}`}
            onClick={onTogglePlay}
            disabled={disabled || totalCycles <= 1}
            title={isPlaying ? 'Pausar (Espacio)' : 'Reproducir (Espacio)'}
          >
            {isPlaying ? <Pause className="icon-sm" /> : <Play className="icon-sm" />}
          </button>
          <button
            type="button"
            className="ctrl-btn"
            onClick={onStepForward}
            disabled={disabled || currentCycle >= maxIndex}
            title="Ciclo siguiente (Flecha Derecha)"
          >
            <ChevronRight className="icon-sm" />
          </button>
        </div>

        {/* Scrubber slider */}
        <div className="scrubber-wrapper">
          <input
            type="range"
            min={0}
            max={maxIndex}
            value={currentCycle}
            onChange={e => onSeekCycle(Number(e.target.value))}
            disabled={disabled || totalCycles <= 1}
            className="scrubber-slider"
          />
          <div className="scrubber-label">
            <span>Ciclo <strong>{currentCycle}</strong> / {maxIndex}</span>
          </div>
        </div>

        {/* Speed multiplier selector */}
        <div className="speed-selector">
          {[1, 2, 5].map(spd => (
            <button
              key={spd}
              type="button"
              className={`speed-btn ${playbackSpeed === spd ? 'active' : ''}`}
              onClick={() => onSetSpeed(spd)}
              disabled={disabled}
            >
              {spd}x
            </button>
          ))}
        </div>
      </div>

      {/* Bottom Bar: Mode Toggle (Best vs Individual Food Source) */}
      <div className="playback-mode-row">
        <div className="mode-tabs">
          <button
            type="button"
            className={`mode-tab ${inspectionMode === 'best' ? 'active' : ''}`}
            onClick={() => onSetInspectionMode('best')}
            disabled={disabled}
          >
            <Sparkles className="icon-xs" />
            <span>Mejor Solución Histórica</span>
          </button>

          <button
            type="button"
            className={`mode-tab ${inspectionMode === 'individual' ? 'active' : ''}`}
            onClick={() => onSetInspectionMode('individual')}
            disabled={disabled || !populationAvailable}
            title={
              populationAvailable
                ? 'Inspeccionar una fuente de alimento individual de la población'
                : 'Historial poblacional no grabado para esta corrida'
            }
          >
            <Users className="icon-xs" />
            <span>Fuente Individual</span>
          </button>
        </div>

        {/* Source selector dropdown when in Individual mode */}
        {inspectionMode === 'individual' && populationAvailable && currentPopulation && (
          <div className="source-picker-group">
            <label htmlFor="source-select" className="source-label">
              Fuente:
            </label>
            <select
              id="source-select"
              value={selectedSourceIndex}
              onChange={e => onSelectSourceIndex(Number(e.target.value))}
              className="source-select"
            >
              {currentPopulation.map((src, i) => (
                <option key={i} value={i}>
                  Fuente #{i + 1} — f(X): {src.cost.toFixed(4)} (trial: {src.trial})
                </option>
              ))}
            </select>

            {activeSource && (
              <div className="source-stats-badge">
                <span>Costo: <strong>{activeSource.cost.toFixed(6)}</strong></span>
                <span>Fitness: <strong>{activeSource.fitness.toFixed(6)}</strong></span>
                <span>Trial: <strong className={activeSource.trial > 0 ? 'text-gold' : ''}>{activeSource.trial}</strong></span>
              </div>
            )}
          </div>
        )}

        {/* Informative notice if population history is not available */}
        {!populationAvailable && (
          <div className="pop-history-notice">
            <Info className="icon-xs text-muted" />
            <span>
              Historial poblacional no grabado. Active <em>"Grabar Historial Poblacional"</em> en la configuración para inspeccionar las SN fuentes.
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
