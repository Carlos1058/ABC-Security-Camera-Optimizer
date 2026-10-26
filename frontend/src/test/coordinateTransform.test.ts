import { describe, expect, it } from 'vitest'
import { CoordinateTransform } from '../renderer/coordinateTransform'
import type { Scenario } from '../types/api'

describe('CoordinateTransform Tests', () => {
  it('1. transforms world coordinates (meters) to canvas pixels with Cartesian Y-up orientation', () => {
    const scenario: Scenario = {
      xmin: 0.0,
      xmax: 20.0,
      ymin: 0.0,
      ymax: 10.0,
    }
    // 800x400 canvas, 0 padding for exact math test
    const transform = new CoordinateTransform(800, 400, scenario, 1.0, 0, 0, 0)

    // In a 20x10 room on 800x400, scale is 40 px/m
    expect(transform.scale).toBeCloseTo(40.0)

    // (0, 0) should be at bottom-left in screen pixels (x = 0, y = 400)
    const pOrigin = transform.worldToScreen({ x: 0, y: 0 })
    expect(pOrigin.x).toBeCloseTo(0.0)
    expect(pOrigin.y).toBeCloseTo(400.0)

    // (20, 10) should be at top-right in screen pixels (x = 800, y = 0)
    const pTopRight = transform.worldToScreen({ x: 20, y: 10 })
    expect(pTopRight.x).toBeCloseTo(800.0)
    expect(pTopRight.y).toBeCloseTo(0.0)

    // Center (10, 5) should be at center of canvas (400, 200)
    const pCenter = transform.worldToScreen({ x: 10, y: 5 })
    expect(pCenter.x).toBeCloseTo(400.0)
    expect(pCenter.y).toBeCloseTo(200.0)
  })

  it('2. preserves aspect ratio and correctly handles arbitrary non-zero room origins', () => {
    // Non-zero origin: room from x=[-5, 15], y=[10, 30] -> width=20, height=20 (square)
    const squareScenario: Scenario = {
      xmin: -5.0,
      xmax: 15.0,
      ymin: 10.0,
      ymax: 30.0,
    }

    // Wide rectangular canvas 1000x500 with 50px padding (available: 900x400)
    const transform = new CoordinateTransform(1000, 500, squareScenario, 1.0, 0, 0, 50)

    // Room is 20m x 20m. Scale should be bounded by available height (400 / 20 = 20 px/m)
    expect(transform.scale).toBeCloseTo(20.0)

    // Bidirectional roundtrip test: screenToWorld(worldToScreen(p)) == p
    const testPoints = [
      { x: -5.0, y: 10.0 }, // bottom-left
      { x: 15.0, y: 30.0 }, // top-right
      { x: 5.0, y: 20.0 },  // center
      { x: 0.0, y: 15.5 },  // internal point
    ]

    for (const pt of testPoints) {
      const screen = transform.worldToScreen(pt)
      const reconstructed = transform.screenToWorld(screen)
      expect(reconstructed.x).toBeCloseTo(pt.x, 6)
      expect(reconstructed.y).toBeCloseTo(pt.y, 6)
    }
  })

  it('3. handles zoom and pan transformations correctly', () => {
    const scenario: Scenario = { xmin: 0, xmax: 10, ymin: 0, ymax: 10 }
    const zoomFactor = 2.5
    const panOffset = { x: 50, y: -30 }

    const transform = new CoordinateTransform(500, 500, scenario, zoomFactor, panOffset.x, panOffset.y, 20)

    const pt = { x: 5, y: 5 }
    const screen = transform.worldToScreen(pt)
    const roundtrip = transform.screenToWorld(screen)

    expect(roundtrip.x).toBeCloseTo(pt.x, 6)
    expect(roundtrip.y).toBeCloseTo(pt.y, 6)
  })

  it('4. angle conversion preserves Cartesian heading orientation in screen space', () => {
    const scenario: Scenario = { xmin: 0, xmax: 10, ymin: 0, ymax: 10 }
    const transform = new CoordinateTransform(500, 500, scenario)

    // Heading East (0 rad) -> 0 rad
    expect(transform.angleToScreen(0)).toBeCloseTo(0)

    // Heading North (pi/2 rad, +Y in Cartesian) -> -pi/2 in Canvas screen space (pointing up)
    expect(transform.angleToScreen(Math.PI / 2)).toBeCloseTo(-Math.PI / 2)

    // Heading South (-pi/2 rad, -Y in Cartesian) -> +pi/2 in Canvas screen space (pointing down)
    expect(transform.angleToScreen(-Math.PI / 2)).toBeCloseTo(Math.PI / 2)
  })
})
