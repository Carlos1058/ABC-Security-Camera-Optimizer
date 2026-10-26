/**
 * Computational Geometry Utilities and Scenario Validation.
 *
 * Implements:
 * - Segment-segment intersection testing.
 * - Polygon self-intersection and degeneracy detection.
 * - Distance from point to segment (for click selection and door opening projection).
 * - Wall splitting for physical door openings.
 * - Grid snap calculations.
 * - Client-side scenario validation matching FastAPI backend constraints.
 */

import type { Point, RiskZone, Scenario, Wall } from '../types/api'

const EPSILON = 1e-6

export function pointDistance(a: Point, b: Point): number {
  return Math.hypot(a.x - b.x, a.y - b.y)
}

export function snapPoint(pt: Point, snapSize: number): Point {
  if (snapSize <= 0) return { ...pt }
  const x = Math.round(pt.x / snapSize) * snapSize
  const y = Math.round(pt.y / snapSize) * snapSize
  // Normalize -0 to 0 and round to 4 decimal places to prevent floating point noise
  return {
    x: Number(x.toFixed(4)),
    y: Number(y.toFixed(4)),
  }
}

/**
 * Compute the distance from point P to line segment AB, returning the distance,
 * the projection point on the segment, and the parameter t in [0, 1].
 */
export function pointToSegmentDistance(
  p: Point,
  a: Point,
  b: Point
): { distance: number; projection: Point; t: number } {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const l2 = dx * dx + dy * dy

  if (l2 < EPSILON) {
    return {
      distance: pointDistance(p, a),
      projection: { x: a.x, y: a.y },
      t: 0,
    }
  }

  // Projection parameter t = ((p - a) . (b - a)) / l2
  let t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / l2
  t = Math.max(0, Math.min(1, t))

  const proj: Point = {
    x: a.x + t * dx,
    y: a.y + t * dy,
  }

  return {
    distance: pointDistance(p, proj),
    projection: proj,
    t,
  }
}

export type SegmentIntersectionResult =
  | { type: 'none' }
  | { type: 'point'; point: Point }
  | { type: 'segment'; start: Point; end: Point }

/**
 * Detailed 2D segment intersection algorithm matching Python's Segment2D.intersect_with.
 * Deterministically categorizes intersections into:
 *  - 'none' : No intersection
 *  - 'point' : Intersection at a single point (crossing or endpoint touch)
 *  - 'segment' : Collinear overlap with positive length
 */
export function intersectSegmentsDetailed(
  p1: Point,
  p2: Point,
  p3: Point,
  p4: Point,
  tol = EPSILON
): SegmentIntersectionResult {
  const rx = p2.x - p1.x
  const ry = p2.y - p1.y
  const sx = p4.x - p3.x
  const sy = p4.y - p3.y

  const lenR = Math.hypot(rx, ry)
  const lenS = Math.hypot(sx, sy)

  if (lenR < tol || lenS < tol) {
    return { type: 'none' }
  }

  const qx = p3.x - p1.x
  const qy = p3.y - p1.y

  // 2D cross product: r x s
  const crossRS = rx * sy - ry * sx
  const sinAngle = Math.abs(crossRS) / (lenR * lenS)

  // Collinear or parallel lines
  if (sinAngle <= 1e-9) {
    const crossQR = qx * ry - qy * rx
    const distBetweenLines = Math.abs(crossQR) / lenR

    if (distBetweenLines > tol) {
      // Parallel but separated
      return { type: 'none' }
    }

    // Collinear: project S2 onto S1 parameter space t in [0, 1]
    const invRSq = 1.0 / (lenR * lenR)
    const t3 = (qx * rx + qy * ry) * invRSq
    const t4 = ((p4.x - p1.x) * rx + (p4.y - p1.y) * ry) * invRSq

    const tMinS2 = Math.min(t3, t4)
    const tMaxS2 = Math.max(t3, t4)

    const tStart = Math.max(0.0, tMinS2)
    const tEnd = Math.min(1.0, tMaxS2)

    const tolT = tol / lenR

    if (tStart > tEnd + tolT) {
      // Disjoint along line
      return { type: 'none' }
    }

    if (Math.abs(tStart - tEnd) <= tolT) {
      // Touching at a single point along line
      const tTouch = Math.max(0.0, Math.min(1.0, (tStart + tEnd) / 2.0))
      return {
        type: 'point',
        point: { x: p1.x + tTouch * rx, y: p1.y + tTouch * ry },
      }
    }

    // Collinear overlap with positive length
    return {
      type: 'segment',
      start: { x: p1.x + tStart * rx, y: p1.y + tStart * ry },
      end: { x: p1.x + tEnd * rx, y: p1.y + tEnd * ry },
    }
  }

  // Non-parallel lines: solve r x s * t = q x s, r x s * u = q x r
  const crossQS = qx * sy - qy * sx
  const crossQR = qx * ry - qy * rx

  const t = crossQS / crossRS
  const u = crossQR / crossRS

  const tolT = tol / lenR
  const tolU = tol / lenS

  if (t >= -tolT && t <= 1.0 + tolT && u >= -tolU && u <= 1.0 + tolU) {
    const tClamped = Math.max(0.0, Math.min(1.0, t))
    return {
      type: 'point',
      point: { x: p1.x + tClamped * rx, y: p1.y + tClamped * ry },
    }
  }

  return { type: 'none' }
}

