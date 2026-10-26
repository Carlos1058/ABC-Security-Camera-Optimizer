import React, { useState } from 'react'
import {
  AlertTriangle,
  Award,
  Check,
  Copy,
  Cpu,
  Layers,
  Scale,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Zap,
} from 'lucide-react'
import type { OptimizationResult } from '../types/api'

interface ResultsPanelProps {
  result: OptimizationResult | null
  currentCycleCost?: number | null
  currentCycleIndex?: number | null
}

export const ResultsPanel: React.FC<ResultsPanelProps> = ({
  result,
  currentCycleCost,
  currentCycleIndex,
}) => {
  const [copiedSeed, setCopiedSeed] = useState(false)

  if (!result) {
    return (
      <div className="results-card empty-results">
        <Layers className="icon-md text-muted" />
        <h3>Resultados y Telemetría</h3>
        <p>Configure los parámetros y ejecute una optimización para visualizar las métricas oficiales.</p>
      </div>
    )
  }

  const {
    initial_best_cost,
    final_best_cost,
    coverage_metrics,
    total_evaluations,
    total_proposals,
    rejected_infeasible_proposals,
    total_scout_resets,
    execution_time_seconds,
    effective_seed,
    config,
  } = result

  const netImprovement = initial_best_cost - final_best_cost
  const percentImprovement =
    initial_best_cost > 0 ? (netImprovement / initial_best_cost) * 100 : 0

  // Mathematical identity verification
  const cRisk = coverage_metrics.risk_weighted_coverage
  const deficitCrit = coverage_metrics.critical_deficit
  const lambdaDef = config.lambda_def
  const expectedFinalCost = (1.0 - cRisk) + lambdaDef * deficitCrit
  const identityDelta = Math.abs(final_best_cost - expectedFinalCost)
  const isIdentityExact = identityDelta < 1e-9

  const handleCopySeed = async () => {
    try {
      await navigator.clipboard.writeText(effective_seed)
      setCopiedSeed(true)
      setTimeout(() => setCopiedSeed(false), 2000)
    } catch {
      // clipboard fallback
    }
  }

  return (
    <div className="results-card">
      <div className="results-header">
        <div className="results-title-group">
          <Award className="icon-sm text-gold" />
          <h2 className="results-title">Resultados de Optimización ABC</h2>
        </div>

        {/* Effective Seed Badge with Copy */}
        <div className="seed-badge-wrapper">
          <span className="seed-label">Semilla Efectiva:</span>
          <button
            type="button"
            className="seed-copy-btn"
            onClick={handleCopySeed}
            title="Copiar semilla reproducible al portapapeles"
          >
            <code>{effective_seed}</code>
            {copiedSeed ? (
              <Check className="icon-xs text-success" />
            ) : (
              <Copy className="icon-xs" />
            )}
          </button>
        </div>
      </div>

      {/* Main KPI Metric Grid */}
      <div className="kpi-grid">
        {/* Cost Card */}
        <div className="kpi-card cost-card">
          <div className="kpi-label">
            <Sparkles className="icon-xs text-gold" />
            <span>Función Objetivo f(X)</span>
          </div>
          <div className="kpi-main-val">
            {currentCycleCost != null && currentCycleIndex != null ? (
              <>
                <span className="val-primary">{currentCycleCost.toFixed(6)}</span>
                <span className="val-sub">Ciclo {currentCycleIndex}</span>
              </>
            ) : (
              <>
                <span className="val-primary">{final_best_cost.toFixed(6)}</span>
                <span className="val-sub">Final (Ciclo {result.best_cost_per_cycle.length - 1})</span>
              </>
            )}
          </div>
          <div className="kpi-footer">
            <span>Inicial: <strong>{initial_best_cost.toFixed(6)}</strong></span>
            <span className="improvement-pill">
              -{percentImprovement.toFixed(1)}%
            </span>
          </div>
        </div>

        {/* Geometric Coverage Card */}
        <div className="kpi-card">
          <div className="kpi-label">
            <ShieldCheck className="icon-xs text-cyan" />
            <span>Cobertura Geométrica</span>
          </div>
          <div className="kpi-main-val">
            <span className="val-primary">
              {coverage_metrics.geometric_coverage_percent.toFixed(1)}%
            </span>
            <span className="val-sub">
              {coverage_metrics.num_covered_points} / {coverage_metrics.num_eval_points} nodos
            </span>
          </div>
          <div className="kpi-footer">
            <span>Promedio Probabilístico:</span>
            <strong>{coverage_metrics.mean_probabilistic_coverage.toFixed(4)}</strong>
          </div>
        </div>

        {/* Risk-Weighted Coverage Card */}
        <div className="kpi-card">
          <div className="kpi-label">
            <ShieldAlert className="icon-xs text-gold" />
            <span>Cobertura Ponderada (C_risk)</span>
          </div>
          <div className="kpi-main-val">
            <span className="val-primary">
              {coverage_metrics.risk_weighted_coverage.toFixed(4)}
            </span>
            <span className="val-sub">con factores de riesgo</span>
          </div>
          <div className="kpi-footer">
            <span>Puntos críticos:</span>
            <strong>{coverage_metrics.num_critical_points}</strong>
          </div>
        </div>

        {/* Critical Deficit Card */}
        <div className="kpi-card">
          <div className="kpi-label">
            <AlertTriangle
              className={`icon-xs ${
                coverage_metrics.critical_deficit > 0 ? 'text-danger' : 'text-success'
              }`}
            />
            <span>Déficit Crítico</span>
          </div>
          <div className="kpi-main-val">
            <span
              className={`val-primary ${
                coverage_metrics.critical_deficit > 0 ? 'text-danger' : 'text-success'
              }`}
            >
              {coverage_metrics.critical_deficit.toFixed(4)}
            </span>
            <span className="val-sub">Umbral Tcrit = {config.Tcrit.toFixed(2)}</span>
          </div>
          <div className="kpi-footer">
            <span>Penalización λ:</span>
            <strong>{config.lambda_def.toFixed(2)}</strong>
          </div>
        </div>
      </div>

      {/* Effort & Telemetry Row */}
      <div className="telemetry-bar">
        <div className="telemetry-item">
          <Cpu className="icon-xs text-muted" />
          <span className="telemetry-label">Evaluaciones (NFE):</span>
          <span className="telemetry-val">{total_evaluations}</span>
        </div>

        <div className="telemetry-item">
          <Zap className="icon-xs text-muted" />
          <span className="telemetry-label">Propuestas Totales:</span>
          <span className="telemetry-val">{total_proposals}</span>
        </div>

        <div className="telemetry-item">
          <AlertTriangle className="icon-xs text-muted" />
          <span className="telemetry-label">Infactibles Rechazadas:</span>
          <span className="telemetry-val text-gold">{rejected_infeasible_proposals}</span>
        </div>

        <div className="telemetry-item">
          <Sparkles className="icon-xs text-muted" />
          <span className="telemetry-label">Resets Scout:</span>
          <span className="telemetry-val">{total_scout_resets}</span>
        </div>

        <div className="telemetry-item">
          <span className="telemetry-label">Tiempo de Cómputo:</span>
          <span className="telemetry-val text-cyan">{execution_time_seconds.toFixed(3)} s</span>
        </div>
      </div>

      {/* Mathematical Identity Verification Box */}
      <div className="identity-card">
        <div className="identity-header">
          <Scale className="icon-xs text-gold" />
          <span className="identity-title">Identidad Matemática Verificada</span>
          <span className={`identity-badge ${isIdentityExact ? 'exact' : 'mismatch'}`}>
            {isIdentityExact ? 'Exacta (Δ = 0.00)' : `Discrepancia Δ = ${identityDelta.toExponential(2)}`}
          </span>
        </div>
        <div className="identity-formula">
          <code>
            f(X) = (1 - C_risk) + λ_def × Deficit_crit = (1 - {cRisk.toFixed(4)}) + {lambdaDef.toFixed(2)} × {deficitCrit.toFixed(4)} = {expectedFinalCost.toFixed(6)}
          </code>
        </div>
      </div>

      <div className="results-disclaimer">
        <span>
          * Nota: Las métricas detalladas de cobertura geométrica y déficit corresponden a la configuración óptima final devuelta por el evaluador de la API.
        </span>
      </div>
    </div>
  )
}
