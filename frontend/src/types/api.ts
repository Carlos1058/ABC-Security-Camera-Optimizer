/**
 * Data contracts and DTOs matching the ABC Security Camera Optimizer FastAPI Backend.
 * Strictly aligned with backend/src/camera_optimizer/api/schemas.py.
 */

export interface Point {
  x: number;
  y: number;
}

export interface Wall {
  start: Point;
  end: Point;
  is_opaque?: boolean;
}

export interface Obstacle {
  vertices: Point[];
}

export interface RiskZone {
  vertices: Point[];
  weight: number;
  name?: string;
}

export interface Scenario {
  xmin?: number;
  xmax: number;
  ymin?: number;
  ymax: number;
  walls?: Wall[];
  obstacles?: Obstacle[];
  risk_zones?: RiskZone[];
  grid_resolution?: number;
}

export interface CameraProfile {
  Rmin: number;
  Rmax: number;
  FOV: number;
  p0: number;
  beta_d: number;
  beta_theta: number;
}

export interface OptimizationConfig {
  K: number;
  SN: number;
  max_cycles: number;
  limit?: number | null;
  seed?: string | number | null;
  lambda_def: number;
  Tcrit: number;
  record_population: boolean;
}

export interface CameraPose {
  x: number;
  y: number;
  theta: number;
  theta_deg?: number;
}

export interface CoverageMetrics {
  num_eval_points: number;
  num_covered_points: number;
  geometric_coverage_ratio: number;
  geometric_coverage_percent: number;
  mean_probabilistic_coverage: number;
  risk_weighted_coverage: number;
  num_critical_points: number;
  critical_deficit: number;
}

export interface FoodSource {
  position: number[];
  poses: CameraPose[];
  cost: number;
  fitness: number;
  trial: number;
}

export interface CycleSnapshot {
  cycle: number;
  best_cost: number;
  best_poses: CameraPose[];
  mean_population_cost: number;
  improvements_count: number;
  scout_resets: number;
  population?: FoodSource[] | null;
}

export interface OptimizationResult {
  scenario: Scenario;
  profile: CameraProfile;
  config: OptimizationConfig;
  effective_seed: string;
  dimension: number;
  initial_best_cost: number;
  initial_best_poses: CameraPose[];
  final_best_cost: number;
  final_best_poses: CameraPose[];
  best_cost_per_cycle: number[];
  mean_cost_per_cycle: number[];
  coverage_metrics: CoverageMetrics;
  total_evaluations: number;
  total_proposals: number;
  rejected_infeasible_proposals: number;
  total_scout_resets: number;
  execution_time_seconds: number;
  history: CycleSnapshot[];
  population_history_available: boolean;
  notes: string;
}

export interface OptimizationRequest {
  scenario: Scenario;
  profile: CameraProfile;
  config: OptimizationConfig;
}

export interface ValidationRequest {
  scenario: Scenario;
  profile: CameraProfile;
  config: OptimizationConfig;
}

export interface ValidationResponse {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
  details: {
    estimated_grid_cells?: number;
    actual_grid_nodes?: number;
    estimated_nfe_upper?: number;
    estimated_work_upper?: number;
    estimated_population_history_elements?: number;
    [key: string]: unknown;
  };
}

export interface PredefinedScenarioItem {
  id: string;
  name: string;
  description: string;
  scenario: Scenario;
  recommended_profile: CameraProfile;
  recommended_config: OptimizationConfig;
}

export interface PredefinedScenariosResponse {
  scenarios: PredefinedScenarioItem[];
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  is_busy: boolean;
  details?: {
    is_busy?: boolean;
    active_run_id?: string | null;
    elapsed_seconds?: number | null;
  };
}

export interface CoverageGridNode {
  x: number;
  y: number;
  probability: number;
  binary_covered: boolean;
  risk_weight: number;
}

export interface CoverageEvaluationRequest {
  scenario: Scenario;
  profile?: CameraProfile;
  cameras: CameraPose[];
  lambda_def?: number;
  t_crit?: number;
  config?: OptimizationConfig;
}

export interface CoverageEvaluationResponse {
  cell_width: number;
  cell_height: number;
  total_nodes: number;
  nodes: CoverageGridNode[];
  metrics: CoverageMetrics;
  objective_cost: number;
  is_feasible: boolean;
}

export type CanvasViewMode = 'floorplan' | 'probability' | 'geometric' | 'risk';

