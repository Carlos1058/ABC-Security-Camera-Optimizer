/**
 * Reusable Canvas 2D Floorplan Renderer.
 * Decoupled from React lifecycle, renders room bounds, walls, obstacles,
 * risk zones, and camera poses with nominal FOV sectors.
 */

import type {
  CameraPose,
  CameraProfile,
  CanvasViewMode,
  CoverageGridNode,
  Point,
  Scenario,
  Wall,
} from '../types/api'
import type { EditorTool, SelectedObject } from '../types/editor'
import { CoordinateTransform } from './coordinateTransform'

export interface RenderOptions {
  scenario: Scenario
  cameras: CameraPose[]
  profile?: CameraProfile | null
  transform: CoordinateTransform
  selectedCameraIndex?: number | null
  hoveredPoint?: { x: number; y: number } | null
  cameraColorMode?: 'best' | 'individual'
  sourceLabel?: string
  coverageNodes?: CoverageGridNode[] | null
  cellWidth?: number
  cellHeight?: number
  viewMode?: CanvasViewMode
  coverageOpacity?: number
  showCameraCones?: boolean
  // Editor mode overlays
  isEditorMode?: boolean
  activeTool?: EditorTool
  selectedObject?: SelectedObject | null
  draftPoints?: Point[]
  snappedCursor?: Point | null
  hoveredWallForDoor?: { wall: Wall; openingStart: Point; openingEnd: Point } | null
}

export class FloorplanRenderer {
  private ctx: CanvasRenderingContext2D

  constructor(ctx: CanvasRenderingContext2D) {
    this.ctx = ctx
  }

  /**
   * Main render method. Draws the complete floorplan, coverage layer, and camera deployment.
   */
  public render(options: RenderOptions): void {
    const {
      scenario,
      cameras,
      profile,
      transform,
      selectedCameraIndex,
      cameraColorMode,
      coverageNodes,
      cellWidth,
      cellHeight,
      viewMode = 'floorplan',
      coverageOpacity = 0.75,
      showCameraCones = viewMode === 'floorplan',
    } = options
    const ctx = this.ctx
    const { canvasWidth, canvasHeight } = transform

    // 1. Clear Canvas with absolute minimalist black (#000000)
    ctx.clearRect(0, 0, canvasWidth, canvasHeight)
    ctx.fillStyle = '#000000'
    ctx.fillRect(0, 0, canvasWidth, canvasHeight)

    // 2. Draw Floor Grid & Axes
    this.drawGrid(transform)

    // 3. Draw Room Interior Floor
    this.drawRoomFloor(scenario, transform)

    // 4. Draw Authentic Coverage Heatmap Layer (between floor and obstacles/walls)
    if (viewMode !== 'floorplan' && coverageNodes && coverageNodes.length > 0 && cellWidth && cellHeight) {
      this.drawCoverageLayer(coverageNodes, cellWidth, cellHeight, viewMode, coverageOpacity, transform)
    }

    // 5. Draw Risk Zones (Priority regions)
    if (scenario.risk_zones && scenario.risk_zones.length > 0) {
      this.drawRiskZones(scenario.risk_zones, transform)
    }

    // 6. Draw Obstacles (Solid barriers)
    if (scenario.obstacles && scenario.obstacles.length > 0) {
      this.drawObstacles(scenario.obstacles, transform)
    }

    // 7. Draw Interior Walls
    if (scenario.walls && scenario.walls.length > 0) {
      this.drawWalls(scenario.walls, transform)
    }

    // 8. Draw Room Perimeter Boundary
    this.drawRoomBoundary(scenario, transform)

    // 9. Draw Cameras & Nominal FOV Cones
    if (cameras && cameras.length > 0) {
      this.drawCameras(cameras, profile, transform, selectedCameraIndex, cameraColorMode, scenario, showCameraCones)
    }

    // 10. Draw Scale Indicator Bar in bottom-left
    this.drawScaleBar(transform)

    // 11. Draw Interactive Editor Overlays
    if (options.isEditorMode) {
      this.drawEditorOverlay(options)
    }
  }

  /**
   * Draw metric background grid and coordinate ticks.
   */
  private drawGrid(transform: CoordinateTransform): void {
    const ctx = this.ctx
    const { xmin, xmax, ymin, ymax, scale } = transform

    // Determine grid step in meters based on zoom scale
    let step = 1.0 // 1m default
    if (scale < 15) step = 5.0
    if (scale < 6) step = 10.0
    if (scale > 60) step = 0.5

    ctx.save()
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)'
    ctx.lineWidth = 1

