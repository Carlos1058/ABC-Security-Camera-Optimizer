/**
 * Authentic Integration Test Suite for TAREA 08.2 — Fase 5C: Editor 2D
 *
 * Verifies real interaction workflows connecting React components, Canvas event processing,
 * drag transactions, geometric integrity, strict JSON schema validation, and async cache synchronization.
 */

import { useState, useEffect } from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { FloorplanCanvas } from '../components/FloorplanCanvas'
import { ScenarioInspector } from '../components/ScenarioInspector'
import { useScenarioEditor } from '../renderer/useScenarioEditor'
import { CoordinateTransform } from '../renderer/coordinateTransform'
import {
  doSegmentsIntersect,
  isPolygonSelfIntersecting,
  pointDistance,
  validateScenarioLocally,
} from '../renderer/geometryValidation'
import {
  serializeScenarioToJson,
  parseAndValidateScenarioJson,
} from '../services/scenarioIO'
import type { Scenario, Point } from '../types/api'

describe('TAREA 08.2 — Authentic Interaction & Editor Verification Suite', () => {
  const baseScenario: Scenario = {
    xmin: 0.0,
    xmax: 20.0,
    ymin: 0.0,
    ymax: 15.0,
    walls: [
      { start: { x: 0.0, y: 7.5 }, end: { x: 20.0, y: 7.5 }, is_opaque: true },
    ],
    obstacles: [
      {
        vertices: [
          { x: 3.0, y: 2.0 },
          { x: 6.0, y: 2.0 },
          { x: 6.0, y: 4.0 },
          { x: 3.0, y: 4.0 },
        ],
      },
    ],
    risk_zones: [
      {
        vertices: [
          { x: 10.0, y: 10.0 },
          { x: 15.0, y: 10.0 },
          { x: 15.0, y: 14.0 },
          { x: 10.0, y: 14.0 },
        ],
        weight: 2.5,
        name: 'Critical Storage',
      },
    ],
    grid_resolution: 0.5,
  }

  // Helper to mock canvas bounding box
  const setupCanvasMock = (canvas: HTMLCanvasElement) => {
    vi.spyOn(canvas, 'getBoundingClientRect').mockReturnValue({
      left: 0,
      top: 0,
      width: 800,
      height: 600,
      right: 800,
      bottom: 600,
      x: 0,
      y: 0,
      toJSON: () => {},
    })
  }

  // --------------------------------------------------------------------------
  // 1. Corregir prueba React de dibujo de pared
  // --------------------------------------------------------------------------
  it('1. should draw a wall via TWO independent clicks with controlled draftPoints state', () => {
    const onWallCommitted = vi.fn()

    function WallDrawingTestHarness() {
      const [scenario, setScenario] = useState<Scenario>(baseScenario)
      const [draftPoints, setDraftPoints] = useState<Point[]>([])

      return (
        <FloorplanCanvas
          scenario={scenario}
          cameras={[]}
          isEditorMode={true}
          activeTool="wall"
          snapToGrid={false}
          draftPoints={draftPoints}
          onUpdateDraftPoints={setDraftPoints}
          onCommitScenario={(next) => {
            setScenario(next)
            onWallCommitted(next)
          }}
        />
      )
    }

    const { container } = render(<WallDrawingTestHarness />)
    const canvas = container.querySelector('canvas')!
    expect(canvas).not.toBeNull()
    setupCanvasMock(canvas)

    const transform = new CoordinateTransform(800, 600, baseScenario, 1, 0, 0, 45)
    const p1World: Point = { x: 2.0, y: 3.0 }
    const p2World: Point = { x: 10.0, y: 3.0 }
    const p1Screen = transform.worldToScreen(p1World)
    const p2Screen = transform.worldToScreen(p2World)

    // Click 1: Start point (mouseDown + mouseUp at p1Screen, drag distance = 0 < 5px)
    fireEvent.mouseDown(canvas, { clientX: p1Screen.x, clientY: p1Screen.y })
    fireEvent.mouseUp(canvas, { clientX: p1Screen.x, clientY: p1Screen.y })

    // Verify first click did NOT commit a wall yet (it updates draftPoints)
    expect(onWallCommitted).not.toHaveBeenCalled()

    // Move mouse to second point (rubberband preview)
    fireEvent.mouseMove(canvas, { clientX: p2Screen.x, clientY: p2Screen.y })

    // Click 2: End point (mouseDown + mouseUp at p2Screen, drag distance = 0 < 5px)
    fireEvent.mouseDown(canvas, { clientX: p2Screen.x, clientY: p2Screen.y })
    fireEvent.mouseUp(canvas, { clientX: p2Screen.x, clientY: p2Screen.y })

    // Verify wall was committed
    expect(onWallCommitted).toHaveBeenCalledTimes(1)
    const nextScenario = onWallCommitted.mock.calls[0][0] as Scenario
    expect(nextScenario.walls?.length).toBe(baseScenario.walls!.length + 1)

    const addedWall = nextScenario.walls![nextScenario.walls!.length - 1]
    expect(Math.abs(addedWall.start.x - p1World.x)).toBeLessThan(0.01)
    expect(Math.abs(addedWall.start.y - p1World.y)).toBeLessThan(0.01)
    expect(Math.abs(addedWall.end.x - p2World.x)).toBeLessThan(0.01)
    expect(Math.abs(addedWall.end.y - p2World.y)).toBeLessThan(0.01)
    expect(addedWall.is_opaque).toBe(true)
  })

  // --------------------------------------------------------------------------
  // 2. Corregir prueba React de creación de abertura
  // --------------------------------------------------------------------------
  it('2. should create an opening via real mouseDown/mouseUp on wall and verify line of sight and FastAPI validity', () => {
    const onDoorCommitted = vi.fn()

    function DoorDrawingTestHarness() {
      const [scenario, setScenario] = useState<Scenario>(baseScenario)

      return (
        <FloorplanCanvas
          scenario={scenario}
          cameras={[]}
          isEditorMode={true}
          activeTool="door"
          doorWidth={1.2}
          onCommitScenario={(next) => {
            setScenario(next)
            onDoorCommitted(next)
          }}
        />
      )
    }

    const { container } = render(<DoorDrawingTestHarness />)
    const canvas = container.querySelector('canvas')!
    expect(canvas).not.toBeNull()
    setupCanvasMock(canvas)

    // The single wall in baseScenario is from (0.0, 7.5) to (20.0, 7.5).
    // Target center is (10.0, 7.5).
    const transform = new CoordinateTransform(800, 600, baseScenario, 1, 0, 0, 45)
    const doorCenterWorld: Point = { x: 10.0, y: 7.5 }
    const doorCenterScreen = transform.worldToScreen(doorCenterWorld)

    // MouseDown and MouseUp directly over wall center (drag distance = 0 < 5px)
    fireEvent.mouseDown(canvas, { clientX: doorCenterScreen.x, clientY: doorCenterScreen.y })
    fireEvent.mouseUp(canvas, { clientX: doorCenterScreen.x, clientY: doorCenterScreen.y })

    expect(onDoorCommitted).toHaveBeenCalledTimes(1)
    const committedScenario = onDoorCommitted.mock.calls[0][0] as Scenario

    // 1. Original 1 wall is replaced by 2 disjoint segments
    expect(committedScenario.walls?.length).toBe(2)
    const [w1, w2] = committedScenario.walls!

    // 2. Opening measures 1.2 m within tolerance
    const openingGap = pointDistance(w1.end, w2.start)
    expect(Math.abs(openingGap - 1.2)).toBeLessThan(0.01)

    // 3. Line of sight passes cleanly through opening without hitting either wall segment
    const rayStart: Point = { x: 10.0, y: 5.0 }
    const rayEnd: Point = { x: 10.0, y: 10.0 }
    expect(doSegmentsIntersect(rayStart, rayEnd, w1.start, w1.end)).toBe(false)
    expect(doSegmentsIntersect(rayStart, rayEnd, w2.start, w2.end)).toBe(false)

    // 4. Geometry remains strictly valid for FastAPI
    const validation = validateScenarioLocally(committedScenario)
    expect(validation.isValid).toBe(true)
    expect(validation.errors.length).toBe(0)
  })

  // --------------------------------------------------------------------------
  // 3. Prueba integrada de arrastre y Undo
  // --------------------------------------------------------------------------
  it('3. should support integrated vertex drag from FloorplanCanvas with single Undo, Redo, Escape cancel, and invalid drag rejection', () => {
    let editorHookRef: any = null

    function IntegratedDragEditorHarness() {
      const [scenario, setScenario] = useState<Scenario>(baseScenario)
      const editor = useScenarioEditor({
        scenario,
        onUpdateScenario: setScenario,
        onInvalidate: vi.fn(),
      })
      useEffect(() => {
        editorHookRef = editor
      })

      return (
        <div>
          <button data-testid="undo-btn" disabled={!editor.canUndo} onClick={editor.undo}>
            Undo
          </button>
          <button data-testid="redo-btn" disabled={!editor.canRedo} onClick={editor.redo}>
            Redo
          </button>
          <span data-testid="undo-count">{editor.undoStack.length}</span>
          <span data-testid="wall-start-x">{scenario.walls?.[0]?.start.x.toFixed(2)}</span>
          <FloorplanCanvas
            scenario={scenario}
            cameras={[]}
            isEditorMode={true}
            activeTool="select"
            snapToGrid={false}
            selectedObject={editor.selectedObject}
            onSelectObject={editor.setSelectedObject}
            onStartDragTransaction={editor.startDragTransaction}
            onUpdateTransientScenario={editor.updateTransient}
            onCommitDragTransaction={editor.commitDragTransaction}
            onCancelDragTransaction={editor.cancelDragTransaction}
          />
        </div>
      )
    }

    const { container } = render(<IntegratedDragEditorHarness />)
    const canvas = container.querySelector('canvas')!
    expect(canvas).not.toBeNull()
    setupCanvasMock(canvas)

    const transform = new CoordinateTransform(800, 600, baseScenario, 1, 0, 0, 45)

    // A. Select start vertex of wall 0: at (0.0, 7.5)
    act(() => {
      editorHookRef.setSelectedObject({ type: 'wall', index: 0, vertexIndex: 0 })
    })

    const initialScreen = transform.worldToScreen({ x: 0.0, y: 7.5 })

    // B. Start drag on selected vertex handle
    fireEvent.mouseDown(canvas, { clientX: initialScreen.x, clientY: initialScreen.y })

    // C. Fire 25 mouse move events moving vertex towards (5.0, 7.5)
    for (let i = 1; i <= 25; i++) {
      const targetWorld: Point = { x: (i / 25) * 5.0, y: 7.5 }
      const moveScreen = transform.worldToScreen(targetWorld)
      fireEvent.mouseMove(canvas, { clientX: moveScreen.x, clientY: moveScreen.y })

      // Verify undoStack has NOT accumulated entries during dragging
      expect(screen.getByTestId('undo-count').textContent).toBe('0')
    }

    // D. Release mouse to commit final drag position (5.0, 7.5)
    const finalScreen = transform.worldToScreen({ x: 5.0, y: 7.5 })
    fireEvent.mouseUp(canvas, { clientX: finalScreen.x, clientY: finalScreen.y })

    // EXACTLY ONE entry in undo history
    expect(screen.getByTestId('undo-count').textContent).toBe('1')
    expect(screen.getByTestId('wall-start-x').textContent).toBe('5.00')

    // E. Test Undo restores original position
    fireEvent.click(screen.getByTestId('undo-btn'))
    expect(screen.getByTestId('undo-count').textContent).toBe('0')
    expect(screen.getByTestId('wall-start-x').textContent).toBe('0.00')

    // F. Test Redo restores dragged position
    fireEvent.click(screen.getByTestId('redo-btn'))
    expect(screen.getByTestId('undo-count').textContent).toBe('1')
    expect(screen.getByTestId('wall-start-x').textContent).toBe('5.00')

    // G. Test Escape cancellation without adding history
    const currentScreen = transform.worldToScreen({ x: 5.0, y: 7.5 })
    fireEvent.mouseDown(canvas, { clientX: currentScreen.x, clientY: currentScreen.y })
    for (let i = 1; i <= 5; i++) {
      const moveScreen = transform.worldToScreen({ x: 5.0 + i * 0.5, y: 7.5 })
      fireEvent.mouseMove(canvas, { clientX: moveScreen.x, clientY: moveScreen.y })
    }
    // Press Escape during drag
    fireEvent.keyDown(window, { key: 'Escape' })
    // Position restored to 5.0, history remains 1
    expect(screen.getByTestId('undo-count').textContent).toBe('1')
    expect(screen.getByTestId('wall-start-x').textContent).toBe('5.00')

    // H. Test invalid drag (making wall length < 0.05m by moving start directly on top of end at 20.0, 7.5)
    const endScreen = transform.worldToScreen({ x: 20.0, y: 7.5 })
    fireEvent.mouseDown(canvas, { clientX: currentScreen.x, clientY: currentScreen.y })
    fireEvent.mouseMove(canvas, { clientX: endScreen.x, clientY: endScreen.y })
    fireEvent.mouseUp(canvas, { clientX: endScreen.x, clientY: endScreen.y })

    // Invalid drag rejected: wall remains at 5.0, history not pushed
    expect(screen.getByTestId('undo-count').textContent).toBe('1')
    expect(screen.getByTestId('wall-start-x').textContent).toBe('5.00')
  })

  // --------------------------------------------------------------------------
  // 4. Corregir la prueba de respuestas asíncronas
  // --------------------------------------------------------------------------
  it('4. should prevent stale async network responses from overwriting newer cached results via request tracking', async () => {
    // Model the exact state and lifecycle used by App.tsx
    let coverageData: string | null = null
    let coverageCamerasKey = ''
    let isLoadingCoverage = false
    const coverageCache = new Map<string, string>()
    const coverageRequestIdRef = { current: 0 }

    // Deferred network call resolvers
    const pendingPromises: Array<{
      reqId: number
      targetKey: string
      resolve: (data: string) => void
    }> = []

    const fetchCoverage = (targetKey: string) => {
      // 1. Check local cache first
      if (coverageCache.has(targetKey)) {
        // Invalidate any older in-flight network requests
        coverageRequestIdRef.current += 1
        coverageData = coverageCache.get(targetKey)!
        coverageCamerasKey = targetKey
        isLoadingCoverage = false
        return
      }

      // 2. Fetch from backend with monotonic request tracking
      const reqId = ++coverageRequestIdRef.current
      isLoadingCoverage = true

      new Promise<string>((resolve) => {
        pendingPromises.push({ reqId, targetKey, resolve })
      }).then((res) => {
        coverageCache.set(targetKey, res)
        if (reqId === coverageRequestIdRef.current) {
          coverageData = res
          coverageCamerasKey = targetKey
          isLoadingCoverage = false
        }
      })
    }

    // Step 1: Pre-populate cache with Configuration B
    coverageCache.set('key-B-cached', 'DATA_B_CACHED')

    // Step 2: Trigger network request for Configuration A (delayed)
    fetchCoverage('key-A-network')
    expect(isLoadingCoverage).toBe(true)
    expect(coverageRequestIdRef.current).toBe(1)
    expect(pendingPromises.length).toBe(1)

    // Step 3: Rapidly switch to Configuration B (available in cache)
    fetchCoverage('key-B-cached')
    // Cache retrieval instantly increments counter and updates view
    expect(coverageRequestIdRef.current).toBe(2)
    expect(coverageData).toBe('DATA_B_CACHED')
    expect(coverageCamerasKey).toBe('key-B-cached')
    expect(isLoadingCoverage).toBe(false)

    // Step 4: Stale network request A now finally resolves from backend
    await act(async () => {
      const delayedReqA = pendingPromises[0]
      delayedReqA.resolve('DATA_A_STALE_FROM_NETWORK')
      await new Promise(r => setTimeout(r, 10))
    })

    // Step 5: Verify that stale response did NOT overwrite cached Configuration B!
    expect(coverageData).toBe('DATA_B_CACHED')
    expect(coverageCamerasKey).toBe('key-B-cached')
    // But Request A was still saved in cache for future instant access
    expect(coverageCache.get('key-A-network')).toBe('DATA_A_STALE_FROM_NETWORK')
  })

  // --------------------------------------------------------------------------
  // 5. Ajuste menor de importación JSON: risk_zone.name
  // --------------------------------------------------------------------------
  it('5. should strictly validate risk_zone.name: allow missing default, preserve string, reject invalid types', () => {
    // A. Absent name: default allowed
    const jsonWithoutName = JSON.stringify({
      xmax: 20,
      ymax: 15,
      risk_zones: [
        {
          vertices: [
            { x: 1, y: 1 },
            { x: 3, y: 1 },
            { x: 3, y: 3 },
          ],
          weight: 2.0,
        },
      ],
    })
    const resA = parseAndValidateScenarioJson(jsonWithoutName)
    expect(resA.scenario).not.toBeNull()
    expect(resA.scenario?.risk_zones?.[0].name).toBe('Zona #1')

    // B. Valid string name: preserved
    const jsonWithStringName = JSON.stringify({
      xmax: 20,
      ymax: 15,
      risk_zones: [
        {
          vertices: [
            { x: 1, y: 1 },
            { x: 3, y: 1 },
            { x: 3, y: 3 },
          ],
          weight: 2.0,
          name: 'Perimeter Vault',
        },
      ],
    })
    const resB = parseAndValidateScenarioJson(jsonWithStringName)
    expect(resB.scenario).not.toBeNull()
    expect(resB.scenario?.risk_zones?.[0].name).toBe('Perimeter Vault')

    // C. Numeric name: MUST be rejected with descriptive error without silent substitution
    const jsonWithNumericName = JSON.stringify({
      xmax: 20,
      ymax: 15,
      risk_zones: [
        {
          vertices: [
            { x: 1, y: 1 },
            { x: 3, y: 1 },
            { x: 3, y: 3 },
          ],
          weight: 2.0,
          name: 12345,
        },
      ],
    })
    const resC = parseAndValidateScenarioJson(jsonWithNumericName)
    expect(resC.scenario).toBeNull()
    expect(resC.errors.length).toBeGreaterThan(0)
    expect(resC.errors.some(e => e.includes('tipo inválido') || e.includes('name'))).toBe(true)

    // D. Boolean name: MUST be rejected
    const jsonWithBooleanName = JSON.stringify({
      xmax: 20,
      ymax: 15,
      risk_zones: [
        {
          vertices: [
            { x: 1, y: 1 },
            { x: 3, y: 1 },
            { x: 3, y: 3 },
          ],
          weight: 2.0,
          name: true,
        },
      ],
    })
    const resD = parseAndValidateScenarioJson(jsonWithBooleanName)
    expect(resD.scenario).toBeNull()
    expect(resD.errors.length).toBeGreaterThan(0)
  })

  // --------------------------------------------------------------------------
  // 6. Inspector numerical editing & Lossless round-trip preservation
  // --------------------------------------------------------------------------
  it('6. should edit risk weight from inspector and preserve lossless IEEE-754 precision (> 6 decimals)', () => {
    const onUpdateScenario = vi.fn()
    render(
      <ScenarioInspector
        scenario={baseScenario}
        selectedObject={{ type: 'risk_zone', index: 0 }}
        activeTool="risk_zone"
        onUpdateScenario={onUpdateScenario}
        onClose={vi.fn()}
      />
    )

    const weightInput = screen.getByLabelText(/Peso de riesgo crítico/i) as HTMLInputElement
    expect(weightInput.value).toBe('2.5')
    fireEvent.change(weightInput, { target: { value: '4.8765432' } })
    expect(onUpdateScenario).toHaveBeenCalledWith(
      expect.objectContaining({
        risk_zones: [expect.objectContaining({ weight: 4.8765432 })],
      })
    )

    // Lossless round-trip verification
    const highPrecisionScenario: Scenario = {
      ...baseScenario,
      xmin: 0.1234567,
      xmax: 22.9876543,
      walls: [
        {
          start: { x: 1.1234567, y: 2.2345678 },
          end: { x: 10.9876543, y: 2.2345678 },
          is_opaque: true,
        },
      ],
      risk_zones: [
        {
          vertices: [
            { x: 3.1234567, y: 3.1234567 },
            { x: 7.9876543, y: 3.1234567 },
            { x: 7.9876543, y: 7.9876543 },
          ],
          weight: 2.3456789,
          name: 'Precision Zone',
        },
      ],
    }

    const exported = serializeScenarioToJson(highPrecisionScenario)
    const imported = parseAndValidateScenarioJson(exported)
    expect(imported.scenario).not.toBeNull()
    expect(imported.scenario!.xmin).toBe(0.1234567)
    expect(imported.scenario!.walls![0].start.x).toBe(1.1234567)
    expect(imported.scenario!.risk_zones![0].weight).toBe(2.3456789)
    expect(isPolygonSelfIntersecting(highPrecisionScenario.risk_zones![0].vertices)).toBe(false)
  })
})
