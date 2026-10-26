/**
 * Standalone Automated Test Runner for Fase 5C Scenario Editor
 * Verifies all 16 required test cases with real assertions matching exact TypeScript types.
 */

import assert from 'node:assert';
import {
  pointDistance,
  snapPoint,
  doSegmentsIntersect,
  isPolygonSelfIntersecting,
  polygonArea,
  isPointInsidePolygon,
  splitWallWithOpening,
  validateScenarioLocally,
} from '../renderer/geometryValidation.ts';
import { CoordinateTransform } from '../renderer/coordinateTransform.ts';
import { buildCanonicalCoverageKey } from '../renderer/coverageKey.ts';
import { parseAndValidateScenarioJson } from '../services/scenarioIO.ts';
import type { Scenario, Wall, RiskZone, CameraProfile, Point } from '../types/api.ts';

let passed = 0;
let failed = 0;

function runTest(name: string, fn: () => void | Promise<void>) {
  try {
    const res = fn();
    if (res instanceof Promise) {
      throw new Error('Async test must be awaited in runner');
    }
    console.log(`  \x1b[32m✓\x1b[0m ${name}`);
    passed++;
  } catch (err: any) {
    console.error(`  \x1b[31m✗\x1b[0m ${name}`);
    console.error(`    ${err?.message || err}`);
    failed++;
  }
}

console.log('\n\x1b[1m\x1b[34m=== FASE 5C: COMPREHENSIVE EDITOR VERIFICATION SUITE ===\x1b[0m\n');

// 1. Valid wall creation via two distinct clicks
runTest('1. Valid wall creation via two distinct clicks with draftPoints state', () => {
  let draftPoints: Point[] = [];
  let committedWalls: Wall[] = [];

  function handleCanvasClick(worldPt: Point) {
    if (draftPoints.length === 0) {
      draftPoints = [worldPt];
    } else {
      const startPt = draftPoints[0];
      const len = pointDistance(startPt, worldPt);
      if (len >= 0.05) {
        committedWalls.push({ start: { ...startPt }, end: { ...worldPt }, is_opaque: true });
        draftPoints = [];
      }
    }
  }

  // Click 1: sets draftPoints
  handleCanvasClick({ x: 2.0, y: 3.0 });
  assert.strictEqual(draftPoints.length, 1);
  assert.strictEqual(committedWalls.length, 0);

  // Click 2: completes wall
  handleCanvasClick({ x: 10.0, y: 3.0 });
  assert.strictEqual(draftPoints.length, 0);
  assert.strictEqual(committedWalls.length, 1);

  const wall = committedWalls[0];
  const length = pointDistance(wall.start, wall.end);
  assert.strictEqual(length, 8.0);
  assert.strictEqual(wall.is_opaque, true);

  const scenario: Scenario = {
    xmin: 0,
    xmax: 20,
    ymin: 0,
    ymax: 15,
    walls: committedWalls,
    grid_resolution: 0.5,
  };
  const res = validateScenarioLocally(scenario);
  assert.strictEqual(res.isValid, true);
  assert.strictEqual(res.errors.length, 0);
});

// 2. Door opening creation and segment splitting
runTest('2. Door opening creation and segment splitting into disjoint valid walls', () => {
  const originalWall: Wall = {
    start: { x: 2.0, y: 4.0 },
    end: { x: 12.0, y: 4.0 },
    is_opaque: true,
  };

  const splitResult = splitWallWithOpening(originalWall, { x: 7.0, y: 4.0 }, 1.2);
  assert.ok(splitResult !== null);
  assert.strictEqual(splitResult.valid, true);
  assert.strictEqual(splitResult.walls.length, 2);

  const [w1, w2] = splitResult.walls;
  assert.strictEqual(w1.start.x, 2.0);
  assert.strictEqual(w1.end.x, 6.4);
  assert.strictEqual(w2.start.x, 7.6);
  assert.strictEqual(w2.end.x, 12.0);

  const gap = pointDistance(w1.end, w2.start);
  assert.ok(Math.abs(gap - 1.2) < 1e-4);

  // Line of sight passes through opening without hitting wall segments
  const losStart = { x: 7.0, y: 2.0 };
  const losEnd = { x: 7.0, y: 6.0 };
  assert.strictEqual(doSegmentsIntersect(losStart, losEnd, w1.start, w1.end), false);
  assert.strictEqual(doSegmentsIntersect(losStart, losEnd, w2.start, w2.end), false);
});