    // Vertical grid lines
    const startX = Math.floor(xmin / step) * step
    for (let x = startX; x <= xmax + step; x += step) {
      const p1 = transform.worldToScreen({ x, y: ymin - step })
      const p2 = transform.worldToScreen({ x, y: ymax + step })
      ctx.beginPath()
      ctx.moveTo(p1.x, p1.y)
      ctx.lineTo(p2.x, p2.y)
      ctx.stroke()
    }

    // Horizontal grid lines
    const startY = Math.floor(ymin / step) * step
    for (let y = startY; y <= ymax + step; y += step) {
      const p1 = transform.worldToScreen({ x: xmin - step, y })
      const p2 = transform.worldToScreen({ x: xmax + step, y })
      ctx.beginPath()
      ctx.moveTo(p1.x, p1.y)
      ctx.lineTo(p2.x, p2.y)
      ctx.stroke()
    }

    ctx.restore()
  }

  /**
   * Draw usable indoor floor area with subtle dark blue tint.
   */
  private drawRoomFloor(scenario: Scenario, transform: CoordinateTransform): void {
    const ctx = this.ctx
    const xmin = scenario.xmin ?? 0.0
    const xmax = scenario.xmax
    const ymin = scenario.ymin ?? 0.0
    const ymax = scenario.ymax

    const pTopLeft = transform.worldToScreen({ x: xmin, y: ymax })
    const pBottomRight = transform.worldToScreen({ x: xmax, y: ymin })

    const width = pBottomRight.x - pTopLeft.x
    const height = pBottomRight.y - pTopLeft.y

    ctx.save()
    // Floor area background: pure deep monochrome surface
    ctx.fillStyle = '#0a0a0c'
    ctx.fillRect(pTopLeft.x, pTopLeft.y, width, height)

    // Subtle inner room border
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)'
    ctx.lineWidth = 1
    ctx.strokeRect(pTopLeft.x, pTopLeft.y, width, height)
    ctx.restore()
  }

  /**
   * Draw exterior room perimeter boundary walls.
   */
  private drawRoomBoundary(scenario: Scenario, transform: CoordinateTransform): void {
    const ctx = this.ctx
    const xmin = scenario.xmin ?? 0.0
    const xmax = scenario.xmax
    const ymin = scenario.ymin ?? 0.0
    const ymax = scenario.ymax

    const pTopLeft = transform.worldToScreen({ x: xmin, y: ymax })
    const pBottomRight = transform.worldToScreen({ x: xmax, y: ymin })

    ctx.save()
    ctx.strokeStyle = '#38bdf8'
    ctx.lineWidth = 2.5
    ctx.strokeRect(pTopLeft.x, pTopLeft.y, pBottomRight.x - pTopLeft.x, pBottomRight.y - pTopLeft.y)

    // Corner accent brackets
    const bracketLen = 10
    ctx.strokeStyle = '#f59e0b'
    ctx.lineWidth = 3

    // Top-left
    ctx.beginPath()
    ctx.moveTo(pTopLeft.x, pTopLeft.y + bracketLen)
    ctx.lineTo(pTopLeft.x, pTopLeft.y)
    ctx.lineTo(pTopLeft.x + bracketLen, pTopLeft.y)
    ctx.stroke()

    // Top-right
    ctx.beginPath()
    ctx.moveTo(pBottomRight.x - bracketLen, pTopLeft.y)
    ctx.lineTo(pBottomRight.x, pTopLeft.y)
    ctx.lineTo(pBottomRight.x, pTopLeft.y + bracketLen)
    ctx.stroke()

    // Bottom-right
    ctx.beginPath()
    ctx.moveTo(pBottomRight.x, pBottomRight.y - bracketLen)
    ctx.lineTo(pBottomRight.x, pBottomRight.y)
    ctx.lineTo(pBottomRight.x - bracketLen, pBottomRight.y)
    ctx.stroke()

    // Bottom-left
    ctx.beginPath()
    ctx.moveTo(pTopLeft.x + bracketLen, pBottomRight.y)
    ctx.lineTo(pTopLeft.x, pBottomRight.y)
    ctx.lineTo(pTopLeft.x, pBottomRight.y - bracketLen)
    ctx.stroke()

    ctx.restore()
  }

  /**
   * Draw interior walls (opaque partitions or glass).
   */
  private drawWalls(walls: NonNullable<Scenario['walls']>, transform: CoordinateTransform): void {
    const ctx = this.ctx
    ctx.save()

    for (const wall of walls) {
      const p1 = transform.worldToScreen(wall.start)
      const p2 = transform.worldToScreen(wall.end)

      ctx.beginPath()
      ctx.moveTo(p1.x, p1.y)
      ctx.lineTo(p2.x, p2.y)

      if (wall.is_opaque !== false) {
        ctx.strokeStyle = '#94a3b8'
        ctx.lineWidth = 4
        ctx.setLineDash([])
      } else {
        ctx.strokeStyle = 'rgba(148, 163, 184, 0.6)'
        ctx.lineWidth = 2
        ctx.setLineDash([6, 4])
      }
      ctx.stroke()

      // Endpoint anchors
      ctx.fillStyle = '#64748b'
      ctx.beginPath()
      ctx.arc(p1.x, p1.y, 2.5, 0, 2 * Math.PI)
      ctx.arc(p2.x, p2.y, 2.5, 0, 2 * Math.PI)
      ctx.fill()
    }

    ctx.restore()
  }

  /**
   * Draw solid interior obstacles with dark fill and hatched interior.
   */
  private drawObstacles(obstacles: NonNullable<Scenario['obstacles']>, transform: CoordinateTransform): void {
    const ctx = this.ctx

    for (const obs of obstacles) {
      if (obs.vertices.length < 3) continue

      ctx.save()
      ctx.beginPath()
      const first = transform.worldToScreen(obs.vertices[0])
      ctx.moveTo(first.x, first.y)
      for (let i = 1; i < obs.vertices.length; i++) {
        const pt = transform.worldToScreen(obs.vertices[i])
        ctx.lineTo(pt.x, pt.y)
      }
      ctx.closePath()

      // Solid dark fill
      ctx.fillStyle = '#1e293b'
      ctx.fill()

      // Crisp solid border
      ctx.strokeStyle = '#64748b'
      ctx.lineWidth = 2
      ctx.stroke()

      // Subtle diagonal hatching pattern
      ctx.clip()
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)'
      ctx.lineWidth = 1
      const pMin = transform.worldToScreen(obs.vertices[0])
      const hatchSpan = 200
      for (let d = -hatchSpan; d < hatchSpan * 2; d += 8) {
        ctx.beginPath()
        ctx.moveTo(pMin.x + d, pMin.y - hatchSpan)
        ctx.lineTo(pMin.x + d - hatchSpan, pMin.y + hatchSpan)
        ctx.stroke()
      }

      ctx.restore()
    }
  }

  /**
   * Draw priority risk zones with translucent amber tint and label.
   */
  private drawRiskZones(riskZones: NonNullable<Scenario['risk_zones']>, transform: CoordinateTransform): void {
    const ctx = this.ctx

    for (const rz of riskZones) {
      if (rz.vertices.length < 3) continue

      ctx.save()
      ctx.beginPath()
      const first = transform.worldToScreen(rz.vertices[0])
      ctx.moveTo(first.x, first.y)
      let sumX = 0
      let sumY = 0

      for (const v of rz.vertices) {
        const pt = transform.worldToScreen(v)
        ctx.lineTo(pt.x, pt.y)
        sumX += pt.x
        sumY += pt.y
      }
      ctx.closePath()

      // Alpha intensity scales with weight
      const alpha = Math.min(0.28, 0.08 + (rz.weight - 1.0) * 0.05)
      ctx.fillStyle = `rgba(245, 158, 11, ${alpha})`
      ctx.fill()

      // Dashed border
      ctx.strokeStyle = '#f59e0b'
      ctx.lineWidth = 1.5
      ctx.setLineDash([5, 3])
      ctx.stroke()

      // Centroid label
      const centerX = sumX / rz.vertices.length
      const centerY = sumY / rz.vertices.length

      ctx.setLineDash([])
      ctx.fillStyle = '#fde68a'
      ctx.font = '600 11px system-ui, sans-serif'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'

      const labelText = rz.name ? `${rz.name} (${rz.weight.toFixed(1)}×)` : `Zona de Riesgo (${rz.weight.toFixed(1)}×)`
      ctx.fillText(labelText, centerX, centerY)

      ctx.restore()
    }
  }

  /**
   * Draw deployed cameras and their nominal FOV sector cones.
   */
  private drawCameras(
    cameras: CameraPose[],
    profile: CameraProfile | null | undefined,
    transform: CoordinateTransform,
    selectedCameraIndex?: number | null,
    cameraColorMode: 'best' | 'individual' = 'best',
    scenario?: Scenario,
    showCameraCones: boolean = true
  ): void {
    const ctx = this.ctx

    const Rmin = profile?.Rmin ?? 0.0
    const Rmax = profile?.Rmax ?? 10.0
    const FOV = profile?.FOV ?? Math.PI / 2.0

    const isIndividual = cameraColorMode === 'individual'
    const primaryColor = isIndividual ? '#38bdf8' : '#facc15'
    const primaryGlow = isIndividual ? 'rgba(56, 189, 248, 0.25)' : 'rgba(250, 204, 21, 0.25)'
    const sectorFill = isIndividual ? 'rgba(56, 189, 248, 0.08)' : 'rgba(250, 204, 21, 0.09)'

    // Pass 1: Draw FOV sectors for all cameras (clipped to room bounds if scenario provided)
    if (showCameraCones) {
      ctx.save()
      if (scenario) {
        const xmin = scenario.xmin ?? 0.0
        const xmax = scenario.xmax
        const ymin = scenario.ymin ?? 0.0
        const ymax = scenario.ymax
        const pTopLeft = transform.worldToScreen({ x: xmin, y: ymax })
        const pBottomRight = transform.worldToScreen({ x: xmax, y: ymin })
        ctx.beginPath()
        ctx.rect(pTopLeft.x, pTopLeft.y, pBottomRight.x - pTopLeft.x, pBottomRight.y - pTopLeft.y)
        ctx.clip()
      }

      for (let i = 0; i < cameras.length; i++) {
        const cam = cameras[i]
        const isSelected = selectedCameraIndex === i
        const center = transform.worldToScreen(cam)

        const screenAngle = transform.angleToScreen(cam.theta)
        const startAngle = screenAngle - FOV / 2.0
        const endAngle = screenAngle + FOV / 2.0

        const rMinPx = transform.distanceToPixels(Rmin)
        const rMaxPx = transform.distanceToPixels(Rmax)

        ctx.save()

        // Sector Cone Geometry
        ctx.beginPath()
        if (rMinPx > 1) {
          ctx.arc(center.x, center.y, rMaxPx, startAngle, endAngle, false)
          ctx.arc(center.x, center.y, rMinPx, endAngle, startAngle, true)
        } else {
          ctx.moveTo(center.x, center.y)
          ctx.arc(center.x, center.y, rMaxPx, startAngle, endAngle, false)
        }
        ctx.closePath()

        // Fill sector with gradient or flat alpha
        ctx.fillStyle = isSelected ? primaryGlow : sectorFill
        ctx.fill()

        // Sector boundary lines
        ctx.strokeStyle = isSelected ? primaryColor : 'rgba(250, 204, 21, 0.35)'
        ctx.lineWidth = isSelected ? 2 : 1
        ctx.setLineDash([4, 2])
        ctx.stroke()

        ctx.restore()
      }

      ctx.restore()
    }

    // Pass 2: Draw camera bodies and directional pointers
    for (let i = 0; i < cameras.length; i++) {
      const cam = cameras[i]
      const isSelected = selectedCameraIndex === i
      const center = transform.worldToScreen(cam)
      const screenAngle = transform.angleToScreen(cam.theta)

      ctx.save()
      ctx.translate(center.x, center.y)

      // Outer focus glow for selected camera
      if (isSelected) {
        ctx.beginPath()
        ctx.arc(0, 0, 16, 0, 2 * Math.PI)
        ctx.fillStyle = primaryGlow
        ctx.fill()
      }

      // Camera body housing circle
      ctx.beginPath()
      ctx.arc(0, 0, 9, 0, 2 * Math.PI)
      ctx.fillStyle = isSelected ? '#ffffff' : '#1e293b'
      ctx.fill()
      ctx.strokeStyle = primaryColor
      ctx.lineWidth = 2.5
      ctx.stroke()

      // Directional triangle pointer
      const pointerLen = 14
      const pointerWidth = 5
      const tipX = Math.cos(screenAngle) * pointerLen
      const tipY = Math.sin(screenAngle) * pointerLen
      const baseLeftX = Math.cos(screenAngle + Math.PI / 2) * pointerWidth
      const baseLeftY = Math.sin(screenAngle + Math.PI / 2) * pointerWidth
      const baseRightX = Math.cos(screenAngle - Math.PI / 2) * pointerWidth
      const baseRightY = Math.sin(screenAngle - Math.PI / 2) * pointerWidth

      ctx.beginPath()
      ctx.moveTo(tipX, tipY)
      ctx.lineTo(baseLeftX, baseLeftY)
      ctx.lineTo(baseRightX, baseRightY)
      ctx.closePath()
      ctx.fillStyle = primaryColor
      ctx.fill()

      // Center lens dot
      ctx.beginPath()
      ctx.arc(0, 0, 3, 0, 2 * Math.PI)
      ctx.fillStyle = isSelected ? primaryColor : '#f8fafc'
      ctx.fill()

      // Camera ID label badge (e.g. "C1")
      ctx.restore()
      ctx.save()
      ctx.fillStyle = isSelected ? '#ffffff' : '#cbd5e1'
      ctx.font = '700 10px system-ui, sans-serif'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'top'
      ctx.fillText(`C${i + 1}`, center.x, center.y + 11)
      ctx.restore()
    }
  }

  /**
   * Draw scale indicator bar in bottom-left.
   */
  private drawScaleBar(transform: CoordinateTransform): void {
    const ctx = this.ctx
    const barMeters = transform.scale > 40 ? 1 : transform.scale > 10 ? 5 : 10
    const barPixels = transform.distanceToPixels(barMeters)

    const posX = 20
    const posY = transform.canvasHeight - 20

    ctx.save()
    ctx.strokeStyle = '#94a3b8'
    ctx.lineWidth = 2

    // Horizontal bar
    ctx.beginPath()
    ctx.moveTo(posX, posY)
    ctx.lineTo(posX + barPixels, posY)
    // Left end
    ctx.moveTo(posX, posY - 4)
    ctx.lineTo(posX, posY + 4)
    // Right end
    ctx.moveTo(posX + barPixels, posY - 4)
    ctx.lineTo(posX + barPixels, posY + 4)
    ctx.stroke()

    // Text label
    ctx.fillStyle = '#94a3b8'
    ctx.font = '500 10px system-ui, sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'bottom'
    ctx.fillText(`${barMeters} m`, posX + barPixels / 2, posY - 4)

    ctx.restore()
  }

  /**
   * Draw discrete coverage cells according to active view mode without interpolation across walls.
   */
  private drawCoverageLayer(
    nodes: CoverageGridNode[],
    cellWidth: number,
    cellHeight: number,
    viewMode: CanvasViewMode,
    opacity: number,
    transform: CoordinateTransform
  ): void {
    const ctx = this.ctx
    ctx.save()

    const halfW = cellWidth / 2
    const halfH = cellHeight / 2

    for (let i = 0; i < nodes.length; i++) {
      const node = nodes[i]
      const color = this.getCellColor(node, viewMode, opacity)
      if (!color) continue

      const pTopLeft = transform.worldToScreen({ x: node.x - halfW, y: node.y + halfH })
      const pBottomRight = transform.worldToScreen({ x: node.x + halfW, y: node.y - halfH })

      const w = Math.ceil(pBottomRight.x - pTopLeft.x) + 0.5
      const h = Math.ceil(pBottomRight.y - pTopLeft.y) + 0.5

      ctx.fillStyle = color
      ctx.fillRect(pTopLeft.x, pTopLeft.y, w, h)
    }

    ctx.restore()
  }

  /**
   * Determine exact cell color and opacity based on active visualization mode.
   */
  private getCellColor(node: CoverageGridNode, mode: CanvasViewMode, opacity: number): string | null {
    if (mode === 'probability') {
      const p = node.probability
      if (p <= 0.0001) return null
      const clamped = Math.max(0, Math.min(1, p))

      // 4-stop scientific smooth palette:
      // 0.00: Deep Blue [30, 64, 175]
      // 0.25: Cyan [6, 182, 212]
      // 0.50: Emerald [16, 185, 129]
      // 0.75: Amber [245, 158, 11]
      // 1.00: Crimson Red [239, 68, 68]
      let r: number, g: number, b: number
      if (clamped < 0.25) {
        const t = clamped / 0.25
        r = Math.round(30 + t * (6 - 30))
        g = Math.round(64 + t * (182 - 64))
        b = Math.round(175 + t * (212 - 175))
      } else if (clamped < 0.5) {
        const t = (clamped - 0.25) / 0.25
        r = Math.round(6 + t * (16 - 6))
        g = Math.round(182 + t * (185 - 182))
        b = Math.round(212 + t * (129 - 212))
      } else if (clamped < 0.75) {
        const t = (clamped - 0.5) / 0.25
        r = Math.round(16 + t * (245 - 16))
        g = Math.round(185 + t * (158 - 185))
        b = Math.round(129 + t * (11 - 129))
      } else {
        const t = (clamped - 0.75) / 0.25
        r = Math.round(245 + t * (239 - 245))
        g = Math.round(158 + t * (68 - 158))
        b = Math.round(11 + t * (68 - 11))
      }

      const alpha = (opacity * (0.35 + 0.65 * clamped)).toFixed(3)
      return `rgba(${r}, ${g}, ${b}, ${alpha})`
    }

    if (mode === 'geometric') {
      if (node.binary_covered) {
        return `rgba(16, 185, 129, ${opacity.toFixed(3)})`
      }
      return `rgba(30, 41, 59, ${(opacity * 0.35).toFixed(3)})`
    }

    if (mode === 'risk') {
      if (node.risk_weight > 1.0) {
        const scale = Math.min(1.0, (node.risk_weight - 1.0) / 3.0)
        const r = Math.round(245 + scale * (239 - 245))
        const g = Math.round(158 + scale * (68 - 158))
        const b = Math.round(11 + scale * (68 - 11))
        return `rgba(${r}, ${g}, ${b}, ${opacity.toFixed(3)})`
      }
      return `rgba(56, 189, 248, ${(opacity * 0.25).toFixed(3)})`
    }

    return null
  }

  /**
   * Draw visual editor overlays: selection bounding/handles, active drawing draft,
   * door opening preview, and metric snapping cursor.
   */
  private drawEditorOverlay(options: RenderOptions): void {
    const ctx = this.ctx
    const {
      scenario,
      transform,
      selectedObject,
      draftPoints,
      snappedCursor,
      activeTool,
      hoveredWallForDoor,
    } = options

    ctx.save()

    // 1. Highlight Selected Object
    if (selectedObject) {
      if (selectedObject.type === 'wall' && scenario.walls && scenario.walls[selectedObject.index]) {
        const wall = scenario.walls[selectedObject.index]
        const p1 = transform.worldToScreen(wall.start)
        const p2 = transform.worldToScreen(wall.end)

        // Outer cyan glow
        ctx.beginPath()
        ctx.moveTo(p1.x, p1.y)
        ctx.lineTo(p2.x, p2.y)
        ctx.strokeStyle = 'rgba(6, 182, 212, 0.4)'
        ctx.lineWidth = 10
        ctx.lineCap = 'round'
        ctx.stroke()

        // Inner solid line
        ctx.beginPath()
        ctx.moveTo(p1.x, p1.y)
        ctx.lineTo(p2.x, p2.y)
        ctx.strokeStyle = '#06b6d4'
        ctx.lineWidth = 4
        ctx.stroke()

        // Endpoints handles
        const drawHandle = (p: { x: number; y: number }, isActive: boolean, label: string) => {
          ctx.beginPath()
          ctx.arc(p.x, p.y, isActive ? 8 : 6, 0, 2 * Math.PI)
          ctx.fillStyle = isActive ? '#38bdf8' : '#ffffff'
          ctx.fill()
          ctx.strokeStyle = '#0891b2'
          ctx.lineWidth = 2
          ctx.stroke()

          ctx.fillStyle = '#0891b2'
          ctx.font = 'bold 9px system-ui, sans-serif'
          ctx.textAlign = 'center'
          ctx.textBaseline = 'bottom'
          ctx.fillText(label, p.x, p.y - 8)
        }

        drawHandle(p1, selectedObject.vertexIndex === 0, 'P1')
        drawHandle(p2, selectedObject.vertexIndex === 1, 'P2')

        // Real length tag at midpoint
        const midX = (p1.x + p2.x) / 2
        const midY = (p1.y + p2.y) / 2
        const lenMeters = Math.hypot(wall.end.x - wall.start.x, wall.end.y - wall.start.y)

        ctx.fillStyle = 'rgba(15, 23, 42, 0.9)'
        ctx.strokeStyle = '#06b6d4'
        ctx.lineWidth = 1
        const txt = `${lenMeters.toFixed(2)} m`
        ctx.font = '600 11px system-ui, sans-serif'
        const tw = ctx.measureText(txt).width + 12
        ctx.fillRect(midX - tw / 2, midY - 20, tw, 18)
        ctx.strokeRect(midX - tw / 2, midY - 20, tw, 18)

        ctx.fillStyle = '#38bdf8'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(txt, midX, midY - 11)
      } else if (
        selectedObject.type === 'obstacle' &&
        scenario.obstacles &&
        scenario.obstacles[selectedObject.index]
      ) {
        const obs = scenario.obstacles[selectedObject.index]
        if (obs.vertices.length >= 3) {
          ctx.beginPath()
          const first = transform.worldToScreen(obs.vertices[0])
          ctx.moveTo(first.x, first.y)
          for (let i = 1; i < obs.vertices.length; i++) {
            const pt = transform.worldToScreen(obs.vertices[i])
            ctx.lineTo(pt.x, pt.y)
          }
          ctx.closePath()

          ctx.strokeStyle = '#06b6d4'
          ctx.lineWidth = 2.5
          ctx.setLineDash([6, 4])
          ctx.stroke()
          ctx.setLineDash([])

          // Vertex handles
          obs.vertices.forEach((v, idx) => {
            const pt = transform.worldToScreen(v)
            const isActive = selectedObject.vertexIndex === idx
            ctx.beginPath()
            ctx.arc(pt.x, pt.y, isActive ? 7 : 5, 0, 2 * Math.PI)
            ctx.fillStyle = isActive ? '#38bdf8' : '#ffffff'
            ctx.fill()
            ctx.strokeStyle = '#0891b2'
            ctx.lineWidth = 2
            ctx.stroke()

            ctx.fillStyle = '#38bdf8'
            ctx.font = 'bold 9px system-ui, sans-serif'
            ctx.textAlign = 'center'
            ctx.textBaseline = 'bottom'
            ctx.fillText(`V${idx + 1}`, pt.x, pt.y - 7)
          })
        }
      } else if (
        selectedObject.type === 'risk_zone' &&
        scenario.risk_zones &&
        scenario.risk_zones[selectedObject.index]
      ) {
        const rz = scenario.risk_zones[selectedObject.index]
        if (rz.vertices.length >= 3) {
          ctx.beginPath()
          const first = transform.worldToScreen(rz.vertices[0])
          ctx.moveTo(first.x, first.y)
          for (let i = 1; i < rz.vertices.length; i++) {
            const pt = transform.worldToScreen(rz.vertices[i])
            ctx.lineTo(pt.x, pt.y)
          }
          ctx.closePath()

          ctx.strokeStyle = '#fbbf24'
          ctx.lineWidth = 2.5
          ctx.setLineDash([5, 3])
          ctx.stroke()
          ctx.setLineDash([])

          rz.vertices.forEach((v, idx) => {
            const pt = transform.worldToScreen(v)
            const isActive = selectedObject.vertexIndex === idx
            ctx.beginPath()
            ctx.arc(pt.x, pt.y, isActive ? 7 : 5, 0, 2 * Math.PI)
            ctx.fillStyle = isActive ? '#fbbf24' : '#fef3c7'
            ctx.fill()
            ctx.strokeStyle = '#d97706'
            ctx.lineWidth = 2
            ctx.stroke()

            ctx.fillStyle = '#fbbf24'
            ctx.font = 'bold 9px system-ui, sans-serif'
            ctx.textAlign = 'center'
            ctx.textBaseline = 'bottom'
            ctx.fillText(`V${idx + 1}`, pt.x, pt.y - 7)
          })
        }
      }
    }

    // 2. Door Tool Hover Preview on an Existing Wall
    if (activeTool === 'door' && hoveredWallForDoor) {
      const p1 = transform.worldToScreen(hoveredWallForDoor.openingStart)
      const p2 = transform.worldToScreen(hoveredWallForDoor.openingEnd)

      // Highlight the opening interval with glowing amber dashed line
      ctx.beginPath()
      ctx.moveTo(p1.x, p1.y)
      ctx.lineTo(p2.x, p2.y)
      ctx.strokeStyle = '#f59e0b'
      ctx.lineWidth = 6
      ctx.setLineDash([5, 3])
      ctx.stroke()
      ctx.setLineDash([])

      // Draw Door Opening Tag
      const midX = (p1.x + p2.x) / 2
      const midY = (p1.y + p2.y) / 2
      ctx.fillStyle = 'rgba(15, 23, 42, 0.9)'
      ctx.strokeStyle = '#f59e0b'
      ctx.lineWidth = 1
      const txt = 'Abertura (Clic para aplicar)'
      ctx.font = '600 10px system-ui, sans-serif'
      const tw = ctx.measureText(txt).width + 10
      ctx.fillRect(midX - tw / 2, midY - 22, tw, 18)
      ctx.strokeRect(midX - tw / 2, midY - 22, tw, 18)

      ctx.fillStyle = '#fbbf24'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(txt, midX, midY - 13)
    }

    // 3. Draft Drawing Preview
    if (draftPoints && draftPoints.length > 0) {
      const pts = draftPoints.map(p => transform.worldToScreen(p))
      const cursorScreen = snappedCursor ? transform.worldToScreen(snappedCursor) : null

      if (activeTool === 'wall' && pts.length === 1 && cursorScreen && snappedCursor) {
        // Rubberband wall line
        ctx.beginPath()
        ctx.moveTo(pts[0].x, pts[0].y)
        ctx.lineTo(cursorScreen.x, cursorScreen.y)
        ctx.strokeStyle = '#38bdf8'
        ctx.lineWidth = 3
        ctx.setLineDash([6, 3])
        ctx.stroke()
        ctx.setLineDash([])

        // Start point anchor
        ctx.beginPath()
        ctx.arc(pts[0].x, pts[0].y, 6, 0, 2 * Math.PI)
        ctx.fillStyle = '#38bdf8'
        ctx.fill()
        ctx.strokeStyle = '#ffffff'
        ctx.lineWidth = 2
        ctx.stroke()

        // Real-time length tag
        const len = Math.hypot(snappedCursor.x - draftPoints[0].x, snappedCursor.y - draftPoints[0].y)
        const midX = (pts[0].x + cursorScreen.x) / 2
        const midY = (pts[0].y + cursorScreen.y) / 2
        ctx.fillStyle = 'rgba(15, 23, 42, 0.9)'
        ctx.strokeStyle = '#38bdf8'
        ctx.lineWidth = 1
        const txt = `${len.toFixed(2)} m`
        ctx.font = '600 11px system-ui, sans-serif'
        const tw = ctx.measureText(txt).width + 12
        ctx.fillRect(midX - tw / 2, midY - 22, tw, 18)
        ctx.strokeRect(midX - tw / 2, midY - 22, tw, 18)

        ctx.fillStyle = '#38bdf8'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(txt, midX, midY - 13)
      } else if ((activeTool === 'obstacle' || activeTool === 'risk_zone') && pts.length >= 1) {
        const isRisk = activeTool === 'risk_zone'
        const themeColor = isRisk ? '#f59e0b' : '#38bdf8'
        const fillAlpha = isRisk ? 'rgba(245, 158, 11, 0.15)' : 'rgba(56, 189, 248, 0.15)'

        // Draw existing segments
        ctx.beginPath()
        ctx.moveTo(pts[0].x, pts[0].y)
        for (let i = 1; i < pts.length; i++) {
          ctx.lineTo(pts[i].x, pts[i].y)
        }
        if (cursorScreen) {
          ctx.lineTo(cursorScreen.x, cursorScreen.y)
          // Preview close segment back to start
          if (pts.length >= 2) {
            ctx.lineTo(pts[0].x, pts[0].y)
          }
        }
        ctx.fillStyle = fillAlpha
        ctx.fill()

        // Stroke established segments
        ctx.beginPath()
        ctx.moveTo(pts[0].x, pts[0].y)
        for (let i = 1; i < pts.length; i++) {
          ctx.lineTo(pts[i].x, pts[i].y)
        }
        ctx.strokeStyle = themeColor
        ctx.lineWidth = 2.5
        ctx.stroke()

        // Rubberband line to cursor
        if (cursorScreen) {
          ctx.beginPath()
          ctx.moveTo(pts[pts.length - 1].x, pts[pts.length - 1].y)
          ctx.lineTo(cursorScreen.x, cursorScreen.y)
          ctx.strokeStyle = themeColor
          ctx.lineWidth = 2
          ctx.setLineDash([5, 3])
          ctx.stroke()

          // Dotted closing segment
          if (pts.length >= 2) {
            ctx.beginPath()
            ctx.moveTo(cursorScreen.x, cursorScreen.y)
            ctx.lineTo(pts[0].x, pts[0].y)
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)'
            ctx.lineWidth = 1.5
            ctx.setLineDash([3, 3])
            ctx.stroke()
          }
          ctx.setLineDash([])
        }

        // Draw vertices
        pts.forEach((pt, idx) => {
          ctx.beginPath()
          ctx.arc(pt.x, pt.y, idx === 0 ? 6 : 4, 0, 2 * Math.PI)
          ctx.fillStyle = idx === 0 ? '#10b981' : themeColor
          ctx.fill()
          ctx.strokeStyle = '#ffffff'
          ctx.lineWidth = 1.5
          ctx.stroke()
        })

        // If hovering near start point (closing range < 15px)
        if (cursorScreen && pts.length >= 3) {
          const distToStart = Math.hypot(cursorScreen.x - pts[0].x, cursorScreen.y - pts[0].y)
          if (distToStart < 16) {
            ctx.beginPath()
            ctx.arc(pts[0].x, pts[0].y, 12, 0, 2 * Math.PI)
            ctx.strokeStyle = '#10b981'
            ctx.lineWidth = 2
            ctx.stroke()

            ctx.fillStyle = '#10b981'
            ctx.font = '600 10px system-ui, sans-serif'
            ctx.textAlign = 'center'
            ctx.textBaseline = 'bottom'
            ctx.fillText('Clic para cerrar', pts[0].x, pts[0].y - 12)
          }
        }
      }
    }

    // 4. Snapped Cursor Reticle
    if (snappedCursor) {
      const pt = transform.worldToScreen(snappedCursor)
      ctx.beginPath()
      ctx.arc(pt.x, pt.y, 3, 0, 2 * Math.PI)
      ctx.fillStyle = '#06b6d4'
      ctx.fill()

      ctx.strokeStyle = 'rgba(6, 182, 212, 0.6)'
      ctx.lineWidth = 1
      const arm = 6
      ctx.beginPath()
      ctx.moveTo(pt.x - arm, pt.y)
      ctx.lineTo(pt.x + arm, pt.y)
      ctx.moveTo(pt.x, pt.y - arm)
      ctx.lineTo(pt.x, pt.y + arm)
      ctx.stroke()
    }

    ctx.restore()
  }
}


