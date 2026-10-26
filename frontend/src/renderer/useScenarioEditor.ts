/**
 * Custom Hook for Scenario Editor State and History Management.
 *
 * Enforces:
 * - Independent undo/redo stack (up to 50 snapshots).
 * - Automatic invalidation of ABC optimization and coverage cache upon any change.
 * - Centralized selection, tool switching, and snap configuration.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import type { Scenario } from '../types/api'
import type { EditorTool, SelectedObject } from '../types/editor'

const MAX_HISTORY = 50

export interface UseScenarioEditorOptions {
  scenario: Scenario
  onUpdateScenario: (newScenario: Scenario) => void
  onInvalidate: () => void
}

export function useScenarioEditor({
  scenario,
  onUpdateScenario,
  onInvalidate,
}: UseScenarioEditorOptions) {
  const [activeTool, setActiveTool] = useState<EditorTool>('select')
  const [selectedObject, setSelectedObject] = useState<SelectedObject | null>(null)
  const [snapToGrid, setSnapToGrid] = useState<boolean>(true)
  const [snapSize, setSnapSize] = useState<number>(0.5)
  const [doorWidth, setDoorWidth] = useState<number>(1.0)
  const [draftPoints, setDraftPoints] = useState<Array<{ x: number; y: number }>>([])

  // Undo / Redo stacks of Scenario snapshots
  const [undoStack, setUndoStack] = useState<Scenario[]>([])
  const [redoStack, setRedoStack] = useState<Scenario[]>([])

  // Keep a ref to the latest scenario for reliable history pushes
  const currentScenarioRef = useRef(scenario)
  useEffect(() => {
    currentScenarioRef.current = scenario
  }, [scenario])

  // Drag transaction state
  const dragInitialScenarioRef = useRef<Scenario | null>(null)
  const isDraggingTransactionRef = useRef<boolean>(false)

  const startDragTransaction = useCallback(() => {
    dragInitialScenarioRef.current = JSON.parse(JSON.stringify(currentScenarioRef.current))
    isDraggingTransactionRef.current = true
  }, [])

  const updateTransient = useCallback(
    (transientScenario: Scenario) => {
      onUpdateScenario(transientScenario)
    },
    [onUpdateScenario]
  )

  const commitDragTransaction = useCallback(
    (finalScenario: Scenario) => {
      const initial = dragInitialScenarioRef.current
      isDraggingTransactionRef.current = false
      dragInitialScenarioRef.current = null

      if (!initial) {
        // Fallback to regular commit if transaction was not started
        setUndoStack(prev => [...prev.slice(-MAX_HISTORY + 1), currentScenarioRef.current])
        setRedoStack([])
        onUpdateScenario(finalScenario)
        onInvalidate()
        return
      }

      // Check if actual changes occurred
      const hasChanged = JSON.stringify(initial) !== JSON.stringify(finalScenario)
      if (hasChanged) {
        setUndoStack(prev => [...prev.slice(-MAX_HISTORY + 1), initial])
        setRedoStack([])
        onUpdateScenario(finalScenario)
        onInvalidate()
      } else {
        onUpdateScenario(initial)
      }
    },
    [onUpdateScenario, onInvalidate]
  )

  const cancelDragTransaction = useCallback(() => {
    const initial = dragInitialScenarioRef.current
    isDraggingTransactionRef.current = false
    dragInitialScenarioRef.current = null

    if (initial) {
      onUpdateScenario(initial)
    }
  }, [onUpdateScenario])

  const commitScenario = useCallback(
    (nextScenario: Scenario) => {
      // Push snapshot to undo stack
      setUndoStack(prev => [...prev.slice(-MAX_HISTORY + 1), currentScenarioRef.current])
      setRedoStack([])
      onUpdateScenario(nextScenario)
      onInvalidate()
    },
    [onUpdateScenario, onInvalidate]
  )

  const undo = useCallback(() => {
    if (undoStack.length === 0) return
    const prevScenario = undoStack[undoStack.length - 1]
    const nextUndoStack = undoStack.slice(0, -1)

    setRedoStack(prev => [...prev.slice(-MAX_HISTORY + 1), currentScenarioRef.current])
    setUndoStack(nextUndoStack)
    setSelectedObject(null)
    setDraftPoints([])
    onUpdateScenario(prevScenario)
    onInvalidate()
  }, [undoStack, onUpdateScenario, onInvalidate])

  const redo = useCallback(() => {
    if (redoStack.length === 0) return
    const nextScenario = redoStack[redoStack.length - 1]
    const nextRedoStack = redoStack.slice(0, -1)

    setUndoStack(prev => [...prev.slice(-MAX_HISTORY + 1), currentScenarioRef.current])
    setRedoStack(nextRedoStack)
    setSelectedObject(null)
    setDraftPoints([])
    onUpdateScenario(nextScenario)
    onInvalidate()
  }, [redoStack, onUpdateScenario, onInvalidate])

  const deleteSelected = useCallback(() => {
    if (!selectedObject) return
    const sc = currentScenarioRef.current

    if (selectedObject.type === 'wall' && sc.walls) {
      const nextWalls = sc.walls.filter((_, i) => i !== selectedObject.index)
      commitScenario({ ...sc, walls: nextWalls })
      setSelectedObject(null)
    } else if (selectedObject.type === 'obstacle' && sc.obstacles) {
      const nextObs = sc.obstacles.filter((_, i) => i !== selectedObject.index)
      commitScenario({ ...sc, obstacles: nextObs })
      setSelectedObject(null)
    } else if (selectedObject.type === 'risk_zone' && sc.risk_zones) {
      const nextRz = sc.risk_zones.filter((_, i) => i !== selectedObject.index)
      commitScenario({ ...sc, risk_zones: nextRz })
      setSelectedObject(null)
    }
  }, [selectedObject, commitScenario])

  const cancelDraft = useCallback(() => {
    setDraftPoints([])
  }, [])

  return {
    activeTool,
    setActiveTool,
    selectedObject,
    setSelectedObject,
    snapToGrid,
    setSnapToGrid,
    toggleSnap: () => setSnapToGrid(prev => !prev),
    snapSize,
    setSnapSize,
    doorWidth,
    setDoorWidth,
    draftPoints,
    setDraftPoints,
    cancelDraft,
    canUndo: undoStack.length > 0,
    canRedo: redoStack.length > 0,
    undoStack,
    redoStack,
    undo,
    redo,
    commitScenario,
    startDragTransaction,
    updateTransient,
    commitDragTransaction,
    cancelDragTransaction,
    deleteSelected,
  }
}