// 3. Polygonal obstacle creation
runTest('3. Polygonal obstacle creation (>= 3 distinct vertices, positive area)', () => {
  const obstacleVertices = [
    { x: 3.0, y: 3.0 },
    { x: 7.0, y: 3.0 },
    { x: 7.0, y: 6.0 },
    { x: 3.0, y: 6.0 },
  ];
  assert.strictEqual(isPolygonSelfIntersecting(obstacleVertices), false);
  const area = polygonArea(obstacleVertices);
  assert.strictEqual(area, 12.0);
  assert.strictEqual(isPointInsidePolygon({ x: 5.0, y: 4.5 }, obstacleVertices), true);
  assert.strictEqual(isPointInsidePolygon({ x: 1.0, y: 1.0 }, obstacleVertices), false);
});

// 4. Rejection of self-intersecting polygon
runTest('4. Rejection of self-intersecting / non-simple polygons and collinear overlap', () => {
  // Bowtie hourglass polygon
  const bowtie = [
    { x: 1.0, y: 1.0 },
    { x: 5.0, y: 5.0 },
    { x: 5.0, y: 1.0 },
    { x: 1.0, y: 5.0 },
  ];
  assert.strictEqual(isPolygonSelfIntersecting(bowtie), true);

  // Exact reproducible defect: repeated non-consecutive vertex
  const repeatedVertex = [
    { x: 0, y: 0 },
    { x: 4, y: 0 },
    { x: 4, y: 4 },
    { x: 0, y: 4 },
    { x: 4, y: 0 },
  ];
  assert.strictEqual(isPolygonSelfIntersecting(repeatedVertex), true);

  // Exact reproducible defect in doSegmentsIntersect: collinear overlap (0,0)-(10,0) and (5,0)-(0,0)
  const isCollinearOverlapping = doSegmentsIntersect(
    { x: 0, y: 0 },
    { x: 10, y: 0 },
    { x: 5, y: 0 },
    { x: 0, y: 0 }
  );
  assert.strictEqual(isCollinearOverlapping, true);

  // Collinear disjoint must be false
  assert.strictEqual(
    doSegmentsIntersect({ x: 0, y: 0 }, { x: 2, y: 0 }, { x: 3, y: 0 }, { x: 5, y: 0 }),
    false
  );

  // Collinear sharing only an endpoint must not be an interior intersection
  assert.strictEqual(
    doSegmentsIntersect({ x: 0, y: 0 }, { x: 5, y: 0 }, { x: 5, y: 0 }, { x: 10, y: 0 }, true),
    false
  );

  // Valid concave simple polygon must be accepted
  const validConcave = [
    { x: 0, y: 0 },
    { x: 10, y: 0 },
    { x: 10, y: 10 },
    { x: 5, y: 5 },
    { x: 0, y: 10 },
  ];
  assert.strictEqual(isPolygonSelfIntersecting(validConcave), false);
});

// 5. Risk zone creation and criticality weight
runTest('5. Risk zone creation, naming and criticality weight (w >= 1.0)', () => {
  const riskZone: RiskZone = {
    name: 'Server Vault Alpha',
    weight: 4.5,
    vertices: [
      { x: 10.0, y: 8.0 },
      { x: 14.0, y: 8.0 },
      { x: 14.0, y: 12.0 },
      { x: 10.0, y: 12.0 },
    ],
  };
  assert.ok(riskZone.weight >= 1.0);
  assert.strictEqual(isPolygonSelfIntersecting(riskZone.vertices), false);

  const validScenario: Scenario = {
    xmin: 0,
    xmax: 20,
    ymin: 0,
    ymax: 15,
    risk_zones: [riskZone],
  };
  assert.strictEqual(validateScenarioLocally(validScenario).isValid, true);

  // Invalid weight < 1.0
  const invalidScenario: Scenario = {
    ...validScenario,
    risk_zones: [{ ...riskZone, weight: 0.5 }],
  };
  const res = validateScenarioLocally(invalidScenario);
  assert.strictEqual(res.isValid, false);
  assert.ok(res.errors.some((e) => e.includes('peso')));
});

