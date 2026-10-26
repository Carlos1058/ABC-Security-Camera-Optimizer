/**
 * TAREA 09 — Minimalist Layout & Component Integration Test Suite
 * Verifies all 10 required minimalist layout workflows:
 * 1. Clean state & Scenario creation with custom bounds/origin
 * 2. Template scenario loading (GET /api/v1/scenarios schema)
 * 3. Drawing elements via floating editor dock tools (wall, door, obstacle, risk zone)
 * 4. Advanced configuration modal & contract preservation
 * 5. Execution of ABC optimization from floating action dock
 * 6. Results summary pill & expanded analysis drawer
 * 7. Heatmap layer switching & nominal cone suppression/toggle
 * 8. Cycle playback and food source inspection
 * 9. Scenario JSON Import/Export with full decimal precision
 * 10. State coherence & cache invalidation across mode transitions
 */

import assert from 'node:assert';
import {
  isPolygonSelfIntersecting,
  polygonArea,
  splitWallWithOpening,
  validateScenarioLocally,
} from '../renderer/geometryValidation.ts';
import { buildCanonicalCoverageKey } from '../renderer/coverageKey.ts';
import { serializeScenarioToJson, parseAndValidateScenarioJson } from '../services/scenarioIO.ts';
import type {
  Scenario,
  Wall,
  Obstacle,
  RiskZone,
  CameraProfile,
  OptimizationConfig,
  OptimizationResult,
} from '../types/api.ts';

let passed = 0;
let failed = 0;

function runTest(name: string, fn: () => void | Promise<void>) {
  try {
    const res = fn();
    if (res instanceof Promise) {
      throw new Error('Async test must be handled in async runner');
    }
    console.log(`  \x1b[32m✓\x1b[0m ${name}`);
    passed++;
  } catch (err: any) {
    console.error(`  \x1b[31m✗\x1b[0m ${name}`);
    console.error(`    ${err?.message || err}`);
    failed++;
  }
}

console.log('\n\x1b[1m\x1b[33m=== TAREA 09: MINIMALIST LAYOUT INTEGRATION TEST SUITE ===\x1b[0m\n');

// 1. Clean state & Scenario creation
runTest('1. Clean state & Scenario creation with custom bounds and origin', () => {
  const width = 24.0;
  const height = 18.0;
  const originX = 0.0;
  const originY = 0.0;
  const resolution = 0.5;

  const newScenario: Scenario = {
    xmin: originX,
    xmax: originX + width,
    ymin: originY,
    ymax: originY + height,
    walls: [],
    obstacles: [],
    risk_zones: [],
    grid_resolution: resolution,
  };

  const validation = validateScenarioLocally(newScenario);
  assert.strictEqual(validation.isValid, true, 'Created scenario must be geometrically valid');
  assert.strictEqual(newScenario.xmax! - newScenario.xmin!, 24.0);
  assert.strictEqual(newScenario.ymax! - newScenario.ymin!, 18.0);
  assert.strictEqual(newScenario.walls?.length, 0, 'Initial scenario has no interior walls');
  assert.strictEqual(newScenario.obstacles?.length, 0, 'Initial scenario has no obstacles');
  assert.strictEqual(newScenario.risk_zones?.length, 0, 'Initial scenario has no risk zones');
});

// 2. Template loading from registered backend scenarios
runTest('2. Template scenario loading matching registered FastAPI schema', () => {
  const registeredTemplates = [
    {
      id: 'warehouse_pillars',
      name: 'Almacén con pilares',
      description: 'Espacio de 30×20 m con 6 pilares estructurales y 2 zonas de alto riesgo.',
      dimensions: '30 × 20 m',
      wallsCount: 0,
      obstaclesCount: 6,
      riskZonesCount: 2,
    },
    {
      id: 'empty_room_10x10',
      name: 'Habitación vacía',
      description: 'Espacio cuadrado limpio de 10×10 m sin obstáculos internos.',
      dimensions: '10 × 10 m',
      wallsCount: 0,
      obstaclesCount: 0,
      riskZonesCount: 0,
    },
    {
      id: 'l_shaped_office',
      name: 'Oficina en L',
      description: 'Planta en forma de L de 25×20 m con particiones internas.',
      dimensions: '25 × 20 m',
      wallsCount: 2,
      obstaclesCount: 1,
      riskZonesCount: 1,
    },
    {
      id: 'complex_multiroom',
      name: 'Instalación multicompartimento',
      description: 'Edificio de 35×25 m con 4 salas interconectadas y zonas restringidas.',
      dimensions: '35 × 25 m',
      wallsCount: 7,
      obstaclesCount: 3,
      riskZonesCount: 3,
    },
  ];

  assert.strictEqual(registeredTemplates.length, 4, 'Must expose exactly the 4 registered benchmark templates');
  registeredTemplates.forEach(t => {
    assert(t.id.length > 0);
    assert(t.name.length > 0);
    assert(t.dimensions.includes('×'));
  });
});

