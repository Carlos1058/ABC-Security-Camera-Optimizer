import React, { useState } from 'react'
import {
  Activity,
  BarChart2,
  Film,
  Layers,
  X,
} from 'lucide-react'
import { ConvergenceChart } from './ConvergenceChart'
import { PlaybackControls } from './PlaybackControls'
import { ResultsPanel } from './ResultsPanel'
import type { CycleSnapshot, OptimizationResult } from '../types/api'

interface AnalysisDrawerProps {
  isOpen: boolean
  onClose: () => void
  result: OptimizationResult | null
  currentCycleIndex: number
  currentCycleCost?: number | null
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
  currentSnapshot?: CycleSnapshot
}

export const AnalysisDrawer: React.FC<AnalysisDrawerProps> = ({
  isOpen,
  onClose,
  result,
  currentCycleIndex,
  currentCycleCost,
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
  currentSnapshot,
}) => {
  const [activeTab, setActiveTab] = useState<'metrics' | 'convergence' | 'playback'>('metrics')

  if (!isOpen) return null

  return (
    <div className="drawer-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="drawer-analysis-title">
      <aside className="analysis-drawer" onClick={e => e.stopPropagation()}>
        <div className="drawer-header">
          <div className="drawer-title-group">
            <div className="drawer-icon-badge">
              <Activity className="icon-sm text-gold" />
            </div>
            <div>
              <h2 id="drawer-analysis-title" className="drawer-title">Análisis y Telemetría ABC</h2>
              <p className="drawer-subtitle">Resultados científicos, convergencia metaheurística y dinámica poblacional.</p>
            </div>
          </div>
          <button type="button" className="btn-icon-close" onClick={onClose} aria-label="Cerrar panel de análisis">
            <X className="icon-sm" />
          </button>
        </div>

        {/* Drawer Tabs */}
        <div className="drawer-tabs-bar" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'metrics'}
            className={`drawer-tab-btn ${activeTab === 'metrics' ? 'active' : ''}`}
            onClick={() => setActiveTab('metrics')}
          >
            <Layers className="icon-xs" />
            <span>Métricas</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'convergence'}
            className={`drawer-tab-btn ${activeTab === 'convergence' ? 'active' : ''}`}
            onClick={() => setActiveTab('convergence')}
          >
            <BarChart2 className="icon-xs" />
            <span>Convergencia</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'playback'}
            className={`drawer-tab-btn ${activeTab === 'playback' ? 'active' : ''}`}
            onClick={() => setActiveTab('playback')}
          >
            <Film className="icon-xs" />
            <span>Reproducción</span>
          </button>
        </div>

        <div className="drawer-body">
          {/* TAB 1: METRICS */}
          {activeTab === 'metrics' && (
            <div className="drawer-tab-pane">
              <ResultsPanel
                result={result}
                currentCycleCost={currentCycleCost}
                currentCycleIndex={currentCycleIndex}
              />
            </div>
          )}

          {/* TAB 2: CONVERGENCE */}
          {activeTab === 'convergence' && (
            <div className="drawer-tab-pane">
              <ConvergenceChart
                bestCosts={result?.best_cost_per_cycle ?? []}
                meanCosts={result?.mean_cost_per_cycle ?? []}
                currentCycle={currentCycleIndex}
                onSelectCycle={onSeekCycle}
                disabled={!result}
              />
            </div>
          )}

          {/* TAB 3: PLAYBACK */}
          {activeTab === 'playback' && (
            <div className="drawer-tab-pane">
              <PlaybackControls
                currentCycle={currentCycleIndex}
                totalCycles={result?.history.length ?? 0}
                isPlaying={isPlaying}
                playbackSpeed={playbackSpeed}
                onTogglePlay={onTogglePlay}
                onStepForward={onStepForward}
                onStepBackward={onStepBackward}
                onReset={onReset}
                onSetSpeed={onSetSpeed}
                onSeekCycle={onSeekCycle}
                inspectionMode={inspectionMode}
                onSetInspectionMode={onSetInspectionMode}
                selectedSourceIndex={selectedSourceIndex}
                onSelectSourceIndex={onSelectSourceIndex}
                currentPopulation={currentSnapshot?.population}
                populationAvailable={result?.population_history_available ?? false}
                disabled={!result}
              />
            </div>
          )}
        </div>
      </aside>
    </div>
  )
}