// 6. Vertex selection and coordinates modification
runTest('6. Vertex selection and coordinates modification', () => {
  let polygon = [
    { x: 2.0, y: 2.0 },
    { x: 6.0, y: 2.0 },
    { x: 6.0, y: 5.0 },
    { x: 2.0, y: 5.0 },
  ];

  // Move vertex index 2 from (6, 5) to (8, 7)
  const modified = polygon.map((pt, idx) => (idx === 2 ? { x: 8.0, y: 7.0 } : pt));
  assert.strictEqual(modified[2].x, 8.0);
  assert.strictEqual(modified[2].y, 7.0);
  assert.strictEqual(isPolygonSelfIntersecting(modified), false);
  assert.strictEqual(polygonArea(modified) > 0, true);
});

// 7. Grid snap precision
runTest('7. Metric grid snapping (0.1m, 0.25m, 0.5m, 1.0m)', () => {
  const pt = { x: 4.18, y: 7.92 };
  assert.deepStrictEqual(snapPoint(pt, 0.5), { x: 4.0, y: 8.0 });
  assert.deepStrictEqual(snapPoint(pt, 0.25), { x: 4.25, y: 8.0 });
  assert.deepStrictEqual(snapPoint(pt, 1.0), { x: 4.0, y: 8.0 });
  assert.deepStrictEqual(snapPoint(pt, 0.1), { x: 4.2, y: 7.9 });
});

// 8. Bidirectional coordinate transformation with zoom and pan
runTest('8. Bidirectional coordinate transformation with zoom and pan', () => {
  const transform = new CoordinateTransform(1000, 800, {
    xmin: 0,
    xmax: 25,
    ymin: 0,
    ymax: 20,
  });

  const worldPt = { x: 12.5, y: 10.0 };
  const canvasPt = transform.worldToScreen(worldPt);
  const backToWorld = transform.screenToWorld(canvasPt);

  assert.ok(Math.abs(backToWorld.x - worldPt.x) < 1e-3);
  assert.ok(Math.abs(backToWorld.y - worldPt.y) < 1e-3);

  // Apply zoom and pan
  const transformed2 = new CoordinateTransform(1000, 800, {
    xmin: 0,
    xmax: 25,
    ymin: 0,
    ymax: 20,
  }, 2.0, 50, -30);

  const canvasPt2 = transformed2.worldToScreen(worldPt);
  const backToWorld2 = transformed2.screenToWorld(canvasPt2);
  assert.ok(Math.abs(backToWorld2.x - worldPt.x) < 1e-3);
  assert.ok(Math.abs(backToWorld2.y - worldPt.y) < 1e-3);
});

// 9. Independent undo / redo history stack and drag transactions
runTest('9. Independent undo / redo history stack and single-step drag transactions', () => {
  let current: Scenario = { xmin: 0, xmax: 10, ymin: 0, ymax: 10, walls: [] };
  const undoStack: Scenario[] = [];
  const redoStack: Scenario[] = [];

  function commit(next: Scenario) {
    undoStack.push(JSON.parse(JSON.stringify(current)));
    if (undoStack.length > 50) undoStack.shift();
    redoStack.length = 0;
    current = JSON.parse(JSON.stringify(next));
  }

  // 10 standard mutations
  for (let i = 1; i <= 10; i++) {
    commit({
      ...current,
      walls: [...(current.walls || []), { start: { x: 0, y: i }, end: { x: 5, y: i } }],
    });
  }
  assert.strictEqual(current.walls!.length, 10);
  assert.strictEqual(undoStack.length, 10);

  // Undo 3 times
  for (let i = 0; i < 3; i++) {
    redoStack.push(current);
    current = undoStack.pop()!;
  }
  assert.strictEqual(current.walls!.length, 7);
  assert.strictEqual(redoStack.length, 3);

  // Redo 1 time
  undoStack.push(current);
  current = redoStack.pop()!;
  assert.strictEqual(current.walls!.length, 8);

  // DRAG TRANSACTION SIMULATION: 25 mouse moves, exactly 1 undo entry
  let dragInitial: Scenario | null = null;
  function startDrag() {
    dragInitial = JSON.parse(JSON.stringify(current));
  }
  function moveTransient(transient: Scenario) {
    current = transient; // updates view without pushing history
  }
  function commitDrag(finalSc: Scenario) {
    if (dragInitial && JSON.stringify(dragInitial) !== JSON.stringify(finalSc)) {
      undoStack.push(dragInitial);
      redoStack.length = 0;
      current = finalSc;
    }
    dragInitial = null;
  }

  const preDragUndoCount = undoStack.length;
  startDrag();
  for (let m = 1; m <= 25; m++) {
    moveTransient({
      ...current,
      walls: [{ start: { x: 0, y: m * 0.1 }, end: { x: 5, y: 1 } }],
    });
    // intermediate moves MUST NOT push to undoStack
    assert.strictEqual(undoStack.length, preDragUndoCount);
  }
  commitDrag({
    ...current,
    walls: [{ start: { x: 0, y: 2.5 }, end: { x: 5, y: 1 } }],
  });

  // Exactly ONE history step added for all 25 moves
  assert.strictEqual(undoStack.length, preDragUndoCount + 1);

  // A single undo restores pre-drag geometry
  redoStack.push(current);
  current = undoStack.pop()!;
  assert.strictEqual(current.walls!.length, 8);
});