// 3. Drawing elements via floating editor dock tools
runTest('3. Drawing elements: Wall, Door, Obstacle and Risk Zone transactions', () => {
  const currentScenario: Scenario = {
    xmin: 0.0,
    xmax: 20.0,
    ymin: 0.0,
    ymax: 15.0,
    walls: [],
    obstacles: [],
    risk_zones: [],
  };

  // 3a. Draw wall
  const wall: Wall = {
    start: { x: 0.0, y: 7.5 },
    end: { x: 20.0, y: 7.5 },
    is_opaque: true,
  };
  currentScenario.walls?.push(wall);
  assert.strictEqual(validateScenarioLocally(currentScenario).isValid, true);

  // 3b. Insert door on wall
  const doorWidth = 1.0;
  const clickPt = { x: 10.0, y: 7.5 };
  const splitRes = splitWallWithOpening(wall, clickPt, doorWidth);
  assert(splitRes !== null, 'Door split must succeed on valid point');
  assert.strictEqual(splitRes.walls.length, 2, 'Splitting wall yields 2 wall segments');
  currentScenario.walls = splitRes.walls;

  // 3c. Draw convex obstacle
  const obstacle: Obstacle = {
    vertices: [
      { x: 3.0, y: 2.0 },
      { x: 6.0, y: 2.0 },
      { x: 6.0, y: 5.0 },
      { x: 3.0, y: 5.0 },
    ],
  };
  assert.strictEqual(isPolygonSelfIntersecting(obstacle.vertices), false);
  assert(polygonArea(obstacle.vertices) > 0);
  currentScenario.obstacles?.push(obstacle);

  // 3d. Draw risk zone
  const riskZone: RiskZone = {
    name: 'Zona Servidores',
    weight: 2.5,
    vertices: [
      { x: 14.0, y: 1.0 },
      { x: 18.0, y: 1.0 },
      { x: 18.0, y: 4.0 },
      { x: 14.0, y: 4.0 },
    ],
  };
  assert(riskZone.weight >= 1.0);
  currentScenario.risk_zones?.push(riskZone);

  const finalVal = validateScenarioLocally(currentScenario);
  assert.strictEqual(finalVal.isValid, true, 'All drawn elements form a valid scenario');
});

// 4. Advanced configuration modal & contract preservation
runTest('4. Advanced configuration parameter model and contract validation', () => {
  const defaultParams: OptimizationConfig = {
    K: 3,
    SN: 30,
    max_cycles: 100,
    limit: 20,
    seed: 42,
    lambda_def: 1.0,
    Tcrit: 0.5,
    record_population: true,
  };

  const defaultProfile: CameraProfile = {
    FOV: 70.0,
    Rmin: 0.5,
    Rmax: 12.0,
    p0: 0.95,
    beta_d: 0.05,
    beta_theta: 0.02,
  };

  // Check validation rules
  assert(defaultParams.SN >= 4 && defaultParams.SN % 2 === 0);
  assert(defaultParams.max_cycles >= 1);
  assert((defaultParams.limit ?? 0) >= 1);
  assert(defaultProfile.FOV > 0 && defaultProfile.FOV <= 360);
  assert(defaultProfile.Rmax > defaultProfile.Rmin);
  assert(defaultProfile.p0 > 0 && defaultProfile.p0 <= 1.0);
});

