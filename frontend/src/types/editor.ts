import type { Point, Scenario } from './api'

export type EditorTool = 'select' | 'boundary' | 'wall' | 'door' | 'obstacle' | 'risk_zone'

export type SelectedObjectType = 'wall' | 'obstacle' | 'risk_zone'

export interface SelectedObject {
  type: SelectedObjectType
  index: number
  vertexIndex?: number | null // for vertex dragging/selection
}

export interface DraftGeometry {
  tool: EditorTool
  points: Point[]
  isOpaque?: boolean
  riskWeight?: number
  riskName?: string
  doorWidth?: number
}

export interface EditorState {
  activeTool: EditorTool
  selectedObject: SelectedObject | null
  draft: DraftGeometry | null
  snapToGrid: boolean
  snapSize: number // in physical meters (e.g. 0.25, 0.5, 1.0)
  doorWidth: number // in meters (default 1.0)
  canUndo: boolean
  canRedo: boolean
}

export interface ScenarioHistoryEntry {
  scenario: Scenario
  description: string
}
