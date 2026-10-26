import React, { useMemo, useState } from 'react'
import { TrendingDown } from 'lucide-react'

interface ConvergenceChartProps {
  bestCosts: number[]
  meanCosts: number[]
  currentCycle: number
  onSelectCycle: (cycle: number) => void
  disabled?: boolean
}

export const ConvergenceChart: React.FC<ConvergenceChartProps> = ({
  bestCosts,
  meanCosts,
  currentCycle,
  onSelectCycle,
  disabled = false,
}) => {
  const [hoveredCycle, setHoveredCycle] = useState<number | null>(null)

  const numCycles = Math.max(bestCosts.length, meanCosts.length)

  // Chart dimensions & margins
  const width = 640
  const height = 180
  const margin = { top: 20, right: 30, bottom: 28, left: 45 }
  const plotW = width - margin.left - margin.right
  const plotH = height - margin.top - margin.bottom

  const { minVal, maxVal, bestPoints, meanPoints, yTicks } = useMemo(() => {
    if (numCycles === 0) {
      return { minVal: 0, maxVal: 1, bestPoints: '', meanPoints: '', yTicks: [0, 0.5, 1.0] }
    }

    const allValues = [...bestCosts, ...meanCosts].filter(v => Number.isFinite(v))
    const rawMin = allValues.length > 0 ? Math.min(...allValues) : 0
    const rawMax = allValues.length > 0 ? Math.max(...allValues) : 1

    const padding = (rawMax - rawMin) * 0.08 || 0.1
    const minVal = Math.max(0, rawMin - padding)
    const maxVal = rawMax + padding

    const scaleX = (c: number) =>
      margin.left + (numCycles > 1 ? (c / (numCycles - 1)) * plotW : plotW / 2)
    const scaleY = (v: number) =>
      margin.top + plotH - ((v - minVal) / (maxVal - minVal)) * plotH

    const bestPoints = bestCosts
      .map((val, idx) => `${scaleX(idx).toFixed(1)},${scaleY(val).toFixed(1)}`)
      .join(' ')

    const meanPoints = meanCosts
      .map((val, idx) => `${scaleX(idx).toFixed(1)},${scaleY(val).toFixed(1)}`)
      .join(' ')

    const yTicks = [
      minVal,
      minVal + (maxVal - minVal) * 0.5,
      maxVal,
    ]

    return { minVal, maxVal, bestPoints, meanPoints, yTicks }
  }, [bestCosts, meanCosts, numCycles, plotW, plotH, margin.left, margin.top])

  if (numCycles === 0) {
    return (
      <div className="chart-empty-state">
        <TrendingDown className="icon-md text-muted" />
        <p>Ejecute una optimización para observar la curva de convergencia por ciclo.</p>
      </div>
    )
  }

  const getCycleFromX = (svgX: number): number => {
    const relX = svgX - margin.left
    const ratio = Math.max(0, Math.min(1, relX / plotW))
    return Math.round(ratio * (numCycles - 1))
  }

  const handlePointer = (e: React.PointerEvent<SVGSVGElement>) => {
    if (disabled || numCycles <= 1) return
    const rect = e.currentTarget.getBoundingClientRect()
    const svgX = ((e.clientX - rect.left) / rect.width) * width
    const cycle = getCycleFromX(svgX)
    setHoveredCycle(cycle)
  }

  const handleClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (disabled || numCycles <= 1) return
    const rect = e.currentTarget.getBoundingClientRect()
    const svgX = ((e.clientX - rect.left) / rect.width) * width
    const cycle = getCycleFromX(svgX)
    onSelectCycle(cycle)
  }

  const activeCycle = hoveredCycle ?? currentCycle
  const activeX =
    margin.left + (numCycles > 1 ? (activeCycle / (numCycles - 1)) * plotW : plotW / 2)
  const activeBestCost = bestCosts[activeCycle] ?? 0
  const activeMeanCost = meanCosts[activeCycle] ?? 0

  return (
    <div className="convergence-chart-card">
      <div className="chart-header">
        <div className="chart-title-group">
          <TrendingDown className="icon-sm text-gold" />
          <span className="chart-title">Curva de Convergencia ABC</span>
        </div>
        <div className="chart-legend">
          <div className="legend-item">
            <span className="legend-swatch swatch-gold" />
            <span>Mejor Costo Histórico: <strong>{activeBestCost.toFixed(6)}</strong></span>
          </div>
          {meanCosts.length > 0 && (
            <div className="legend-item">
              <span className="legend-swatch swatch-cyan" />
              <span>Promedio Población: <strong>{activeMeanCost.toFixed(6)}</strong></span>
            </div>
          )}
        </div>
      </div>

      <div className="svg-container">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="convergence-svg"
          onPointerMove={handlePointer}
          onPointerLeave={() => setHoveredCycle(null)}
          onClick={handleClick}
        >
          {/* Background grid */}
          {yTicks.map((tick, i) => {
            const y = margin.top + plotH - ((tick - minVal) / (maxVal - minVal)) * plotH
            return (
              <g key={i}>
                <line
                  x1={margin.left}
                  y1={y}
                  x2={width - margin.right}
                  y2={y}
                  stroke="rgba(255, 255, 255, 0.07)"
                  strokeDasharray="4 4"
                />
                <text
                  x={margin.left - 6}
                  y={y + 3}
                  textAnchor="end"
                  fontSize="10"
                  fill="#64748b"
                >
                  {tick.toFixed(2)}
                </text>
              </g>
            )
          })}

          {/* X Axis ticks */}
          <line
            x1={margin.left}
            y1={height - margin.bottom}
            x2={width - margin.right}
            y2={height - margin.bottom}
            stroke="rgba(255, 255, 255, 0.15)"
          />

          <text
            x={margin.left}
            y={height - margin.bottom + 16}
            textAnchor="middle"
            fontSize="10"
            fill="#64748b"
          >
            0
          </text>
          <text
            x={width - margin.right}
            y={height - margin.bottom + 16}
            textAnchor="middle"
            fontSize="10"
            fill="#64748b"
          >
            {numCycles - 1}
          </text>
          <text
            x={margin.left + plotW / 2}
            y={height - margin.bottom + 18}
            textAnchor="middle"
            fontSize="10"
            fill="#94a3b8"
          >
            Ciclo ABC
          </text>

          {/* Mean Population Cost Line (Cyan) */}
          {meanPoints && (
            <polyline
              fill="none"
              stroke="#38bdf8"
              strokeWidth="1.8"
              strokeOpacity="0.85"
              points={meanPoints}
            />
          )}

          {/* Best Solution Cost Line (Gold Amber) */}
          {bestPoints && (
            <polyline
              fill="none"
              stroke="#f59e0b"
              strokeWidth="2.4"
              points={bestPoints}
            />
          )}

          {/* Active Cycle Vertical Cursor */}
          <line
            x1={activeX}
            y1={margin.top}
            x2={activeX}
            y2={height - margin.bottom}
            stroke="#f59e0b"
            strokeWidth="1.5"
            strokeDasharray="3 3"
          />

          {/* Active Cycle Marker Dot */}
          {bestCosts[activeCycle] != null && (
            <circle
              cx={activeX}
              cy={margin.top + plotH - ((bestCosts[activeCycle] - minVal) / (maxVal - minVal)) * plotH}
              r="4.5"
              fill="#f59e0b"
              stroke="#ffffff"
              strokeWidth="1.5"
            />
          )}
        </svg>
      </div>
    </div>
  )
}