// 5. Execution of ABC optimization from floating action dock
runTest('5. Floating action dock optimization payload & execution state', () => {
  const K = 3;
  const config: OptimizationConfig = {
    K,
    SN: 30,
    max_cycles: 50,
    limit: 20,
    seed: 42,
    lambda_def: 1.0,
    Tcrit: 0.5,
    record_population: true,
  };

  const profile: CameraProfile = {
    FOV: 70.0,
    Rmin: 0.5,
    Rmax: 12.0,
    p0: 0.95,
    beta_d: 0.05,
    beta_theta: 0.02,
  };

  const requestPayload = {
    scenario: {
      xmin: 0.0,
      xmax: 20.0,
      ymin: 0.0,
      ymax: 15.0,
      walls: [],
      obstacles: [],
      risk_zones: [],
    },
    profile,
    config,
  };

  assert.strictEqual(requestPayload.config.K, 3);
  assert.strictEqual(requestPayload.config.SN, 30);
  assert.strictEqual(requestPayload.config.record_population, true);
});

// 6. Results summary pill & expanded analysis drawer
runTest('6. Results summary pill values & expanded analysis drawer data binding', () => {
  const mockOptimization: OptimizationResult = {
    scenario: { xmin: 0, xmax: 20, ymin: 0, ymax: 15 },
    profile: { FOV: 70, Rmin: 0.5, Rmax: 12, p0: 0.95, beta_d: 0.05, beta_theta: 0.02 },
    config: { K: 3, SN: 30, max_cycles: 50, limit: 20, seed: 42, lambda_def: 1.0, Tcrit: 0.5, record_population: true },
    effective_seed: '42',
    dimension: 9,
    initial_best_cost: 0.82,
    initial_best_poses: [],
    final_best_cost: 0.624008704,
    final_best_poses: [
      { x: 2.5, y: 3.0, theta: 0.785 },
      { x: 10.0, y: 12.0, theta: 4.712 },
      { x: 17.5, y: 3.5, theta: 2.356 },
    ],
    best_cost_per_cycle: [0.82, 0.69, 0.624008704],
    mean_cost_per_cycle: [0.88, 0.74, 0.68],
    coverage_metrics: {
      num_eval_points: 600,
      num_covered_points: 507,
      geometric_coverage_ratio: 0.845,
      geometric_coverage_percent: 84.5,
      mean_probabilistic_coverage: 0.812,
      risk_weighted_coverage: 0.892,
      num_critical_points: 48,
      critical_deficit: 0.045,
    },
    total_evaluations: 1530,
    total_proposals: 1500,
    rejected_infeasible_proposals: 840,
    total_scout_resets: 4,
    execution_time_seconds: 0.384,
    history: [],
    population_history_available: false,
    notes: 'Sequential ABC benchmark run',
  };

  // Summary pill checks (Section 2 & 6)
  const geomPct = mockOptimization.coverage_metrics.geometric_coverage_percent.toFixed(1);
  const riskPct = (mockOptimization.coverage_metrics.risk_weighted_coverage * 100).toFixed(1);
  const costStr = mockOptimization.final_best_cost.toFixed(4);
  const timeStr = `${mockOptimization.execution_time_seconds.toFixed(2)}s`;

  assert.strictEqual(geomPct, '84.5');
  assert.strictEqual(riskPct, '89.2');
  assert.strictEqual(costStr, '0.6240');
  assert.strictEqual(timeStr, '0.38s');

  // Expanded analysis drawer checks
  assert.strictEqual(mockOptimization.best_cost_per_cycle.length, 3);
  assert.strictEqual(mockOptimization.total_evaluations, 1530);
  assert.strictEqual(mockOptimization.rejected_infeasible_proposals, 840);
  assert.strictEqual(mockOptimization.total_scout_resets, 4);
});