/**
 * Test whether segment AB intersects segment CD.
 * If strictInterior is true, sharing a single endpoint does NOT count as an intersection.
 * If segments overlap collinearly with positive length, ALWAYS returns true.
 */
export function doSegmentsIntersect(
  a: Point,
  b: Point,
  c: Point,
  d: Point,
  strictInterior = false
): boolean {
  const res = intersectSegmentsDetailed(a, b, c, d)

  if (res.type === 'none') {
    return false
  }

  if (res.type === 'segment') {
    // Collinear overlap of positive length is ALWAYS a geometric intersection
    return true
  }

  // Single point intersection
  if (strictInterior) {
    const pt = res.point
    const atEndpoint =
      pointDistance(pt, a) < EPSILON ||
      pointDistance(pt, b) < EPSILON ||
      pointDistance(pt, c) < EPSILON ||
      pointDistance(pt, d) < EPSILON

    return !atEndpoint
  }

  return true
}

/**
 * Check if a polygon defined by an ordered list of vertices has self-intersections.
 * Strictly adheres to Python Polygon2D semantics:
 * 1. At least 3 vertices.
 * 2. Consecutive vertices must not be identical within tolerance.
 * 3. Non-consecutive vertices must not be identical (reject figure-8, lasso, repeated vertices).
 * 4. Adjacent edges must not overlap collinearly (reject spikes/backtracking).
 * 5. Non-adjacent edges must not intersect at all (reject self-intersections and touches).
 * 6. Non-zero area.
 */
export function isPolygonSelfIntersecting(vertices: Point[]): boolean {
  const n = vertices.length
  if (n < 3) return true

  // 1. Consecutive vertices must be distinct
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n
    if (pointDistance(vertices[i], vertices[j]) < EPSILON) {
      return true
    }
  }

  // 2. Non-consecutive vertices must be distinct (reject repeated vertices like figure-8 or pinched)
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      if (pointDistance(vertices[i], vertices[j]) < EPSILON) {
        return true
      }
    }
  }

  // 3. Construct edges
  const edges: Array<{ p1: Point; p2: Point }> = []
  for (let i = 0; i < n; i++) {
    edges.push({ p1: vertices[i], p2: vertices[(i + 1) % n] })
  }

  // 4. Pairwise edge intersection tests
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const isAdjacent = j === i + 1 || (i === 0 && j === n - 1)
      const inter = intersectSegmentsDetailed(edges[i].p1, edges[i].p2, edges[j].p1, edges[j].p2)

      if (isAdjacent) {
        // Adjacent edges must only touch at their shared vertex and must NOT overlap collinearly
        if (inter.type === 'segment') {
          return true
        }
      } else {
        // Non-adjacent edges must NOT intersect at all
        if (inter.type !== 'none') {
          return true
        }
      }
    }
  }

  // 5. Degenerate near-zero area check
  const area = Math.abs(polygonArea(vertices))
  if (area < 0.001) {
    return true
  }

  return false
}

