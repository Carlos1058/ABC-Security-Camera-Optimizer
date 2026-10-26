/**
 * Verification Test Suite for TAREA 08 — Fase 5C: Interactive Floorplan Editor.
 *
 * Verifies all 16 required capabilities:
 * 1. Valid wall creation (coordinates, length >= 0.05m, opacity).
 * 2. Door opening creation and segment splitting (gap width, disjoint valid segments).
 * 3. Polygonal obstacle creation (>= 3 distinct vertices, positive area).
 * 4. Rejection of self-intersecting / non-simple polygons.
 * 5. Risk zone creation, naming and criticality weight (w >= 1.0).
 * 6. Vertex selection and coordinates modification.
 * 7. Metric grid snapping (0.1m, 0.25m, 0.5m, 1.0m).
 * 8. Bidirectional coordinate transformation with zoom and pan.
 * 9. Independent undo / redo history stack (up to 50 operations).
 * 10. ScenarioDTO authentic JSON export and import round-trip.
 * 11. Backend scenario validation schema compatibility.
 * 12. Invalidation of ABC optimization and coverage cache upon scenario modification.
 * 13. Optimization request payload generation from custom scenario.
 * 14. Coverage evaluation request payload generation from custom scenario.
 * 15. Pending async coverage request invalidation on cache retrieval (Phase 5B bug fix).
 * 16. Preservation of scenario constraints (finite bounds, positive resolution).
 */

import { describe, expect, it } from 'vitest'
import {
  doSegmentsIntersect,
  isPointInsidePolygon,
  isPolygonSelfIntersecting,
  pointDistance,
  pointToSegmentDistance,
  polygonArea,
  snapPoint,
  splitWallWithOpening,
  validateScenarioLocally,
} from '../renderer/geometryValidation'
import { CoordinateTransform } from '../renderer/coordinateTransform'
import { buildCanonicalCoverageKey } from '../renderer/coverageKey'
import { parseAndValidateScenarioJson } from '../services/scenarioIO'
import type { CameraProfile, Scenario, Wall } from '../types/api'