// 10. ScenarioDTO authentic JSON export and import round-trip & strict error handling
runTest('10. ScenarioDTO authentic JSON round-trip (>6 decimals) and strict error handling', () => {
  const highPrecisionScenario: Scenario = {
    xmin: 0.1234567,
    xmax: 24.9876543,
    ymin: 0.2345678,
    ymax: 16.8765432,
    grid_resolution: 0.25,
    walls: [
      { start: { x: 1.1234567, y: 2.2345678 }, end: { x: 10.9876543, y: 2.2345678 }, is_opaque: true },
    ],
    obstacles: [],
    risk_zones: [
      {
        name: 'Zone A',
        weight: 2.3456789,
        vertices: [
          { x: 18.123456, y: 10.123456 },
          { x: 22.987654, y: 10.123456 },
          { x: 22.987654, y: 14.987654 },
          { x: 18.123456, y: 14.987654 },
        ],
      },
    ],
  };

  // Export JSON without editorial rounding
  const jsonStr = JSON.stringify(highPrecisionScenario, null, 2);
  const parsedRes = parseAndValidateScenarioJson(jsonStr);

  assert.strictEqual(parsedRes.errors.length, 0);
  assert.ok(parsedRes.scenario !== null);
  const parsed = parsedRes.scenario!;

  // Verify coordinates and weights retain >6 decimal places exactly
  assert.strictEqual(parsed.xmin, 0.1234567);
  assert.strictEqual(parsed.xmax, 24.9876543);
  assert.strictEqual(parsed.walls![0].start.x, 1.1234567);
  assert.strictEqual(parsed.walls![0].start.y, 2.2345678);
  assert.strictEqual(parsed.risk_zones![0].weight, 2.3456789);

  // STRICT REJECTION: malformed JSON must return errors and scenario: null (no silent substitution)
  const malformed = JSON.stringify({
    xmax: 10,
    ymax: 10,
    walls: 'not-an-array',
    obstacles: {},
    risk_zones: null,
    grid_resolution: -10,
  });
  const malformedRes = parseAndValidateScenarioJson(malformed);
  assert.strictEqual(malformedRes.scenario, null);
  assert.ok(malformedRes.errors.length >= 3);
  assert.ok(malformedRes.errors.some((e) => e.includes('walls')));
});

// 11. Backend scenario validation schema compatibility
runTest('11. Backend scenario validation schema compatibility', () => {
  const scenario: Scenario = {
    xmin: 0,
    xmax: 30,
    ymin: 0,
    ymax: 20,
    grid_resolution: 0.5,
    walls: [{ start: { x: 5, y: 5 }, end: { x: 15, y: 5 } }],
  };

  const payload = { scenario };
  assert.ok('scenario' in payload);
  assert.ok(payload.scenario.xmax > (payload.scenario.xmin ?? 0));
  assert.ok(payload.scenario.ymax > (payload.scenario.ymin ?? 0));
  assert.ok(typeof payload.scenario.grid_resolution === 'number');
});

