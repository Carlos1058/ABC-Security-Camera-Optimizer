import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

// Mock HTMLCanvasElement.getContext('2d')
if (typeof HTMLCanvasElement !== 'undefined') {
  HTMLCanvasElement.prototype.getContext = vi.fn().mockImplementation((contextId: string) => {
    if (contextId === '2d') {
      return {
        fillRect: vi.fn(),
        strokeRect: vi.fn(),
        clearRect: vi.fn(),
        getImageData: vi.fn(),
        putImageData: vi.fn(),
        createImageData: vi.fn(),
        setTransform: vi.fn(),
        drawImage: vi.fn(),
        save: vi.fn(),
        fillText: vi.fn(),
        strokeText: vi.fn(),
        restore: vi.fn(),
        beginPath: vi.fn(),
        moveTo: vi.fn(),
        lineTo: vi.fn(),
        closePath: vi.fn(),
        stroke: vi.fn(),
        fill: vi.fn(),
        arc: vi.fn(),
        scale: vi.fn(),
        rotate: vi.fn(),
        translate: vi.fn(),
        setLineDash: vi.fn(),
        clip: vi.fn(),
        createLinearGradient: vi.fn().mockReturnValue({ addColorStop: vi.fn() }),
        createRadialGradient: vi.fn().mockReturnValue({ addColorStop: vi.fn() }),
        measureText: vi.fn().mockReturnValue({ width: 50 }),
      }
    }
    return null
  })

  HTMLElement.prototype.getBoundingClientRect = vi.fn().mockReturnValue({
    width: 600,
    height: 400,
    top: 0,
    left: 0,
    right: 600,
    bottom: 400,
    x: 0,
    y: 0,
    toJSON: () => {},
  })
}

// Mock ResizeObserver
export class MockResizeObserver {
  static instances: MockResizeObserver[] = []
  callback: ResizeObserverCallback

  constructor(cb: ResizeObserverCallback) {
    this.callback = cb
    MockResizeObserver.instances.push(this)
  }

  observe: () => void = vi.fn()
  unobserve: () => void = vi.fn()
  disconnect: () => void = vi.fn()

  trigger() {
    this.callback([], this as unknown as ResizeObserver)
  }
}

globalThis.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver

// Mock navigator.clipboard
if (!navigator.clipboard) {
  Object.defineProperty(navigator, 'clipboard', {
    value: {
      writeText: vi.fn().mockResolvedValue(undefined),
    },
    configurable: true,
  })
}