/**
 * Calculate signed polygon area (Shoelace formula).
 * Returns positive for CCW, negative for CW.
 */
export function polygonArea(vertices: Point[]): number {
  const n = vertices.length
  if (n < 3) return 0
  let area = 0
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n
    area += vertices[i].x * vertices[j].y - vertices[j].x * vertices[i].y
  }
  return area / 2
}

/**
 * Point-in-polygon test using ray-casting.
 */
export function isPointInsidePolygon(p: Point, vertices: Point[]): boolean {
  let inside = false
  const n = vertices.length
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const xi = vertices[i].x
    const yi = vertices[i].y
    const xj = vertices[j].x
    const yj = vertices[j].y

    const intersect =
      yi > p.y !== yj > p.y && p.x < ((xj - xi) * (p.y - yi)) / (yj - yi) + xi
    if (intersect) inside = !inside
  }
  return inside
}

/**
 * Split a wall segment to create an opening/doorway of given width.
 * Returns two disjoint wall segments with an opening between them.
 */
export function splitWallWithOpening(
  wall: Wall,
  clickPoint: Point,
  openingWidth = 1.0
): { valid: boolean; walls: Wall[]; error?: string } {
  const { t } = pointToSegmentDistance(clickPoint, wall.start, wall.end)
  const totalLength = pointDistance(wall.start, wall.end)

  if (totalLength < openingWidth + 0.2) {
    return {
      valid: false,
      walls: [wall],
      error: `La pared mide ${totalLength.toFixed(2)}m, insuficiente para una abertura de ${openingWidth.toFixed(2)}m (mínimo ${(openingWidth + 0.2).toFixed(2)}m).`,
    }
  }

  const half = openingWidth / 2
  const clickDist = t * totalLength

  // Clamp opening window so it stays within the wall bounds with at least 0.1m stub
  let startDist = clickDist - half
  let endDist = clickDist + half

  if (startDist < 0.1) {
    startDist = 0.1
    endDist = startDist + openingWidth
  }
  if (endDist > totalLength - 0.1) {
    endDist = totalLength - 0.1
    startDist = endDist - openingWidth
  }

  const dx = (wall.end.x - wall.start.x) / totalLength
  const dy = (wall.end.y - wall.start.y) / totalLength

  const isOpaque = wall.is_opaque !== false

  // Segment 1: start to opening start
  const wall1: Wall = {
    start: { ...wall.start },
    end: {
      x: Number((wall.start.x + dx * startDist).toFixed(4)),
      y: Number((wall.start.y + dy * startDist).toFixed(4)),
    },
    is_opaque: isOpaque,
  }

  // Segment 2: opening end to wall end
  const wall2: Wall = {
    start: {
      x: Number((wall.start.x + dx * endDist).toFixed(4)),
      y: Number((wall.start.y + dy * endDist).toFixed(4)),
    },
    end: { ...wall.end },
    is_opaque: isOpaque,
  }

  return {
    valid: true,
    walls: [wall1, wall2],
  }
}

export interface ValidationSummary {
  isValid: boolean
  errors: string[]
  warnings: string[]
}

/**
 * Comprehensive client-side geometric validation before submitting to FastAPI.
 */
