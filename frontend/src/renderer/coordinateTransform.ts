/**
 * Coordinate transformation between physical meters and Canvas 2D pixel coordinates.
 *
 * Guarantees:
 * - Exact aspect ratio preservation (no spatial distortion).
 * - Support for arbitary floorplan origins (including xmin != 0, ymin != 0).
 * - Cartesian orientation: +X points East (right), +Y points North (up).
 * - Zoom & pan offset transformations with bidirectional mapping.
 */

import type { Point, Scenario } from '../types/api'

export interface TransformState {
  scale: number; // pixels per meter
  offsetX: number; // canvas pixel offset X
  offsetY: number; // canvas pixel offset Y
  canvasWidth: number;
  canvasHeight: number;
  xmin: number;
  xmax: number;
  ymin: number;
  ymax: number;
  zoom: number; // user zoom factor (1.0 = fit)
  panX: number; // user pan offset in pixels
  panY: number; // user pan offset in pixels
}

export class CoordinateTransform {
  public scale: number
  public offsetX: number
  public offsetY: number
  public canvasWidth: number
  public canvasHeight: number
  public xmin: number
  public xmax: number
  public ymin: number
  public ymax: number
  public zoom: number
  public panX: number
  public panY: number

  constructor(
    canvasWidth: number,
    canvasHeight: number,
    scenario?: Scenario | null,
    zoom = 1.0,
    panX = 0,
    panY = 0,
    padding = 40
  ) {
    this.canvasWidth = Math.max(10, canvasWidth)
    this.canvasHeight = Math.max(10, canvasHeight)
    this.zoom = zoom
    this.panX = panX
    this.panY = panY

    this.xmin = scenario?.xmin ?? 0.0
    this.xmax = scenario?.xmax ?? 20.0
    this.ymin = scenario?.ymin ?? 0.0
    this.ymax = scenario?.ymax ?? 20.0

    const roomW = Math.max(0.1, this.xmax - this.xmin)
    const roomH = Math.max(0.1, this.ymax - this.ymin)

    const availW = Math.max(10, this.canvasWidth - 2 * padding)
    const availH = Math.max(10, this.canvasHeight - 2 * padding)

    // Base uniform scale (pixels per meter) to fit room in canvas
    const baseScale = Math.min(availW / roomW, availH / roomH)
    this.scale = baseScale * this.zoom

    // Center the floorplan within the available canvas area
    const totalRenderW = roomW * this.scale
    const totalRenderH = roomH * this.scale

    this.offsetX = (this.canvasWidth - totalRenderW) / 2 + this.panX
    this.offsetY = (this.canvasHeight - totalRenderH) / 2 + this.panY
  }

  /**
   * Convert physical world coordinate (meters) to canvas screen coordinate (pixels).
   * Note: In Cartesian, +Y is UP. In Canvas pixels, Y=0 is TOP.
   * Therefore, world ymax maps to top edge, and world ymin maps to bottom edge.
   */
  public worldToScreen(p: Point): { x: number; y: number } {
    const x = this.offsetX + (p.x - this.xmin) * this.scale
    const y = this.offsetY + (this.ymax - p.y) * this.scale
    return { x, y }
  }

  /**
   * Convert canvas screen coordinate (pixels) to physical world coordinate (meters).
   */
  public screenToWorld(pt: { x: number; y: number }): Point {
    const x = this.xmin + (pt.x - this.offsetX) / this.scale
    const y = this.ymax - (pt.y - this.offsetY) / this.scale
    return { x, y }
  }

  /**
   * Convert physical scalar distance (meters) to canvas pixels.
   */
  public distanceToPixels(meters: number): number {
    return meters * this.scale
  }

  /**
   * Convert canvas scalar pixels to physical distance in meters.
   */
  public pixelsToDistance(pixels: number): number {
    return pixels / this.scale
  }

  /**
   * Convert Cartesian angle theta (where 0 is +X, pi/2 is +Y up)
   * to Canvas 2D screen angle in radians (where 0 is +X right, pi/2 is DOWN).
   */
  public angleToScreen(theta: number): number {
    return -theta
  }
}
