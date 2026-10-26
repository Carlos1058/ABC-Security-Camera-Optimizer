import { JSDOM } from 'jsdom'

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://localhost:5173',
  pretendToBeVisual: true,
})

;(globalThis as any).window = dom.window
;(globalThis as any).document = dom.window.document
Object.defineProperty(globalThis, 'navigator', {
  value: dom.window.navigator,
  configurable: true,
  writable: true,
})
;(globalThis as any).HTMLElement = dom.window.HTMLElement
;(globalThis as any).HTMLCanvasElement = dom.window.HTMLCanvasElement
;(globalThis as any).MouseEvent = dom.window.MouseEvent
;(globalThis as any).KeyboardEvent = dom.window.KeyboardEvent
;(globalThis as any).Event = dom.window.Event
;(globalThis as any).CustomEvent = dom.window.CustomEvent
;(globalThis as any).Node = dom.window.Node
;(globalThis as any).requestAnimationFrame = (cb: any) => setTimeout(cb, 16)
;(globalThis as any).cancelAnimationFrame = (id: any) => clearTimeout(id)

;(globalThis as any).ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
}

const mockContext2D: any = {
  canvas: dom.window.document.createElement('canvas'),
  clearRect: () => {},
  fillRect: () => {},
  strokeRect: () => {},
  beginPath: () => {},
  closePath: () => {},
  moveTo: () => {},
  lineTo: () => {},
  arc: () => {},
  ellipse: () => {},
  fill: () => {},
  stroke: () => {},
  clip: () => {},
  rect: () => {},
  save: () => {},
  restore: () => {},
  translate: () => {},
  rotate: () => {},
  scale: () => {},
  setLineDash: () => {},
  getLineDash: () => [],
  measureText: (text: string) => ({ width: text.length * 6, height: 10 }),
  fillText: () => {},
  strokeText: () => {},
  createImageData: () => ({ data: new Uint8ClampedArray(4) }),
  getImageData: () => ({ data: new Uint8ClampedArray(4) }),
  putImageData: () => {},
  fillStyle: '#000000',
  strokeStyle: '#ffffff',
  lineWidth: 1,
}

dom.window.HTMLCanvasElement.prototype.getContext = function (contextId: string) {
  if (contextId === '2d') return mockContext2D
  return null
} as any

export { dom }