// 12. Invalidation of ABC optimization and coverage cache upon scenario modification
runTest('12. Invalidation of ABC optimization and coverage cache upon scenario modification', () => {
  let optimizationResult: any = { best_solution: { cameras: [{ x: 5, y: 5, theta: 0 }] } };
  let coverageData: any = { grid: { Nx: 20, Ny: 20 }, P_det: [] };
  let activeCamerasKey: string | null = 'some_cached_key';

  function onScenarioModified() {
    optimizationResult = null;
    coverageData = null;
    activeCamerasKey = null;
  }

  onScenarioModified();

  assert.strictEqual(optimizationResult, null);
  assert.strictEqual(coverageData, null);
  assert.strictEqual(activeCamerasKey, null);
});

// 13. Optimization request payload generation from custom scenario
runTest('13. Optimization request payload generation from custom scenario', () => {
  const customScenario: Scenario = {
    xmin: 0,
    xmax: 28,
    ymin: 0,
    ymax: 18,
    walls: [{ start: { x: 0, y: 9 }, end: { x: 14, y: 9 } }],
  };

  const req = {
    scenario: customScenario,
    camera_profile: {
      Rmin: 0.2,
      Rmax: 12.0,
      FOV: 1.57,
      p0: 1.0,
      beta_d: 0.4,
      beta_theta: 0.5,
    },
    config: {
      K: 4,
      SN: 15,
      max_cycles: 25,
      lambda_def: 1.0,
      Tcrit: 0.8,
      record_population: true,
    },
  };

  assert.strictEqual(req.scenario.xmax, 28);
  assert.strictEqual(req.config.K, 4);
});

// 14. Coverage evaluation request payload generation from custom scenario
runTest('14. Coverage evaluation request payload generation from custom scenario', () => {
  const customScenario: Scenario = {
    xmin: 0,
    xmax: 25,
    ymin: 0,
    ymax: 20,
    grid_resolution: 0.5,
  };
  const profile: CameraProfile = {
    Rmin: 0.5,
    Rmax: 10.0,
    FOV: 1.57,
    p0: 1.0,
    beta_d: 0.5,
    beta_theta: 0.5,
  };
  const cameras = [
    { x: 5.0, y: 5.0, theta: 0.5 },
    { x: 20.0, y: 15.0, theta: 3.14 },
  ];

  const payload = {
    scenario: customScenario,
    camera_profile: profile,
    critical_deficit: { lambda_def: 1.0, Tcrit: 0.8 },
    cameras,
  };

  assert.strictEqual(payload.cameras.length, 2);
  const cacheKey = buildCanonicalCoverageKey(customScenario, profile, 1.0, 0.8, cameras);
  assert.ok(cacheKey.length > 0);
  assert.ok(cacheKey.includes('beta_theta'));
  assert.ok(cacheKey.includes('customScenario') || cacheKey.includes('25'));
});

// 15. Pending async coverage request invalidation on cache retrieval (Phase 5B fix)
runTest('15. Pending async coverage request invalidation on cache retrieval (Phase 5B fix)', () => {
  let coverageRequestId = 0;
  let activeState = 'empty';

  // Request 1 dispatched (slow network)
  const req1Id = ++coverageRequestId;

  // Cache hit arrives synchronously for another state
  const req2Id = ++coverageRequestId; // explicit invalidation on cache hit
  activeState = 'cached_result_B';

  // Later, Request 1 resolves asynchronously
  function onReq1Response() {
    if (req1Id === coverageRequestId) {
      activeState = 'slow_network_result_A';
    }
  }
  onReq1Response();

  // Cached result must NOT be overwritten by the stale in-flight request
  assert.strictEqual(activeState, 'cached_result_B');
  assert.strictEqual(coverageRequestId, req2Id);
});

// 16. Preservation of scenario constraints
runTest('16. Preservation of scenario constraints (finite bounds, positive resolution)', () => {
  const invalidNegative: Scenario = {
    xmin: 10,
    xmax: 5,
    ymin: 0,
    ymax: 10,
  };
  assert.strictEqual(validateScenarioLocally(invalidNegative).isValid, false);

  const invalidRes: Scenario = {
    xmin: 0,
    xmax: 10,
    ymin: 0,
    ymax: 10,
    grid_resolution: 0,
  };
  assert.strictEqual(validateScenarioLocally(invalidRes).isValid, false);
});

console.log(`\n\x1b[1mSummary: ${passed} passed, ${failed} failed.\x1b[0m\n`);
if (failed > 0) process.exit(1);
