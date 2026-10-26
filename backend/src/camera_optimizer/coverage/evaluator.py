"""Core evaluators for individual and multi-camera simulated detection coverage."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from camera_optimizer.camera.pose import CameraPose, wrap_pi
from camera_optimizer.camera.profile import CameraProfile
from camera_optimizer.coverage.metrics import CoverageMetrics
from camera_optimizer.domain.floorplan import FloorPlan
from camera_optimizer.domain.grid import SamplingGrid
from camera_optimizer.geometry.intersections import (
    DEFAULT_ANGULAR_TOLERANCE,
    DEFAULT_TOLERANCE,
)
from camera_optimizer.geometry.point import Point2D


def is_point_geometrically_covered(
    camera: CameraPose,
    profile: CameraProfile,
    target: Point2D,
    floorplan: FloorPlan,
    tol: float = DEFAULT_TOLERANCE,
    angular_tol: float = DEFAULT_ANGULAR_TOLERANCE,
) -> bool:
    """Determine whether a target point is geometrically visible and inside a camera's sensing sector.

    Coverage is strictly a geometric predicate:
    1. Distance d lies within [Rmin, Rmax].
    2. Absolute angular deviation |delta| lies within [0, FOV/2].
    3. Visual line of sight is unobstructed by obstacles or walls.

    This predicate is completely independent of the numerical value of the exponential
    detection probability attenuation (which may underflow to 0.0 in extreme cases).

    Parameters
    ----------
    camera : CameraPose
        Position and orientation of the observing camera.
    profile : CameraProfile
        Optical and sensing parameters of the camera.
    target : Point2D
        Evaluation target location.
    floorplan : FloorPlan
        Physical facility environment used to verify unobstructed line of sight.
    tol : float
        Spatial tolerance in meters.
    angular_tol : float
        Angular tolerance in radians.

    Returns
    -------
    bool
        True if the point is within range, aperture, and has clear line of sight; False otherwise.
    """
    if not isinstance(camera, CameraPose):
        raise TypeError(f"Expected CameraPose, got {type(camera).__name__}")
    if not isinstance(profile, CameraProfile):
        raise TypeError(f"Expected CameraProfile, got {type(profile).__name__}")
    if not isinstance(target, Point2D):
        raise TypeError(f"Expected Point2D, got {type(target).__name__}")
    if not isinstance(floorplan, FloorPlan):
        raise TypeError(f"Expected FloorPlan, got {type(floorplan).__name__}")

    # Radial distance
    dist = camera.distance_to(target)
    if dist < profile.Rmin - tol or dist > profile.Rmax + tol:
        return False

    # Angular deviation relative to optical heading
    delta = camera.angular_deviation_to(target)
    if abs(delta) > profile.half_fov + angular_tol:
        return False

    # Real geometric line of sight verification against obstacles and walls
    return floorplan.check_visibility(camera.point, target, validate_endpoints=True, tol=tol)


def calculate_point_probability(
    camera: CameraPose,
    profile: CameraProfile,
    target: Point2D,
    floorplan: FloorPlan,
    tol: float = DEFAULT_TOLERANCE,
    angular_tol: float = DEFAULT_ANGULAR_TOLERANCE,
) -> float:
    """Calculate the simulated detection probability of a single camera on a target point.

    Parameters
    ----------
    camera : CameraPose
        Position and orientation of the observing camera.
    profile : CameraProfile
        Optical and sensing parameters of the camera.
    target : Point2D
        Evaluation target location.
    floorplan : FloorPlan
        Physical facility environment used to verify unobstructed line of sight.
    tol : float
        Spatial tolerance in meters.
    angular_tol : float
        Angular tolerance in radians.

    Returns
    -------
    float
        Detection probability p_j in [0.0, 1.0]. Returns 0.0 if occluded by walls,
        outside sensing range [Rmin, Rmax], or outside angular aperture [-FOV/2, FOV/2].
    """
    if not is_point_geometrically_covered(
        camera, profile, target, floorplan, tol=tol, angular_tol=angular_tol
    ):
        return 0.0

    dist = camera.distance_to(target)
    delta = camera.angular_deviation_to(target)
    abs_delta = abs(delta)

    # Normalized distance and angle coordinates within the valid sensing cone
    u_d = (dist - profile.Rmin) / profile.range_span
    u_d = max(0.0, min(1.0, u_d))

    u_a = abs_delta / profile.half_fov
    u_a = max(0.0, min(1.0, u_a))

    # Exponential decay model with normalized squared terms
    exponent = -(profile.beta_d * (u_d ** 2) + profile.beta_theta * (u_a ** 2))
    p = profile.p0 * math.exp(exponent)
    return max(0.0, min(1.0, float(p)))


def evaluate_camera_grid_visibility_and_probabilities(
    camera: CameraPose,
    profile: CameraProfile,
    grid: SamplingGrid,
    floorplan: FloorPlan,
    tol: float = DEFAULT_TOLERANCE,
    angular_tol: float = DEFAULT_ANGULAR_TOLERANCE,
) -> tuple[np.ndarray, np.ndarray]:
    """Evaluate both the geometric visibility mask and detection probabilities across a grid.

    Decouples binary geometric coverage from numerical probability values.
    Even if extreme exponential attenuation causes the probability to underflow to 0.0 in float64,
    the geometric mask correctly records True for visible points in the sensing sector.

    Parameters
    ----------
    camera : CameraPose
        Position and heading of the camera.
    profile : CameraProfile
        Optical sensing profile.
    grid : SamplingGrid
        Discrete evaluation grid discretizing the free space.
    floorplan : FloorPlan
        Physical facility environment.
    tol : float
        Spatial tolerance in meters.
    angular_tol : float
        Angular tolerance in radians.

    Returns
    -------
    geom_mask : np.ndarray
        1D boolean array of shape (N,) indicating geometric coverage within sector.
    probs : np.ndarray
        1D float64 array of shape (N,) containing simulated detection probabilities in [0.0, 1.0].
    """
    coords, _ = grid.as_numpy_arrays()
    n_nodes = len(grid.nodes)
    geom_mask = np.zeros(n_nodes, dtype=bool)
    probs = np.zeros(n_nodes, dtype=np.float64)

    if n_nodes == 0:
        return geom_mask, probs

    # Vectorized radial distance from camera
    dx = coords[:, 0] - camera.x
    dy = coords[:, 1] - camera.y
    dist = np.hypot(dx, dy)

    # Filter points within radial range [Rmin, Rmax]
    range_mask = (dist >= profile.Rmin - tol) & (dist <= profile.Rmax + tol)

    # Vectorized circular angular deviation
    phi = np.arctan2(dy, dx)
    delta = (phi - camera.theta + np.pi) % (2.0 * np.pi) - np.pi
    abs_delta = np.abs(delta)

    # Filter points within horizontal angular cone
    fov_mask = abs_delta <= (profile.half_fov + angular_tol)

    candidate_mask = range_mask & fov_mask
    candidate_indices = np.flatnonzero(candidate_mask)

    camera_pt = camera.point

    # Evaluate exact geometric line-of-sight only for points inside the optical cone
    for idx in candidate_indices:
        target_pt = grid.nodes[idx].point
        if not floorplan.check_visibility(camera_pt, target_pt, validate_endpoints=True, tol=tol):
            continue

        # Point has unobstructed geometric line-of-sight inside the sensing cone
        geom_mask[idx] = True

        d_val = float(dist[idx])
        a_val = float(abs_delta[idx])

        u_d = max(0.0, min(1.0, (d_val - profile.Rmin) / profile.range_span))
        u_a = max(0.0, min(1.0, a_val / profile.half_fov))

        exponent = -(profile.beta_d * (u_d ** 2) + profile.beta_theta * (u_a ** 2))
        p = profile.p0 * math.exp(exponent)
        probs[idx] = max(0.0, min(1.0, p))

    return geom_mask, probs


def evaluate_camera_grid(
    camera: CameraPose,
    profile: CameraProfile,
    grid: SamplingGrid,
    floorplan: FloorPlan,
    tol: float = DEFAULT_TOLERANCE,
    angular_tol: float = DEFAULT_ANGULAR_TOLERANCE,
) -> np.ndarray:
    """Evaluate detection probabilities of a camera across all evaluation nodes of a grid.

    Maintains backward compatibility by returning the float64 probability array.

    Parameters
    ----------
    camera : CameraPose
        Position and heading of the camera.
    profile : CameraProfile
        Optical sensing profile.
    grid : SamplingGrid
        Discrete evaluation grid discretizing the free space.
    floorplan : FloorPlan
        Physical facility environment.
    tol : float
        Spatial tolerance in meters.
    angular_tol : float
        Angular tolerance in radians.

    Returns
    -------
    np.ndarray
        1D array of shape (N,) containing float64 probabilities p_j(i) in [0.0, 1.0].
    """
    _, probs = evaluate_camera_grid_visibility_and_probabilities(
        camera, profile, grid, floorplan, tol=tol, angular_tol=angular_tol
    )
    return probs


def evaluate_multicamera_coverage(
    cameras: Sequence[CameraPose],
    profile: CameraProfile,
    grid: SamplingGrid,
    floorplan: FloorPlan,
    t_crit: float = 0.8,
    tol: float = DEFAULT_TOLERANCE,
    angular_tol: float = DEFAULT_ANGULAR_TOLERANCE,
) -> CoverageMetrics:
    """Evaluate combined coverage and detailed metrics for a configuration of K cameras.

    Combined detection probability under conditional independence:
        P_det(i) = 1.0 - PRODUCT_{j=1..K} (1.0 - p_j(i))

    Geometric coverage:
        Point i is covered if at least one camera can geometrically observe it (range, FOV, line-of-sight),
        independent of probability attenuation underflow.

    Risk-weighted coverage:
        C_risk = SUM(w_i * P_det(i)) / SUM(w_i)
        Computed using numerically scaled weights (w_i / max(w)) to prevent overflow with large weights (e.g. 1e308).

    Critical zone deficit:
        Deficit_crit = SUM_{i in crit} (w_i * max(0, T_crit - P_det(i))) / SUM_{i in crit} (w_i)
        where critical nodes are those with w_i > 1.0. If no critical nodes exist, Deficit_crit = 0.0.

    Parameters
    ----------
    cameras : Sequence[CameraPose]
        Sequence of camera poses.
    profile : CameraProfile
        Optical sensor profile shared across cameras.
    grid : SamplingGrid
        Discrete spatial evaluation grid.
    floorplan : FloorPlan
        Facility geometry with boundaries, walls, and obstacles.
    t_crit : float
        Critical detection probability threshold in (0.0, 1.0].
    tol : float
        Spatial tolerance in meters.
    angular_tol : float
        Angular tolerance in radians.

    Returns
    -------
    CoverageMetrics
        Complete structured record of geometric and probabilistic coverage metrics.
    """
    if not (0.0 < t_crit <= 1.0):
        raise ValueError(f"t_crit must be in the open-closed interval (0.0, 1.0], got {t_crit}")

    n_nodes = grid.num_nodes
    if n_nodes == 0:
        raise ValueError("Cannot evaluate coverage on an empty SamplingGrid with 0 nodes.")

    weights = np.array(grid.weights, dtype=np.float64)

    # Empty camera configuration case (baseline)
    if len(cameras) == 0:
        combined_prob = np.zeros(n_nodes, dtype=np.float64)
        binary_covered = np.zeros(n_nodes, dtype=bool)
        crit_mask = weights > 1.0
        n_crit = int(np.count_nonzero(crit_mask))
        crit_deficit = float(t_crit) if n_crit > 0 else 0.0

        return CoverageMetrics(
            num_eval_points=n_nodes,
            num_covered_points=0,
            geometric_coverage_ratio=0.0,
            geometric_coverage_percent=0.0,
            mean_probabilistic_coverage=0.0,
            risk_weighted_coverage=0.0,
            num_critical_points=n_crit,
            critical_deficit=crit_deficit,
            point_probabilities=combined_prob,
            point_binary_covered=binary_covered,
        )

    # Accumulate complement probabilities: P(miss) = PRODUCT (1 - p_j)
    prob_miss = np.ones(n_nodes, dtype=np.float64)
    # Binary geometric coverage accumulated strictly from geometric visibility masks
    binary_covered = np.zeros(n_nodes, dtype=bool)

    for cam in cameras:
        cam_geom, p_j = evaluate_camera_grid_visibility_and_probabilities(
            cam, profile, grid, floorplan, tol=tol, angular_tol=angular_tol
        )
        prob_miss *= (1.0 - p_j)
        binary_covered |= cam_geom

    # Combined detection probability: P_det = 1 - P(miss)
    combined_prob = 1.0 - prob_miss
    # Ensure numerical stability within [0.0, 1.0]
    np.clip(combined_prob, 0.0, 1.0, out=combined_prob)

    num_covered = int(np.count_nonzero(binary_covered))
    geo_ratio = float(num_covered / n_nodes)
    geo_percent = geo_ratio * 100.0
    mean_prob = float(np.mean(combined_prob))

    # Numerically stable risk-weighted coverage:
    # Scale weights by max(weights) to eliminate floating-point overflow to inf
    max_weight = float(np.max(weights))
    if max_weight <= 0.0 or not math.isfinite(max_weight):
        raise ValueError(f"Invalid maximum grid weight: {max_weight}")

    scaled_weights = weights / max_weight
    sum_scaled_weights = float(np.sum(scaled_weights))
    risk_weighted_cov = float(np.sum(scaled_weights * combined_prob) / sum_scaled_weights)

    if not math.isfinite(risk_weighted_cov):
        raise ValueError(f"Computed risk-weighted coverage is not finite: {risk_weighted_cov}")
    risk_weighted_cov = max(0.0, min(1.0, risk_weighted_cov))

    # Critical zone deficit evaluation
    crit_mask = weights > 1.0
    num_crit = int(np.count_nonzero(crit_mask))

    if num_crit > 0:
        crit_w = weights[crit_mask]
        crit_p = combined_prob[crit_mask]
        crit_shortfall = np.maximum(0.0, t_crit - crit_p)

        max_crit_w = float(np.max(crit_w))
        if max_crit_w <= 0.0 or not math.isfinite(max_crit_w):
            raise ValueError(f"Invalid maximum critical weight: {max_crit_w}")

        scaled_crit_w = crit_w / max_crit_w
        sum_scaled_crit_w = float(np.sum(scaled_crit_w))

        crit_deficit = float(np.sum(scaled_crit_w * crit_shortfall) / sum_scaled_crit_w)
        if not math.isfinite(crit_deficit):
            raise ValueError(f"Computed critical deficit is not finite: {crit_deficit}")
        crit_deficit = max(0.0, min(1.0, crit_deficit))
    else:
        crit_deficit = 0.0

    return CoverageMetrics(
        num_eval_points=n_nodes,
        num_covered_points=num_covered,
        geometric_coverage_ratio=geo_ratio,
        geometric_coverage_percent=geo_percent,
        mean_probabilistic_coverage=mean_prob,
        risk_weighted_coverage=risk_weighted_cov,
        num_critical_points=num_crit,
        critical_deficit=crit_deficit,
        point_probabilities=combined_prob,
        point_binary_covered=binary_covered,
    )