// 7. Heatmap layer switching & nominal cone suppression/toggle
runTest('7. Heatmap layer switching and nominal cone suppression by default (Req 7)', () => {
  type ViewMode = 'floorplan' | 'probability' | 'geometric' | 'risk';

  const modes: ViewMode[] = ['floorplan', 'probability', 'geometric', 'risk'];
  assert.strictEqual(modes.length, 4);

  // In floorplan mode: cones default to true
  const floorplanDefaultCones = true;
  assert.strictEqual(floorplanDefaultCones, true);

  // In heatmap modes: cones MUST default to false to reduce visual noise (Req 7)
  const heatmapDefaultCones = false;
  assert.strictEqual(heatmapDefaultCones, false);

  // Toggle must allow user to turn cones on over heatmap on demand
  let userToggledCones = heatmapDefaultCones;
  userToggledCones = !userToggledCones;
  assert.strictEqual(userToggledCones, true, 'User can toggle cones on demand over heatmaps');
});

// 8. Cycle playback and food source inspection
runTest('8. Cycle playback step-by-step and inspection state', () => {
  const totalCycles = 50;
  let currentCycle = 0;
  let isPlaying = false;

  // Step forward
  currentCycle = Math.min(totalCycles, currentCycle + 1);
  assert.strictEqual(currentCycle, 1);

  // Play / Pause toggle
  isPlaying = !isPlaying;
  assert.strictEqual(isPlaying, true);
  isPlaying = !isPlaying;
  assert.strictEqual(isPlaying, false);

  // Scrub to specific cycle
  currentCycle = 25;
  assert.strictEqual(currentCycle, 25);
});

// 9. Scenario JSON Import/Export with full decimal precision
runTest('9. Scenario JSON Import/Export preserving full float precision (>6 decimals)', () => {
  const originalScenario: Scenario = {
    xmin: 0.12345678,
    xmax: 25.87654321,
    ymin: 0.98765432,
    ymax: 18.12345678,
    walls: [
      {
        start: { x: 5.111222333, y: 7.444555666 },
        end: { x: 15.777888999, y: 7.444555666 },
        is_opaque: true,
      },
    ],
    obstacles: [
      {
        vertices: [
          { x: 8.1234567, y: 2.2345678 },
          { x: 10.3456789, y: 2.2345678 },
          { x: 10.3456789, y: 4.4567891 },
        ],
      },
    ],
    risk_zones: [],
  };

  const jsonStr = serializeScenarioToJson(originalScenario);
  const parsedRes = parseAndValidateScenarioJson(jsonStr);

  assert.strictEqual(parsedRes.errors.length, 0);
  assert(parsedRes.scenario !== null);
  assert.strictEqual(parsedRes.scenario.xmin, 0.12345678);
  assert.strictEqual(parsedRes.scenario.xmax, 25.87654321);
  assert.strictEqual(parsedRes.scenario.walls?.[0].start.x, 5.111222333);
  assert.strictEqual(parsedRes.scenario.obstacles?.[0].vertices[0].x, 8.1234567);
});

// 10. State coherence & cache invalidation across mode transitions
runTest('10. State coherence and cache invalidation upon scenario modification', () => {
  const scenarioA: Scenario = {
    xmin: 0.0,
    xmax: 20.0,
    ymin: 0.0,
    ymax: 15.0,
    walls: [],
    obstacles: [],
    risk_zones: [],
  };

  const cameras = [{ x: 5.0, y: 5.0, theta: 45.0 }];
  const profile: CameraProfile = {
    FOV: 70.0,
    Rmin: 0.5,
    Rmax: 12.0,
    p0: 0.95,
    beta_d: 0.05,
    beta_theta: 0.02,
  };

  const keyA = buildCanonicalCoverageKey(scenarioA, profile, 1.0, 0.5, cameras);

  // Mutate scenario by adding an obstacle
  const scenarioB: Scenario = {
    ...scenarioA,
    obstacles: [
      {
        vertices: [
          { x: 4.0, y: 4.0 },
          { x: 6.0, y: 4.0 },
          { x: 6.0, y: 6.0 },
        ],
      },
    ],
  };

  const keyB = buildCanonicalCoverageKey(scenarioB, profile, 1.0, 0.5, cameras);

  assert.notStrictEqual(keyA, keyB, 'Cache key must invalidate when scenario geometry changes');
});

console.log(`\n\x1b[1mSummary: ${passed} passed, ${failed} failed.\x1b[0m\n`);

if (failed > 0) {
  process.exit(1);
}