export function validateScenarioLocally(scenario: Scenario): ValidationSummary {
  const errors: string[] = []
  const warnings: string[] = []

  const xmin = scenario.xmin ?? 0.0
  const xmax = scenario.xmax
  const ymin = scenario.ymin ?? 0.0
  const ymax = scenario.ymax

  // 1. Check bounds
  if (!Number.isFinite(xmin) || !Number.isFinite(xmax) || !Number.isFinite(ymin) || !Number.isFinite(ymax)) {
    errors.push('Las dimensiones del recinto deben ser números finitos.')
  }
  if (xmax <= xmin) {
    errors.push(`El límite xmax (${xmax}) debe ser estrictamente mayor que xmin (${xmin}).`)
  }
  if (ymax <= ymin) {
    errors.push(`El límite ymax (${ymax}) debe ser estrictamente mayor que ymin (${ymin}).`)
  }

  if (scenario.grid_resolution !== undefined) {
    if (!Number.isFinite(scenario.grid_resolution) || scenario.grid_resolution <= 0) {
      errors.push(`La resolución de malla grid_resolution (${scenario.grid_resolution}) debe ser un número finito estrictamente mayor que cero.`)
    }
  }

  const roomW = xmax - xmin
  const roomH = ymax - ymin
  if (roomW > 200 || roomH > 200) {
    warnings.push(`El recinto es muy grande (${roomW.toFixed(1)}m × ${roomH.toFixed(1)}m), lo cual puede requerir alto tiempo de cómputo.`)
  }

  // 2. Validate walls
  const walls = scenario.walls || []
  walls.forEach((w, idx) => {
    if (!Number.isFinite(w.start.x) || !Number.isFinite(w.start.y) || !Number.isFinite(w.end.x) || !Number.isFinite(w.end.y)) {
      errors.push(`La pared #${idx + 1} contiene coordenadas no finitas.`)
      return
    }

    const len = pointDistance(w.start, w.end)
    if (len < 0.05) {
      errors.push(`La pared #${idx + 1} es degenerada (longitud ${len.toFixed(3)}m < 0.05m).`)
    }

    // Check if points are inside bounds (with slight tolerance)
    const TOL = 0.5
    if (
      w.start.x < xmin - TOL ||
      w.start.x > xmax + TOL ||
      w.start.y < ymin - TOL ||
      w.start.y > ymax + TOL ||
      w.end.x < xmin - TOL ||
      w.end.x > xmax + TOL ||
      w.end.y < ymin - TOL ||
      w.end.y > ymax + TOL
    ) {
      warnings.push(`La pared #${idx + 1} tiene extremos fuera de los límites del recinto.`)
    }
  })

  // 3. Validate obstacles
  const obstacles = scenario.obstacles || []
  obstacles.forEach((obs, idx) => {
    if (!obs.vertices || obs.vertices.length < 3) {
      errors.push(`El obstáculo #${idx + 1} debe tener al menos 3 vértices (tiene ${obs.vertices?.length || 0}).`)
      return
    }

    for (const v of obs.vertices) {
      if (!Number.isFinite(v.x) || !Number.isFinite(v.y)) {
        errors.push(`El obstáculo #${idx + 1} contiene coordenadas no finitas.`)
        return
      }
    }

    const area = Math.abs(polygonArea(obs.vertices))
    if (area < 0.01) {
      errors.push(`El obstáculo #${idx + 1} es colineal o degenerado (área ${area.toFixed(4)}m²).`)
    }

    if (isPolygonSelfIntersecting(obs.vertices)) {
      errors.push(`El obstáculo #${idx + 1} es autointersecado (polígono no simple).`)
    }
  })

  // 4. Validate risk zones
  const riskZones = scenario.risk_zones || []
  riskZones.forEach((rz: RiskZone, idx: number) => {
    if (!rz.vertices || rz.vertices.length < 3) {
      errors.push(`La zona de riesgo #${idx + 1} debe tener al menos 3 vértices.`)
      return
    }

    if (!Number.isFinite(rz.weight) || rz.weight < 1.0) {
      errors.push(`La zona de riesgo #${idx + 1} (${rz.name || 'Sin nombre'}) debe tener un peso w >= 1.0 (tiene ${rz.weight}).`)
    }

    for (const v of rz.vertices) {
      if (!Number.isFinite(v.x) || !Number.isFinite(v.y)) {
        errors.push(`La zona de riesgo #${idx + 1} contiene coordenadas no finitas.`)
        return
      }
    }

    const area = Math.abs(polygonArea(rz.vertices))
    if (area < 0.01) {
      errors.push(`La zona de riesgo #${idx + 1} es degenerada (área ${area.toFixed(4)}m²).`)
    }

    if (isPolygonSelfIntersecting(rz.vertices)) {
      errors.push(`La zona de riesgo #${idx + 1} es autointersecada.`)
    }
  })

  return {
    isValid: errors.length === 0,
    errors,
    warnings,
  }
}