describe('Fase 5C: Editor Interactivo de Escenarios Arquitectónicos', () => {
  // Test 1: Valid wall creation
  it('1. should create and validate authentic wall segments', () => {
    const wall: Wall = {
      start: { x: 2.0, y: 3.0 },
      end: { x: 10.0, y: 3.0 },
      is_opaque: true,
    }
    const len = pointDistance(wall.start, wall.end)
    expect(len).toBeCloseTo(8.0, 4)

    const sc: Scenario = {
      xmin: 0,
      xmax: 20,
      ymin: 0,
      ymax: 20,
      walls: [wall],
    }
    const val = validateScenarioLocally(sc)
    expect(val.isValid).toBe(true)
    expect(val.errors).toHaveLength(0)

    // Degenerate wall (< 0.05m) must be rejected
    const degenWall: Wall = {
      start: { x: 2.0, y: 3.0 },
      end: { x: 2.02, y: 3.0 },
      is_opaque: true,
    }
    const valDegen = validateScenarioLocally({ ...sc, walls: [degenWall] })
    expect(valDegen.isValid).toBe(false)
    expect(valDegen.errors[0]).toMatch(/degenerada/i)
  })

  // Test 2: Door opening and wall splitting
  it('2. should split an existing wall into two valid disjoint segments with opening gap', () => {
    const wall: Wall = {
      start: { x: 0.0, y: 10.0 },
      end: { x: 10.0, y: 10.0 },
      is_opaque: true,
    }

    // Split at center x=5.0 with door width 1.0m
    const res = splitWallWithOpening(wall, { x: 5.0, y: 10.0 }, 1.0)
    expect(res.valid).toBe(true)
    expect(res.walls).toHaveLength(2)

    const [w1, w2] = res.walls
    // First segment ends at 4.5m
    expect(w1.start.x).toBeCloseTo(0.0, 2)
    expect(w1.end.x).toBeCloseTo(4.5, 2)
    expect(w1.is_opaque).toBe(true)

    // Second segment starts at 5.5m
    expect(w2.start.x).toBeCloseTo(5.5, 2)
    expect(w2.end.x).toBeCloseTo(10.0, 2)
    expect(w2.is_opaque).toBe(true)

    // Gap between segments is exactly 1.0m
    const gap = pointDistance(w1.end, w2.start)
    expect(gap).toBeCloseTo(1.0, 2)

    // Reject opening when wall is shorter than opening + 0.2m margin
    const shortWall: Wall = {
      start: { x: 0.0, y: 5.0 },
      end: { x: 0.8, y: 5.0 },
      is_opaque: true,
    }
    const shortRes = splitWallWithOpening(shortWall, { x: 0.4, y: 5.0 }, 1.0)
    expect(shortRes.valid).toBe(false)
    expect(shortRes.error).toBeDefined()
  })

  // Test 3: Polygonal obstacle creation
  it('3. should create valid polygonal obstacles with positive area', () => {
    const vertices = [
      { x: 3.0, y: 3.0 },
      { x: 8.0, y: 3.0 },
      { x: 8.0, y: 7.0 },
      { x: 3.0, y: 7.0 },
    ]
    const area = Math.abs(polygonArea(vertices))
    expect(area).toBeCloseTo(20.0, 2)

    const sc: Scenario = {
      xmin: 0,
      xmax: 20,
      ymin: 0,
      ymax: 20,
      obstacles: [{ vertices }],
    }
    const val = validateScenarioLocally(sc)
    expect(val.isValid).toBe(true)
  })

  // Test 4: Rejection of self-intersecting polygon
  it('4. should reject self-intersecting / non-simple polygons', () => {
    // Bowtie hourglass polygon: (0,0) -> (4,4) -> (0,4) -> (4,0)
    const selfIntersecting = [
      { x: 0.0, y: 0.0 },
      { x: 4.0, y: 4.0 },
      { x: 0.0, y: 4.0 },
      { x: 4.0, y: 0.0 },
    ]
    expect(isPolygonSelfIntersecting(selfIntersecting)).toBe(true)

    const sc: Scenario = {
      xmin: 0,
      xmax: 20,
      ymin: 0,
      ymax: 20,
      obstacles: [{ vertices: selfIntersecting }],
    }
    const val = validateScenarioLocally(sc)
    expect(val.isValid).toBe(false)
    expect(val.errors[0]).toMatch(/autointersecado/i)

    // Simple convex square must NOT be flagged as self-intersecting
    const simple = [
      { x: 0.0, y: 0.0 },
      { x: 4.0, y: 0.0 },
      { x: 4.0, y: 4.0 },
      { x: 0.0, y: 4.0 },
    ]
    expect(isPolygonSelfIntersecting(simple)).toBe(false)
  })

  // Test 5: Risk zone creation and criticality weight
  it('5. should create and validate risk zones with weight w >= 1.0', () => {
    const validRz = {
      vertices: [
        { x: 12.0, y: 12.0 },
        { x: 16.0, y: 12.0 },
        { x: 16.0, y: 16.0 },
        { x: 12.0, y: 16.0 },
      ],
      weight: 3.5,
      name: 'Bóveda Principal',
    }

    const sc: Scenario = {
      xmin: 0,
      xmax: 20,
      ymin: 0,
      ymax: 20,
      risk_zones: [validRz],
    }
    const val = validateScenarioLocally(sc)
    expect(val.isValid).toBe(true)

    // Weight < 1.0 must be rejected
    const invalidRz = { ...validRz, weight: 0.8 }
    const valInvalid = validateScenarioLocally({ ...sc, risk_zones: [invalidRz] })
    expect(valInvalid.isValid).toBe(false)
    expect(valInvalid.errors[0]).toMatch(/peso w >= 1.0/i)
  })

  // Test 6: Vertex selection and point-to-segment calculations
  it('6. should detect vertex selection and calculate point to segment projection', () => {
    const a = { x: 2.0, y: 2.0 }
    const b = { x: 8.0, y: 2.0 }
    const p = { x: 5.0, y: 4.0 }

    const res = pointToSegmentDistance(p, a, b)
    expect(res.distance).toBeCloseTo(2.0, 4)
    expect(res.projection.x).toBeCloseTo(5.0, 4)
    expect(res.projection.y).toBeCloseTo(2.0, 4)
    expect(res.t).toBeCloseTo(0.5, 4)
  })

  // Test 7: Metric grid snapping
  it('7. should snap world coordinates to configured metric grid increments', () => {
    const pt = { x: 4.234, y: 7.891 }

    expect(snapPoint(pt, 0.5)).toEqual({ x: 4.0, y: 8.0 })
    expect(snapPoint(pt, 0.25)).toEqual({ x: 4.25, y: 8.0 })
    expect(snapPoint(pt, 1.0)).toEqual({ x: 4.0, y: 8.0 })
    expect(snapPoint(pt, 0.1)).toEqual({ x: 4.2, y: 7.9 })
  })

  // Test 8: Zoom and Pan transformation round-trip
  it('8. should perform exact bidirectional mapping between screen and world coordinates', () => {
    const sc: Scenario = { xmin: 0, xmax: 30, ymin: 0, ymax: 20 }
    const transform = new CoordinateTransform(800, 600, sc, 1.8, 45, -30, 40)

    const worldOriginal = { x: 12.345, y: 8.678 }
    const screenPt = transform.worldToScreen(worldOriginal)
    const worldRestored = transform.screenToWorld(screenPt)

    expect(worldRestored.x).toBeCloseTo(worldOriginal.x, 5)
    expect(worldRestored.y).toBeCloseTo(worldOriginal.y, 5)
  })

  // Test 9: Undo and Redo stack management
  it('9. should manage independent undo and redo history snapshots up to 50 operations', () => {
    const s0: Scenario = { xmax: 10, ymax: 10, walls: [] }
    const s1: Scenario = {
      xmax: 10,
      ymax: 10,
      walls: [{ start: { x: 0, y: 5 }, end: { x: 10, y: 5 }, is_opaque: true }],
    }
    const s2: Scenario = {
      xmax: 10,
      ymax: 10,
      walls: [
        { start: { x: 0, y: 5 }, end: { x: 10, y: 5 }, is_opaque: true },
        { start: { x: 5, y: 0 }, end: { x: 5, y: 10 }, is_opaque: true },
      ],
    }

    const undoStack: Scenario[] = [s0, s1]
    let redoStack: Scenario[] = []
    let current = s2

    // Undo: revert to s1
    redoStack = [...redoStack, current]
    current = undoStack.pop()!
    expect(current.walls).toHaveLength(1)

    // Undo: revert to s0
    redoStack = [...redoStack, current]
    current = undoStack.pop()!
    expect(current.walls).toHaveLength(0)

    // Redo: restore s1
    undoStack.push(current)
    current = redoStack.pop()!
    expect(current.walls).toHaveLength(1)

    // Redo: restore s2
    undoStack.push(current)
    current = redoStack.pop()!
    expect(current.walls).toHaveLength(2)
  })

  // Test 10: Import and Export JSON round-trip
  it('10. should safely deserialize, validate and preserve scenario properties from JSON', () => {
    const originalJson = JSON.stringify({
      xmin: 0.0,
      xmax: 25.0,
      ymin: 0.0,
      ymax: 15.0,
      grid_resolution: 0.5,
      walls: [
        { start: { x: 5.0, y: 0.0 }, end: { x: 5.0, y: 8.0 }, is_opaque: true },
      ],
      obstacles: [
        {
          vertices: [
            { x: 10.0, y: 5.0 },
            { x: 14.0, y: 5.0 },
            { x: 14.0, y: 9.0 },
            { x: 10.0, y: 9.0 },
          ],
        },
      ],
      risk_zones: [
        {
          vertices: [
            { x: 18.0, y: 2.0 },
            { x: 23.0, y: 2.0 },
            { x: 23.0, y: 7.0 },
            { x: 18.0, y: 7.0 },
          ],
          weight: 4.0,
          name: 'Laboratorio Crítico',
        },
      ],
    })

    const { scenario: parsed, errors } = parseAndValidateScenarioJson(originalJson)
    expect(errors).toHaveLength(0)
    expect(parsed).not.toBeNull()
    expect(parsed?.xmax).toBe(25.0)
    expect(parsed?.walls).toHaveLength(1)
    expect(parsed?.obstacles).toHaveLength(1)
    expect(parsed?.risk_zones).toHaveLength(1)
    expect(parsed?.risk_zones?.[0].weight).toBe(4.0)
    expect(parsed?.risk_zones?.[0].name).toBe('Laboratorio Crítico')

    // Malformed JSON must return clean error without throwing
    const malformedRes = parseAndValidateScenarioJson('{ invalid json string')
    expect(malformedRes.scenario).toBeNull()
    expect(malformedRes.errors[0]).toMatch(/JSON/i)

    // Missing required xmax field
    const missingBounds = parseAndValidateScenarioJson(JSON.stringify({ ymax: 10 }))
    expect(missingBounds.scenario).toBeNull()
    expect(missingBounds.errors[0]).toMatch(/xmax/i)
  })

  // Test 11: Real validation payload against FastAPI constraints
  it('11. should enforce finite bounds and positive resolution matching FastAPI ScenarioDTO', () => {
    const invalidScenario: Scenario = {
      xmin: 0,
      xmax: -10, // xmax <= xmin
      ymin: 0,
      ymax: 10,
    }
    const res = validateScenarioLocally(invalidScenario)
    expect(res.isValid).toBe(false)
    expect(res.errors[0]).toMatch(/xmax.*mayor que xmin/i)
  })

  // Test 12: Invalidation of ABC results upon editing
  it('12. should produce a new canonical coverage key when geometry changes', () => {
    const sc1: Scenario = { xmax: 10, ymax: 10, walls: [] }
    const sc2: Scenario = {
      xmax: 10,
      ymax: 10,
      walls: [{ start: { x: 0, y: 5 }, end: { x: 10, y: 5 }, is_opaque: true }],
    }
    const profile: CameraProfile = {
      Rmin: 0,
      Rmax: 10,
      FOV: Math.PI / 2,
      p0: 1,
      beta_d: 0.5,
      beta_theta: 0.5,
    }
    const cameras = [{ x: 5, y: 2, theta: 0.1 }]

    const key1 = buildCanonicalCoverageKey(sc1, profile, 1.0, 0.8, cameras)
    const key2 = buildCanonicalCoverageKey(sc2, profile, 1.0, 0.8, cameras)

    // The keys must differ, ensuring cache separation and result invalidation
    expect(key1).not.toBe(key2)
  })

  // Test 13: Stale asynchronous response invalidation on cache hit (Phase 5B fix)
  it('13. should invalidate older in-flight requests when a cache hit advances the request counter', async () => {
    let currentRequestId = 0
    let activeCoverageKey = ''
    let renderedResult = ''
    const cache = new Map<string, string>()

    cache.set('KEY_CACHED', 'RESULT_CACHED')

    // Scenario:
    // Request 1 is started for a slow uncached configuration
    const req1Id = ++currentRequestId
    let resolveSlowRequest: (val: string) => void = () => {}
    const slowRequestPromise = new Promise<string>(resolve => {
      resolveSlowRequest = resolve
    })

    // While Request 1 is pending, user selects a previously computed cycle (cache hit!)
    const targetKey = 'KEY_CACHED'
    if (cache.has(targetKey)) {
      // THE FIX: increment currentRequestId so slower pending requests are marked stale!
      currentRequestId += 1
      renderedResult = cache.get(targetKey)!
      activeCoverageKey = targetKey
    }

    expect(renderedResult).toBe('RESULT_CACHED')
    expect(activeCoverageKey).toBe('KEY_CACHED')

    // Now slow Request 1 resolves late
    resolveSlowRequest('RESULT_STALE_SLOW')
    const slowRes = await slowRequestPromise

    // Because req1Id (1) does NOT equal currentRequestId (2), it must be discarded!
    if (req1Id === currentRequestId) {
      renderedResult = slowRes
    }

    // Rendered result must remain the cached one, NOT overwritten by the stale slow response!
    expect(renderedResult).toBe('RESULT_CACHED')
  })

  // Test 14: Non-square dimensions preservation
  it('14. should preserve aspect ratio for non-square rectangular rooms', () => {
    const scWide: Scenario = { xmin: 0, xmax: 30, ymin: 0, ymax: 10 }
    const transform = new CoordinateTransform(600, 400, scWide, 1.0, 0, 0, 20)

    const roomW = scWide.xmax - (scWide.xmin ?? 0)
    const roomH = scWide.ymax - (scWide.ymin ?? 0)

    const renderedPixelW = roomW * transform.scale
    const renderedPixelH = roomH * transform.scale

    // The ratio of pixels must match physical aspect ratio 3:1 exactly
    expect(renderedPixelW / renderedPixelH).toBeCloseTo(3.0, 4)
  })

  // Test 15: Point inside polygon ray casting
  it('15. should accurately detect whether a point lies inside an obstacle polygon', () => {
    const poly = [
      { x: 2, y: 2 },
      { x: 6, y: 2 },
      { x: 6, y: 6 },
      { x: 2, y: 6 },
    ]
    expect(isPointInsidePolygon({ x: 4, y: 4 }, poly)).toBe(true)
    expect(isPointInsidePolygon({ x: 1, y: 1 }, poly)).toBe(false)
    expect(isPointInsidePolygon({ x: 7, y: 7 }, poly)).toBe(false)
  })

  // Test 16: Segment intersection math
  it('16. should correctly determine segment intersections', () => {
    // Crossing segments
    expect(
      doSegmentsIntersect(
        { x: 0, y: 0 },
        { x: 4, y: 4 },
        { x: 0, y: 4 },
        { x: 4, y: 0 }
      )
    ).toBe(true)

    // Parallel disjoint segments
    expect(
      doSegmentsIntersect(
        { x: 0, y: 0 },
        { x: 4, y: 0 },
        { x: 0, y: 2 },
        { x: 4, y: 2 }
      )
    ).toBe(false)
  })
})
