import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Compass,
  Eye,
  Layers,
  Maximize2,
  RefreshCw,
  Sliders,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'
import { CoordinateTransform } from '../renderer/coordinateTransform'
import { FloorplanRenderer } from '../renderer/floorplanRenderer'
import {
  isPointInsidePolygon,
  isPolygonSelfIntersecting,
  pointDistance,
  pointToSegmentDistance,
  snapPoint,
  splitWallWithOpening,
  validateScenarioLocally,
} from '../renderer/geometryValidation'
import type {
  CameraPose,
  CameraProfile,
  CanvasViewMode,
  CoverageEvaluationResponse,
  CoverageGridNode,
  Point,
  Scenario,
  Wall,
} from '../types/api'
import type { EditorTool, SelectedObject } from '../types/editor'

interface FloorplanCanvasProps {
  scenario: Scenario
  cameras: CameraPose[]
  profile?: CameraProfile | null
  cameraColorMode?: 'best' | 'individual'
  selectedCameraIndex?: number | null
  onSelectCameraIndex?: (index: number | null) => void
  // Coverage Heatmap Layer
  coverageData?: CoverageEvaluationResponse | null
  viewMode?: CanvasViewMode
  onChangeViewMode?: (mode: CanvasViewMode) => void
  coverageOpacity?: number
  onChangeCoverageOpacity?: (opacity: number) => void
  onRequestRefreshCoverage?: () => void
  isLoadingCoverage?: boolean
  // Editor mode props
  isEditorMode?: boolean
  activeTool?: EditorTool
  selectedObject?: SelectedObject | null
  onSelectObject?: (obj: SelectedObject | null) => void
  snapToGrid?: boolean
  snapSize?: number
  doorWidth?: number
  draftPoints?: Point[]
  onUpdateDraftPoints?: (pts: Point[]) => void
  onCommitScenario?: (sc: Scenario) => void
  onStartDragTransaction?: () => void
  onUpdateTransientScenario?: (sc: Scenario) => void
  onCommitDragTransaction?: (sc: Scenario) => void
  onCancelDragTransaction?: () => void
  onNotify?: (notification: { type: 'success' | 'error' | 'info'; message: string }) => void
  onMouseMoveCoords?: (coords: { x: number; y: number } | null) => void
}

