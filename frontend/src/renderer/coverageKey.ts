import type { CameraPose, CameraProfile, Scenario } from '../types/api'

/**
 * Builds a deterministic canonical key for a spatial coverage evaluation.
 *
 * Requirements:
 * - Full geometry: bounds, resolution, walls, obstacles, risk zones.
 * - Full optical profile: Rmin, Rmax, FOV, p0, beta_d, beta_theta.
 * - Full objective parameters: lambda_def, t_crit.
 * - Exact ordered camera poses: x, y, theta WITHOUT lossy rounding (no toFixed).
 *
 * Guarantees zero quantization collisions so two configurations with minor differences
 * (e.g. theta=0.1001 vs theta=0.1004, or dx < 0.01m) produce distinct identities.
 */
export function buildCanonicalCoverageKey(
  scenario: Scenario,
  profile: CameraProfile,
  lambda_def: number,
  t_crit: number,
  cameras: CameraPose[]
): string {
  if (cameras.length === 0) return ''

  return JSON.stringify({
    scenario: {
      xmin: scenario.xmin,
      xmax: scenario.xmax,
      ymin: scenario.ymin,
      ymax: scenario.ymax,
      grid_resolution: scenario.grid_resolution,
      walls: (scenario.walls || []).map(w => ({
        start: { x: w.start.x, y: w.start.y },
        end: { x: w.end.x, y: w.end.y },
        is_opaque: w.is_opaque,
      })),
      obstacles: (scenario.obstacles || []).map(o => ({
        vertices: o.vertices.map(v => ({ x: v.x, y: v.y })),
      })),
      risk_zones: (scenario.risk_zones || []).map(rz => ({
        name: rz.name,
        weight: rz.weight,
        vertices: rz.vertices.map(v => ({ x: v.x, y: v.y })),
      })),
    },
    profile: {
      Rmin: profile.Rmin,
      Rmax: profile.Rmax,
      FOV: profile.FOV,
      p0: profile.p0,
      beta_d: profile.beta_d,
      beta_theta: profile.beta_theta,
    },
    objective: {
      lambda_def,
      t_crit,
    },
    cameras: cameras.map(c => ({
      x: c.x,
      y: c.y,
      theta: c.theta,
    })),
  })
}
