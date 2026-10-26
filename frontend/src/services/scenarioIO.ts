/**
 * Import and Export services for ScenarioDTO payloads.
 *
 * Guarantees:
 * - Structural schema validation before applying imported scenarios.
 * - Safe JSON parsing (no eval or script execution).
 * - Preservation of coordinate fidelity, walls, obstacles, risk zones, and grid resolution.
 * - Exact round-trip export-import semantics.
 */

import { validateScenarioLocally } from '../renderer/geometryValidation.ts'
import type { Obstacle, Point, RiskZone, Scenario, Wall } from '../types/api'

export function serializeScenarioToJson(scenario: Scenario): string {
  const exportPayload: Scenario = {
    xmin: scenario.xmin ?? 0.0,
    xmax: scenario.xmax,
    ymin: scenario.ymin ?? 0.0,
    ymax: scenario.ymax,
    grid_resolution: scenario.grid_resolution ?? 0.5,
    walls: (scenario.walls || []).map(w => ({
      start: { x: w.start.x, y: w.start.y },
      end: { x: w.end.x, y: w.end.y },
      is_opaque: w.is_opaque !== false,
    })),
    obstacles: (scenario.obstacles || []).map(o => ({
      vertices: o.vertices.map(v => ({
        x: v.x,
        y: v.y,
      })),
    })),
    risk_zones: (scenario.risk_zones || []).map(r => ({
      name: r.name || 'Zona de Riesgo',
      weight: r.weight,
      vertices: r.vertices.map(v => ({
        x: v.x,
        y: v.y,
      })),
    })),
  }

  return JSON.stringify(exportPayload, null, 2)
}