export const FloorplanCanvas: React.FC<FloorplanCanvasProps> = ({
  scenario,
  cameras,
  profile,
  cameraColorMode = 'best',
  selectedCameraIndex = null,
  onSelectCameraIndex,
  coverageData = null,
  viewMode = 'floorplan',
  onChangeViewMode,
  coverageOpacity = 0.75,
  onChangeCoverageOpacity,
  onRequestRefreshCoverage,
  isLoadingCoverage = false,
  isEditorMode = false,
  activeTool = 'select',
  selectedObject = null,
  onSelectObject,
  snapToGrid = true,
  snapSize = 0.5,
  doorWidth = 1.0,
  draftPoints = [],
  onUpdateDraftPoints,
  onCommitScenario,
  onStartDragTransaction,
  onUpdateTransientScenario,
  onCommitDragTransaction,
  onCancelDragTransaction,
  onNotify,
  onMouseMoveCoords,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const clickStartRef = useRef<{ clientX: number; clientY: number }>({ clientX: 0, clientY: 0 })
  const latestDraggedScenarioRef = useRef<Scenario | null>(null)

  const [containerDimensions, setContainerDimensions] = useState<{ width: number; height: number }>({
    width: 600,
    height: 400,
  })
  const [zoom, setZoom] = useState(1.0)
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 })
  const [mouseWorld, setMouseWorld] = useState<{ x: number; y: number } | null>(null)

  // Dragging vertex state for editor
  const [isDraggingVertex, setIsDraggingVertex] = useState(false)

  // Hovered wall for door opening preview
  const [hoveredWallForDoor, setHoveredWallForDoor] = useState<{
    wall: Wall
    openingStart: Point
    openingEnd: Point
  } | null>(null)

  // Camera nominal FOV cones visibility (default true for floorplan, false for heatmaps per Requirement 7)
  const [prevViewMode, setPrevViewMode] = useState<string>(viewMode)
  const [showCameraCones, setShowCameraCones] = useState<boolean>(viewMode === 'floorplan')

  if (viewMode !== prevViewMode) {
    setPrevViewMode(viewMode)
    setShowCameraCones(viewMode === 'floorplan')
  }

  // 1. Observe container resize explicitly with ResizeObserver
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const updateDimensions = () => {
      const rect = container.getBoundingClientRect()
      const w = Math.max(50, Math.floor(rect.width))
      const h = Math.max(50, Math.floor(rect.height))
      setContainerDimensions(prev => (prev.width !== w || prev.height !== h ? { width: w, height: h } : prev))
    }

    updateDimensions()

    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(() => {
        updateDimensions()
      })
      observer.observe(container)
      return () => {
        observer.disconnect()
      }
    }
  }, [])

  // 2. Computed Snapped Mouse Point in World Coordinates
  const snappedMouseWorld = useMemo(() => {
    if (!mouseWorld) return null
    if (isEditorMode && snapToGrid) {
      return snapPoint(mouseWorld, snapSize)
    }
    return mouseWorld
  }, [mouseWorld, isEditorMode, snapToGrid, snapSize])

  // 3. Redraw canvas whenever inputs, cameras, profile, zoom, pan, coverage data, or dimensions change
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const { width, height } = containerDimensions
    const dpr = window.devicePixelRatio || 1

    canvas.width = width * dpr
    canvas.height = height * dpr
    canvas.style.width = `${width}px`
    canvas.style.height = `${height}px`

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.save()
    ctx.scale(dpr, dpr)

    const transform = new CoordinateTransform(width, height, scenario, zoom, pan.x, pan.y, 45)
    if (typeof window !== 'undefined') {
      ;(window as any).__floorplanTransform = transform
      ;(window as any).__floorplanSelectObject = onSelectObject
    }
    const renderer = new FloorplanRenderer(ctx)

    renderer.render({
      scenario,
      cameras,
      profile,
      transform,
      selectedCameraIndex,
      cameraColorMode,
      coverageNodes: coverageData?.nodes,
      cellWidth: coverageData?.cell_width,
      cellHeight: coverageData?.cell_height,
      viewMode,
      coverageOpacity,
      showCameraCones,
      // Editor overlays
      isEditorMode,
      activeTool,
      selectedObject,
      draftPoints,
      snappedCursor: isEditorMode ? snappedMouseWorld : null,
      hoveredWallForDoor: isEditorMode && activeTool === 'door' ? hoveredWallForDoor : null,
    })

    ctx.restore()
  }, [
    scenario,
    cameras,
    profile,
    zoom,
    pan,
    selectedCameraIndex,
    cameraColorMode,
    containerDimensions,
    coverageData,
    viewMode,
    coverageOpacity,
    showCameraCones,
    isEditorMode,
    activeTool,
    selectedObject,
    draftPoints,
    snappedMouseWorld,
    hoveredWallForDoor,
  ])

  // Helper to find closest object under cursor for selection
  const findObjectAtPoint = useCallback(
    (screenPt: { x: number; y: number }, worldPt: Point, transform: CoordinateTransform): SelectedObject | null => {
      // 1. Check vertex handles of selected object first
      if (selectedObject) {
        if (selectedObject.type === 'wall' && scenario.walls && scenario.walls[selectedObject.index]) {
          const w = scenario.walls[selectedObject.index]
          const s1 = transform.worldToScreen(w.start)
          const s2 = transform.worldToScreen(w.end)
          if (Math.hypot(s1.x - screenPt.x, s1.y - screenPt.y) <= 12) {
            return { type: 'wall', index: selectedObject.index, vertexIndex: 0 }
          }
          if (Math.hypot(s2.x - screenPt.x, s2.y - screenPt.y) <= 12) {
            return { type: 'wall', index: selectedObject.index, vertexIndex: 1 }
          }
        } else if (selectedObject.type === 'obstacle' && scenario.obstacles && scenario.obstacles[selectedObject.index]) {
          const obs = scenario.obstacles[selectedObject.index]
          for (let i = 0; i < obs.vertices.length; i++) {
            const sv = transform.worldToScreen(obs.vertices[i])
            if (Math.hypot(sv.x - screenPt.x, sv.y - screenPt.y) <= 12) {
              return { type: 'obstacle', index: selectedObject.index, vertexIndex: i }
            }
          }
        } else if (selectedObject.type === 'risk_zone' && scenario.risk_zones && scenario.risk_zones[selectedObject.index]) {
          const rz = scenario.risk_zones[selectedObject.index]
          for (let i = 0; i < rz.vertices.length; i++) {
            const sv = transform.worldToScreen(rz.vertices[i])
            if (Math.hypot(sv.x - screenPt.x, sv.y - screenPt.y) <= 12) {
              return { type: 'risk_zone', index: selectedObject.index, vertexIndex: i }
            }
          }
        }
      }

      // 2. Check walls (tolerance: 10px on screen)
      if (scenario.walls) {
        for (let i = 0; i < scenario.walls.length; i++) {
          const w = scenario.walls[i]
          const { distance } = pointToSegmentDistance(worldPt, w.start, w.end)
          const pxDist = transform.distanceToPixels(distance)
          if (pxDist <= 10) {
            return { type: 'wall', index: i }
          }
        }
      }

      // 3. Check obstacles (inside polygon or within 10px)
      if (scenario.obstacles) {
        for (let i = 0; i < scenario.obstacles.length; i++) {
          const obs = scenario.obstacles[i]
          if (isPointInsidePolygon(worldPt, obs.vertices)) {
            return { type: 'obstacle', index: i }
          }
          for (let j = 0; j < obs.vertices.length; j++) {
            const p1 = obs.vertices[j]
            const p2 = obs.vertices[(j + 1) % obs.vertices.length]
            const { distance } = pointToSegmentDistance(worldPt, p1, p2)
            if (transform.distanceToPixels(distance) <= 8) {
              return { type: 'obstacle', index: i }
            }
          }
        }
      }

      // 4. Check risk zones
      if (scenario.risk_zones) {
        for (let i = 0; i < scenario.risk_zones.length; i++) {
          const rz = scenario.risk_zones[i]
          if (isPointInsidePolygon(worldPt, rz.vertices)) {
            return { type: 'risk_zone', index: i }
          }
          for (let j = 0; j < rz.vertices.length; j++) {
            const p1 = rz.vertices[j]
            const p2 = rz.vertices[(j + 1) % rz.vertices.length]
            const { distance } = pointToSegmentDistance(worldPt, p1, p2)
            if (transform.distanceToPixels(distance) <= 8) {
              return { type: 'risk_zone', index: i }
            }
          }
        }
      }

      return null
    },
    [scenario, selectedObject]
  )

  // Mouse interaction: Wheel Zoom
  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault()
    const factor = e.deltaY < 0 ? 1.15 : 0.87
    setZoom(prev => Math.max(0.3, Math.min(6.0, prev * factor)))
  }

  // Mouse interaction: Mouse Down
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const mouseX = e.clientX - rect.left
    const mouseY = e.clientY - rect.top

    clickStartRef.current = { clientX: e.clientX, clientY: e.clientY }

    const transform = new CoordinateTransform(
      containerDimensions.width,
      containerDimensions.height,
      scenario,
      zoom,
      pan.x,
      pan.y,
      45
    )
    const worldPt = transform.screenToWorld({ x: mouseX, y: mouseY })

    // Middle click or right click always pans
    if (e.button === 1 || e.button === 2) {
      setIsDragging(true)
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y })
      return
    }

    // In Editor Mode
    if (isEditorMode) {
      if (activeTool === 'select') {
        const found = findObjectAtPoint({ x: mouseX, y: mouseY }, worldPt, transform)
        if (found) {
          onSelectObject?.(found)
          // If clicked a vertex handle of already selected object, start dragging vertex
          if (found.vertexIndex !== undefined && found.vertexIndex !== null) {
            setIsDraggingVertex(true)
            latestDraggedScenarioRef.current = null
            onStartDragTransaction?.()
            return
          }
          return
        } else {
          // Deselect and start panning canvas on empty space
          onSelectObject?.(null)
          setIsDragging(true)
          setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y })
          return
        }
      }

      // Drawing tools handle their own clicks on mouseUp to avoid accidental drags
      return
    }

    // In Regular View Mode (non-editor): default drag pan
    setIsDragging(true)
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y })
  }

  // Mouse interaction: Mouse Move
  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const mouseX = e.clientX - rect.left
    const mouseY = e.clientY - rect.top

    const transform = new CoordinateTransform(
      containerDimensions.width,
      containerDimensions.height,
      scenario,
      zoom,
      pan.x,
      pan.y,
      45
    )
    const worldPt = transform.screenToWorld({ x: mouseX, y: mouseY })
    setMouseWorld(worldPt)

    const snappedPt = isEditorMode && snapToGrid ? snapPoint(worldPt, snapSize) : worldPt
    onMouseMoveCoords?.(snappedPt)

    // 1. Panning canvas
    if (isDragging) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      })
      return
    }

    // 2. Dragging vertex in editor (transient update without committing undo step)
    if (isDraggingVertex && selectedObject && snappedPt) {
      let updatedScenario: Scenario | null = null

      if (selectedObject.type === 'wall' && scenario.walls && scenario.walls[selectedObject.index]) {
        const wall = scenario.walls[selectedObject.index]
        const updatedWall = { ...wall }
        if (selectedObject.vertexIndex === 0) {
          updatedWall.start = { ...snappedPt }
        } else if (selectedObject.vertexIndex === 1) {
          updatedWall.end = { ...snappedPt }
        }
        const nextWalls = [...scenario.walls]
        nextWalls[selectedObject.index] = updatedWall
        updatedScenario = { ...scenario, walls: nextWalls }
      } else if (
        selectedObject.type === 'obstacle' &&
        scenario.obstacles &&
        scenario.obstacles[selectedObject.index] &&
        selectedObject.vertexIndex !== undefined &&
        selectedObject.vertexIndex !== null
      ) {
        const obs = scenario.obstacles[selectedObject.index]
        const nextVerts = obs.vertices.map((v, i) => (i === selectedObject.vertexIndex ? { ...snappedPt } : v))
        const nextObs = [...scenario.obstacles]
        nextObs[selectedObject.index] = { ...obs, vertices: nextVerts }
        updatedScenario = { ...scenario, obstacles: nextObs }
      } else if (
        selectedObject.type === 'risk_zone' &&
        scenario.risk_zones &&
        scenario.risk_zones[selectedObject.index] &&
        selectedObject.vertexIndex !== undefined &&
        selectedObject.vertexIndex !== null
      ) {
        const rz = scenario.risk_zones[selectedObject.index]
        const nextVerts = rz.vertices.map((v, i) => (i === selectedObject.vertexIndex ? { ...snappedPt } : v))
        const nextRz = [...scenario.risk_zones]
        nextRz[selectedObject.index] = { ...rz, vertices: nextVerts }
        updatedScenario = { ...scenario, risk_zones: nextRz }
      }

      if (updatedScenario) {
        latestDraggedScenarioRef.current = updatedScenario
        if (onUpdateTransientScenario) {
          onUpdateTransientScenario(updatedScenario)
        } else if (onCommitScenario) {
          onCommitScenario(updatedScenario)
        }
      }
      return
    }

    // 3. Hovering for Door Opening Preview
    if (isEditorMode && activeTool === 'door' && scenario.walls) {
      let closestWall: Wall | null = null
      let minDist = Infinity
      for (const w of scenario.walls) {
        const { distance } = pointToSegmentDistance(worldPt, w.start, w.end)
        if (distance < minDist) {
          minDist = distance
          closestWall = w
        }
      }

      if (closestWall && minDist <= 1.0) {
        const splitRes = splitWallWithOpening(closestWall, worldPt, doorWidth)
        if (splitRes.valid && splitRes.walls.length === 2) {
          setHoveredWallForDoor({
            wall: closestWall,
            openingStart: splitRes.walls[0].end,
            openingEnd: splitRes.walls[1].start,
          })
        } else {
          setHoveredWallForDoor(null)
        }
      } else {
        setHoveredWallForDoor(null)
      }
    } else {
      if (hoveredWallForDoor) setHoveredWallForDoor(null)
    }
  }

  // Mouse interaction: Mouse Up / Click completion
  const handleMouseUp = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const dragDistance = Math.hypot(
      e.clientX - clickStartRef.current.clientX,
      e.clientY - clickStartRef.current.clientY
    )

    if (isDragging) {
      setIsDragging(false)
    }
    if (isDraggingVertex) {
      setIsDraggingVertex(false)
      if (latestDraggedScenarioRef.current) {
        const finalScenario = latestDraggedScenarioRef.current
        latestDraggedScenarioRef.current = null

        // Validate final geometry before committing transaction
        const validation = validateScenarioLocally(finalScenario)
        if (!validation.isValid) {
          onNotify?.({
            type: 'error',
            message: validation.errors[0] || 'Geometría resultante inválida al soltar vértice.',
          })
          onCancelDragTransaction?.()
          return
        }

        if (onCommitDragTransaction) {
          onCommitDragTransaction(finalScenario)
        } else if (onCommitScenario) {
          onCommitScenario(finalScenario)
        }
      } else {
        onCancelDragTransaction?.()
      }
      return
    }

    // If mouse was dragged > 5px, it's a pan drag, not a click action
    if (dragDistance >= 5) {
      return
    }

    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const mouseX = e.clientX - rect.left
    const mouseY = e.clientY - rect.top

    const transform = new CoordinateTransform(
      containerDimensions.width,
      containerDimensions.height,
      scenario,
      zoom,
      pan.x,
      pan.y,
      45
    )
    const worldPt = transform.screenToWorld({ x: mouseX, y: mouseY })
    const snappedPt = snapToGrid ? snapPoint(worldPt, snapSize) : worldPt

    // --- Non-editor mode: camera selection ---
    if (!isEditorMode) {
      if (onSelectCameraIndex && cameras.length > 0) {
        let closestIndex: number | null = null
        let minDistancePx = Infinity
        const SELECTION_RADIUS_PX = 20

        cameras.forEach((cam, idx) => {
          const screenPos = transform.worldToScreen({ x: cam.x, y: cam.y })
          const distPx = Math.hypot(screenPos.x - mouseX, screenPos.y - mouseY)
          if (distPx <= SELECTION_RADIUS_PX && distPx < minDistancePx) {
            minDistancePx = distPx
            closestIndex = idx
          }
        })
        onSelectCameraIndex(closestIndex)
      } else if (onSelectCameraIndex) {
        onSelectCameraIndex(null)
      }
      return
    }

    // --- Editor mode tools ---
    // 1. Tool Wall: 2 clicks to place wall
    if (activeTool === 'wall' && onUpdateDraftPoints && onCommitScenario) {
      if (draftPoints.length === 0) {
        onUpdateDraftPoints([snappedPt])
      } else {
        const startPt = draftPoints[0]
        const len = pointDistance(startPt, snappedPt)
        if (len < 0.05) {
          onNotify?.({
            type: 'error',
            message: 'Longitud de pared insuficiente (mínimo 0.05 m).',
          })
          return
        }

        const newWall: Wall = {
          start: { ...startPt },
          end: { ...snappedPt },
          is_opaque: true,
        }

        const nextWalls = [...(scenario.walls || []), newWall]
        onCommitScenario({ ...scenario, walls: nextWalls })
        onUpdateDraftPoints([])
        onNotify?.({
          type: 'success',
          message: `Pared de ${len.toFixed(2)} m agregada con éxito.`,
        })
      }
      return
    }

    // 2. Tool Door: click on wall to split with opening
    if (activeTool === 'door' && onCommitScenario) {
      if (!scenario.walls || scenario.walls.length === 0) {
        onNotify?.({
          type: 'error',
          message: 'No hay paredes en el escenario para crear una abertura.',
        })
        return
      }

      let closestWall: Wall | null = null
      let closestIdx = -1
      let minDist = Infinity

      scenario.walls.forEach((w, idx) => {
        const { distance } = pointToSegmentDistance(worldPt, w.start, w.end)
        if (distance < minDist) {
          minDist = distance
          closestWall = w
          closestIdx = idx
        }
      })

      if (closestWall && minDist <= 1.0 && closestIdx >= 0) {
        const splitRes = splitWallWithOpening(closestWall, worldPt, doorWidth)
        if (!splitRes.valid) {
          onNotify?.({
            type: 'error',
            message: splitRes.error || 'No se puede crear abertura en esta pared.',
          })
          return
        }

        const nextWalls = [...scenario.walls]
        nextWalls.splice(closestIdx, 1, ...splitRes.walls)
        onCommitScenario({ ...scenario, walls: nextWalls })
        setHoveredWallForDoor(null)
        onNotify?.({
          type: 'success',
          message: `Abertura de ${doorWidth.toFixed(2)} m creada, dividiendo la pared en 2 segmentos válidos.`,
        })
      } else {
        onNotify?.({
          type: 'info',
          message: 'Haga clic sobre una pared para crear una abertura.',
        })
      }
      return
    }

    // 3. Tool Obstacle & Tool Risk Zone: multi-click polygon
    if ((activeTool === 'obstacle' || activeTool === 'risk_zone') && onUpdateDraftPoints && onCommitScenario) {
      const isRisk = activeTool === 'risk_zone'

      // Check if clicking near start point to close polygon
      if (draftPoints.length >= 3) {
        const startScreen = transform.worldToScreen(draftPoints[0])
        const distPx = Math.hypot(mouseX - startScreen.x, mouseY - startScreen.y)
        const distMeters = pointDistance(snappedPt, draftPoints[0])

        if (distPx <= 16 || distMeters <= snapSize) {
          // Close polygon
          if (isPolygonSelfIntersecting(draftPoints)) {
            onNotify?.({
              type: 'error',
              message: 'El polígono se autointerseca (no es simple). Reorganice los vértices.',
            })
            return
          }

          if (isRisk) {
            const nextRz = [
              ...(scenario.risk_zones || []),
              {
                vertices: [...draftPoints],
                weight: 2.0,
                name: `Zona de Riesgo #${(scenario.risk_zones?.length || 0) + 1}`,
              },
            ]
            onCommitScenario({ ...scenario, risk_zones: nextRz })
            onNotify?.({
              type: 'success',
              message: 'Zona de riesgo creada exitosamente.',
            })
          } else {
            const nextObs = [
              ...(scenario.obstacles || []),
              {
                vertices: [...draftPoints],
              },
            ]
            onCommitScenario({ ...scenario, obstacles: nextObs })
            onNotify?.({
              type: 'success',
              message: 'Obstáculo poligonal agregado exitosamente.',
            })
          }

          onUpdateDraftPoints([])
          return
        }
      }

      // Add vertex to draft
      onUpdateDraftPoints([...draftPoints, snappedPt])
      return
    }
  }

  // Keyboard shortcuts (Escape to cancel draft, Delete to delete selected object)
  useEffect(() => {
    if (!isEditorMode) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (isDraggingVertex) {
          setIsDraggingVertex(false)
          latestDraggedScenarioRef.current = null
          onCancelDragTransaction?.()
          onNotify?.({
            type: 'info',
            message: 'Arrastre de vértice cancelado.',
          })
          return
        }
        onUpdateDraftPoints?.([])
        onSelectObject?.(null)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [
    isEditorMode,
    isDraggingVertex,
    onUpdateDraftPoints,
    onSelectObject,
    onCancelDragTransaction,
    onNotify,
  ])

  const handleResetView = () => {
    setZoom(1.0)
    setPan({ x: 0, y: 0 })
  }

  const handleZoomIn = () => setZoom(prev => Math.min(6.0, prev * 1.25))
  const handleZoomOut = () => setZoom(prev => Math.max(0.3, prev * 0.8))

  // Find inspected node under cursor
  const hoveredNode: CoverageGridNode | null = useMemo(() => {
    if (!mouseWorld || !coverageData?.nodes || coverageData.nodes.length === 0) return null
    const halfW = (coverageData.cell_width || 1.0) / 2
    const halfH = (coverageData.cell_height || 1.0) / 2

    return (
      coverageData.nodes.find(
        n => Math.abs(n.x - mouseWorld.x) <= halfW && Math.abs(n.y - mouseWorld.y) <= halfH
      ) || null
    )
  }, [mouseWorld, coverageData])

  return (
    <div className="floorplan-container" ref={containerRef}>
      {/* 1. Floating Canvas Layer Controls (Top Center/Left) - shown in inspection mode or when not editing */}
      <div className="canvas-layer-controls">
        <div className="layer-mode-tabs" role="tablist" aria-label="Modos de visualización">
          <button
            type="button"
            role="tab"
            aria-selected={viewMode === 'floorplan'}
            className={`layer-tab-btn ${viewMode === 'floorplan' ? 'active' : ''}`}
            onClick={() => onChangeViewMode?.('floorplan')}
          >
            <Layers className="icon-xs" />
            <span>Plano</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={viewMode === 'probability'}
            className={`layer-tab-btn ${viewMode === 'probability' ? 'active' : ''}`}
            onClick={() => onChangeViewMode?.('probability')}
          >
            <Eye className="icon-xs" />
            <span>Probabilidad</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={viewMode === 'geometric'}
            className={`layer-tab-btn ${viewMode === 'geometric' ? 'active' : ''}`}
            onClick={() => onChangeViewMode?.('geometric')}
          >
            <span title="Cobertura geométrica">Geometría</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={viewMode === 'risk'}
            className={`layer-tab-btn ${viewMode === 'risk' ? 'active' : ''}`}
            onClick={() => onChangeViewMode?.('risk')}
          >
            <span>Riesgo</span>
          </button>
          <div className="layer-tab-divider" />
          <button
            type="button"
            className={`layer-tab-btn btn-cones-toggle ${showCameraCones ? 'active' : ''}`}
            onClick={() => setShowCameraCones(prev => !prev)}
            title={showCameraCones ? 'Ocultar conos nominales de cámaras' : 'Mostrar conos nominales de cámaras'}
            aria-label="Alternar conos nominales de cámaras"
          >
            <Eye className="icon-xs" />
            <span>Conos</span>
          </button>
        </div>

        {/* Opacity slider and refresh button when viewing heatmap */}
        {viewMode !== 'floorplan' && (
          <div className="layer-params-bar">
            <div className="opacity-slider-group">
              <Sliders className="icon-xs text-muted" />
              <label htmlFor="coverage-opacity-slider" className="opacity-label">
                Opacidad: {Math.round(coverageOpacity * 100)}%
              </label>
              <input
                id="coverage-opacity-slider"
                type="range"
                min="0.1"
                max="1.0"
                step="0.05"
                value={coverageOpacity}
                onChange={e => onChangeCoverageOpacity?.(parseFloat(e.target.value))}
                className="opacity-range-input"
                aria-label="Ajustar opacidad del mapa de calor"
              />
            </div>

            {onRequestRefreshCoverage && (
              <button
                type="button"
                className="btn-refresh-coverage"
                onClick={onRequestRefreshCoverage}
                disabled={isLoadingCoverage}
                title="Actualizar evaluación de cobertura del backend"
              >
                <RefreshCw className={`icon-xs ${isLoadingCoverage ? 'spin-animation' : ''}`} />
                <span>{isLoadingCoverage ? 'Evaluando...' : 'Actualizar'}</span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* 2. Floating Canvas Navigation Tools (Top Right) */}
      <div className="canvas-toolbar">
        <button
          type="button"
          className="canvas-btn"
          onClick={handleZoomIn}
          title="Acercar (Rueda del ratón)"
          aria-label="Acercar plano"
        >
          <ZoomIn className="icon-sm" />
        </button>
        <button
          type="button"
          className="canvas-btn"
          onClick={handleZoomOut}
          title="Alejar (Rueda del ratón)"
          aria-label="Alejar plano"
        >
          <ZoomOut className="icon-sm" />
        </button>
        <button
          type="button"
          className="canvas-btn"
          onClick={handleResetView}
          title="Centrar y encuadrar recinto"
          aria-label="Restablecer vista"
        >
          <Maximize2 className="icon-sm" />
        </button>
      </div>

      {/* 3. Real-time Cursor & Node Inspection Badges */}
      <div className="canvas-coords-badge">
        <Compass className="icon-xs text-muted" />
        <span>
          {mouseWorld ? (
            <>
              X: <strong>{mouseWorld.x.toFixed(2)} m</strong>, Y: <strong>{mouseWorld.y.toFixed(2)} m</strong>
            </>
          ) : (
            'Mueva el cursor sobre el plano'
          )}
        </span>
        {hoveredNode && (
          <span className="inspection-node-details">
            | P_det: <strong>{(hoveredNode.probability * 100).toFixed(1)}%</strong> |{' '}
            {hoveredNode.binary_covered ? (
              <span className="text-emerald font-semibold">Visible</span>
            ) : (
              <span className="text-slate font-semibold">No visible</span>
            )}{' '}
            | Riesgo: <strong>{hoveredNode.risk_weight.toFixed(1)}×</strong>
          </span>
        )}
      </div>

      {/* 4. Main Canvas Element */}
      <canvas
        ref={canvasRef}
        className={`floorplan-canvas ${isDragging ? 'dragging' : ''} ${isEditorMode ? `tool-${activeTool}` : ''}`}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => {
          setIsDragging(false)
          setIsDraggingVertex(false)
          setMouseWorld(null)
          onMouseMoveCoords?.(null)
        }}
        onContextMenu={e => e.preventDefault()}
      />

      {/* 5. Dynamic Legend & Footers based on active visualization mode */}
      <div className="canvas-legend-footer">
        {/* Mode: Probabilidad */}
        {viewMode === 'probability' && (
          <div className="probability-legend-container">
            <div className="legend-label-group">
              <span className="legend-title">Probabilidad combinada de detección P_det:</span>
              <div className="gradient-bar-wrapper">
                <div className="probability-gradient-bar" />
                <div className="gradient-ticks">
                  <span>0% (Sin detección)</span>
                  <span>25%</span>
                  <span>50% (Detección media)</span>
                  <span>75%</span>
                  <span>100% (Máxima)</span>
                </div>
              </div>
            </div>
            <div className="legend-meta-summary">
              {coverageData && (
                <span>
                  Nodos: <strong>{coverageData.total_nodes}</strong> | Cobertura media:{' '}
                  <strong>{(coverageData.metrics.mean_probabilistic_coverage * 100).toFixed(1)}%</strong> | Costo:{' '}
                  <strong>{coverageData.objective_cost.toFixed(4)}</strong>
                </span>
              )}
            </div>
          </div>
        )}

        {/* Mode: Cobertura geométrica */}
        {viewMode === 'geometric' && (
          <div className="legend-items">
            <div className="legend-item">
              <span className="swatch-box swatch-geometric-covered" />
              <span>Visible por ≥1 cámara (100% geométrica)</span>
            </div>
            <div className="legend-item">
              <span className="swatch-box swatch-geometric-uncovered" />
              <span>Ocluido por muros o fuera de campo</span>
            </div>
            {coverageData && (
              <div className="legend-meta-summary">
                <span>
                  Puntos cubiertos: <strong>{coverageData.metrics.num_covered_points}</strong> /{' '}
                  {coverageData.metrics.num_eval_points} (
                  <strong>{coverageData.metrics.geometric_coverage_percent.toFixed(1)}%</strong>)
                </span>
              </div>
            )}
          </div>
        )}

        {/* Mode: Riesgo */}
        {viewMode === 'risk' && (
          <div className="legend-items">
            <div className="legend-item">
              <span className="swatch-box swatch-risk-normal" />
              <span>Riesgo estándar (1.0×)</span>
            </div>
            <div className="legend-item">
              <span className="swatch-box swatch-risk-priority" />
              <span>Zona crítica / alta prioridad (&gt;1.0×)</span>
            </div>
            {coverageData && (
              <div className="legend-meta-summary">
                <span>
                  Puntos críticos: <strong>{coverageData.metrics.num_critical_points}</strong> | Déficit crítico:{' '}
                  <strong>{coverageData.metrics.critical_deficit.toFixed(4)}</strong>
                </span>
              </div>
            )}
          </div>
        )}

        {/* Mode: Plano (Geométrico tradicional) */}
        {viewMode === 'floorplan' && (
          <div className="legend-items">
            <div className="legend-item">
              <span className="swatch-box swatch-room" />
              <span>Recinto</span>
            </div>
            <div className="legend-item">
              <span className="swatch-box swatch-wall" />
              <span>Paredes</span>
            </div>
            <div className="legend-item">
              <span className="swatch-box swatch-obstacle" />
              <span>Obstáculos</span>
            </div>
            <div className="legend-item">
              <span className="swatch-box swatch-risk" />
              <span>Zonas de Riesgo</span>
            </div>
            <div className="legend-item">
              <span
                className={`swatch-circle ${cameraColorMode === 'individual' ? 'swatch-cyan' : 'swatch-gold'}`}
              />
              <span>Cámaras ({cameras.length})</span>
            </div>
            <div className="legend-item">
              <span className="swatch-cone" />
              <span>Apertura Nominal</span>
            </div>
          </div>
        )}

        <div className="nominal-disclaimer">
          <span>
            {viewMode === 'floorplan'
              ? '* Los sectores cónicos representan el campo visual nominal. Seleccione «Probabilidad» para visualizar el mapa continuo calculado por FastAPI.'
              : '* Las probabilidades espaciales y visibilidad corresponden estrictamente a la simulación óptica del backend.'}
          </span>
        </div>
      </div>
    </div>
  )
}