export function exportScenarioToJson(scenario: Scenario, filename = 'escenario_abc.json'): string {
  const jsonStr = serializeScenarioToJson(scenario)
  if (typeof document !== 'undefined' && typeof Blob !== 'undefined' && typeof URL !== 'undefined') {
    const blob = new Blob([jsonStr], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }
  return jsonStr
}

export function parseAndValidateScenarioJson(
  jsonText: string
): { scenario: Scenario | null; errors: string[] } {
  let parsed: unknown
  try {
    parsed = JSON.parse(jsonText)
  } catch (err) {
    return {
      scenario: null,
      errors: [`Error de sintaxis JSON: ${err instanceof Error ? err.message : String(err)}`],
    }
  }

  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    return {
      scenario: null,
      errors: ['El archivo JSON debe contener un objeto con la definición del escenario.'],
    }
  }

  const obj = parsed as Record<string, unknown>
  const errors: string[] = []

  // Check required boundaries
  if (typeof obj.xmax !== 'number' || !Number.isFinite(obj.xmax)) {
    errors.push("Campo requerido 'xmax' ausente o no numérico.")
  }
  if (typeof obj.ymax !== 'number' || !Number.isFinite(obj.ymax)) {
    errors.push("Campo requerido 'ymax' ausente o no numérico.")
  }

  // Check optional boundaries
  let xmin = 0.0
  if (obj.xmin !== undefined) {
    if (typeof obj.xmin !== 'number' || !Number.isFinite(obj.xmin)) {
      errors.push("Campo 'xmin' presente pero no es un número finito válido.")
    } else {
      xmin = obj.xmin
    }
  }

  let ymin = 0.0
  if (obj.ymin !== undefined) {
    if (typeof obj.ymin !== 'number' || !Number.isFinite(obj.ymin)) {
      errors.push("Campo 'ymin' presente pero no es un número finito válido.")
    } else {
      ymin = obj.ymin
    }
  }

  // Check grid resolution
  let gridRes = 0.5
  if (obj.grid_resolution !== undefined) {
    if (
      typeof obj.grid_resolution !== 'number' ||
      !Number.isFinite(obj.grid_resolution) ||
      obj.grid_resolution <= 0
    ) {
      errors.push("El campo 'grid_resolution' debe ser un número finito estrictamente mayor que cero.")
    } else {
      gridRes = obj.grid_resolution
    }
  }

  // Validate walls collection
  const walls: Wall[] = []
  if (obj.walls !== undefined) {
    if (!Array.isArray(obj.walls)) {
      errors.push("El campo 'walls' debe ser una lista (array).")
    } else {
      obj.walls.forEach((w: unknown, idx: number) => {
        if (typeof w !== 'object' || w === null) {
          errors.push(`Pared #${idx + 1} no es un objeto válido.`)
          return
        }
        const wallObj = w as Record<string, unknown>
        const start = wallObj.start as Record<string, unknown> | undefined
        const end = wallObj.end as Record<string, unknown> | undefined

        if (
          !start ||
          typeof start.x !== 'number' ||
          !Number.isFinite(start.x) ||
          typeof start.y !== 'number' ||
          !Number.isFinite(start.y) ||
          !end ||
          typeof end.x !== 'number' ||
          !Number.isFinite(end.x) ||
          typeof end.y !== 'number' ||
          !Number.isFinite(end.y)
        ) {
          errors.push(`Pared #${idx + 1} tiene coordenadas de inicio o fin inválidas.`)
          return
        }

        if (wallObj.is_opaque !== undefined && typeof wallObj.is_opaque !== 'boolean') {
          errors.push(`Pared #${idx + 1} tiene un campo 'is_opaque' no booleano.`)
          return
        }

        walls.push({
          start: { x: start.x, y: start.y },
          end: { x: end.x, y: end.y },
          is_opaque: wallObj.is_opaque !== false,
        })
      })
    }
  }

  // Validate obstacles collection
  const obstacles: Obstacle[] = []
  if (obj.obstacles !== undefined) {
    if (!Array.isArray(obj.obstacles)) {
      errors.push("El campo 'obstacles' debe ser una lista (array).")
    } else {
      obj.obstacles.forEach((obs: unknown, idx: number) => {
        if (typeof obs !== 'object' || obs === null) {
          errors.push(`Obstáculo #${idx + 1} no es un objeto válido.`)
          return
        }
        const obsObj = obs as Record<string, unknown>
        if (!Array.isArray(obsObj.vertices)) {
          errors.push(`Obstáculo #${idx + 1} no contiene la lista 'vertices'.`)
          return
        }
        if (obsObj.vertices.length < 3) {
          errors.push(`Obstáculo #${idx + 1} debe tener al menos 3 vértices.`)
          return
        }

        const vertices: Point[] = []
        for (const v of obsObj.vertices) {
          const vObj = v as Record<string, unknown>
          if (
            typeof vObj !== 'object' ||
            vObj === null ||
            typeof vObj.x !== 'number' ||
            !Number.isFinite(vObj.x) ||
            typeof vObj.y !== 'number' ||
            !Number.isFinite(vObj.y)
          ) {
            errors.push(`Obstáculo #${idx + 1} contiene un vértice no numérico.`)
            return
          }
          vertices.push({ x: vObj.x, y: vObj.y })
        }
        obstacles.push({ vertices })
      })
    }
  }

  // Validate risk zones collection
  const riskZones: RiskZone[] = []
  if (obj.risk_zones !== undefined) {
    if (!Array.isArray(obj.risk_zones)) {
      errors.push("El campo 'risk_zones' debe ser una lista (array).")
    } else {
      obj.risk_zones.forEach((rz: unknown, idx: number) => {
        if (typeof rz !== 'object' || rz === null) {
          errors.push(`Zona de riesgo #${idx + 1} no es un objeto válido.`)
          return
        }
        const rzObj = rz as Record<string, unknown>
        if (!Array.isArray(rzObj.vertices)) {
          errors.push(`Zona de riesgo #${idx + 1} no contiene la lista 'vertices'.`)
          return
        }
        if (rzObj.vertices.length < 3) {
          errors.push(`Zona de riesgo #${idx + 1} debe tener al menos 3 vértices.`)
          return
        }

        const vertices: Point[] = []
        for (const v of rzObj.vertices) {
          const vObj = v as Record<string, unknown>
          if (
            typeof vObj !== 'object' ||
            vObj === null ||
            typeof vObj.x !== 'number' ||
            !Number.isFinite(vObj.x) ||
            typeof vObj.y !== 'number' ||
            !Number.isFinite(vObj.y)
          ) {
            errors.push(`Zona de riesgo #${idx + 1} contiene un vértice no numérico.`)
            return
          }
          vertices.push({ x: vObj.x, y: vObj.y })
        }

        if (
          typeof rzObj.weight !== 'number' ||
          !Number.isFinite(rzObj.weight) ||
          rzObj.weight < 1.0
        ) {
          errors.push(`Zona de riesgo #${idx + 1} debe tener un peso 'weight' numérico finito mayor o igual a 1.0.`)
          return
        }

        let name = `Zona #${idx + 1}`
        if (rzObj.name !== undefined) {
          if (typeof rzObj.name !== 'string') {
            errors.push(`Zona de riesgo #${idx + 1} tiene un campo 'name' con tipo inválido (debe ser una cadena de texto).`)
            return
          }
          name = rzObj.name
        }
        riskZones.push({ vertices, weight: rzObj.weight, name })
      })
    }
  }

  // Do not proceed or apply partially if errors exist
  if (errors.length > 0) {
    return { scenario: null, errors }
  }

  const scenario: Scenario = {
    xmin,
    xmax: obj.xmax as number,
    ymin,
    ymax: obj.ymax as number,
    grid_resolution: gridRes,
    walls,
    obstacles,
    risk_zones: riskZones,
  }

  // Complete geometric validation
  const geoValidation = validateScenarioLocally(scenario)
  if (!geoValidation.isValid) {
    return { scenario: null, errors: geoValidation.errors }
  }

  return { scenario, errors: [] }
}
