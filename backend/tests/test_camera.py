"""Unit tests for CameraPose, CameraProfile, and circular angle normalization."""

import math
import pytest

from camera_optimizer.camera.pose import CameraPose, wrap_pi
from camera_optimizer.camera.profile import CameraProfile
from camera_optimizer.geometry.point import Point2D


# ---------------------------------------------------------------------------
# wrap_pi Tests
# ---------------------------------------------------------------------------


def test_wrap_pi_standard_angles() -> None:
    assert wrap_pi(0.0) == pytest.approx(0.0)
    assert wrap_pi(math.pi / 2.0) == pytest.approx(math.pi / 2.0)
    assert wrap_pi(-math.pi / 2.0) == pytest.approx(-math.pi / 2.0)


def test_wrap_pi_boundary_conditions() -> None:
    # Exact +pi wraps to -pi by [-pi, pi) convention
    assert wrap_pi(math.pi) == pytest.approx(-math.pi)
    assert wrap_pi(-math.pi) == pytest.approx(-math.pi)
    # Multiples of 2*pi
    assert wrap_pi(2.0 * math.pi) == pytest.approx(0.0)
    assert wrap_pi(-2.0 * math.pi) == pytest.approx(0.0)
    assert wrap_pi(3.0 * math.pi) == pytest.approx(-math.pi)
    # Near boundaries
    assert wrap_pi(math.pi - 1e-6) == pytest.approx(math.pi - 1e-6)
    assert wrap_pi(-math.pi + 1e-6) == pytest.approx(-math.pi + 1e-6)


def test_wrap_pi_rejects_non_finite() -> None:
    with pytest.raises(ValueError, match="finite real number"):
        wrap_pi(float("nan"))
    with pytest.raises(ValueError, match="finite real number"):
        wrap_pi(float("inf"))
    with pytest.raises(ValueError, match="finite real number"):
        wrap_pi(float("-inf"))


# ---------------------------------------------------------------------------
# CameraPose Tests
# ---------------------------------------------------------------------------


def test_camera_pose_creation_and_normalization() -> None:
    cam = CameraPose(5.0, 5.0, 3.0 * math.pi)
    assert cam.x == pytest.approx(5.0)
    assert cam.y == pytest.approx(5.0)
    # 3*pi wraps to -pi
    assert cam.theta == pytest.approx(-math.pi)
    assert cam.point == Point2D(5.0, 5.0)
    assert cam.as_tuple() == (5.0, 5.0, pytest.approx(-math.pi))


def test_camera_pose_distance_and_angles() -> None:
    cam = CameraPose(0.0, 0.0, 0.0)  # Facing +X
    target = Point2D(3.0, 4.0)
    assert cam.distance_to(target) == pytest.approx(5.0)
    expected_phi = math.atan2(4.0, 3.0)
    assert cam.angle_to(target) == pytest.approx(expected_phi)
    assert cam.angular_deviation_to(target) == pytest.approx(expected_phi)

    # When camera is rotated towards +Y (theta = pi/2)
    cam_y = CameraPose(0.0, 0.0, math.pi / 2.0)
    # Deviation should be phi - pi/2
    assert cam_y.angular_deviation_to(target) == pytest.approx(expected_phi - math.pi / 2.0)


def test_camera_pose_rejects_non_finite_and_invalid_types() -> None:
    with pytest.raises(ValueError, match="finite"):
        CameraPose(float("nan"), 0.0, 0.0)
    with pytest.raises(ValueError, match="finite"):
        CameraPose(0.0, float("inf"), 0.0)
    with pytest.raises(ValueError, match="finite"):
        CameraPose(0.0, 0.0, float("-inf"))
    with pytest.raises(TypeError):
        CameraPose("invalid", 0.0, 0.0)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# CameraProfile Tests & OPT-12 (Validation)
# ---------------------------------------------------------------------------


def test_camera_profile_default_and_properties() -> None:
    prof = CameraProfile()
    assert prof.Rmin == pytest.approx(0.0)
    assert prof.Rmax == pytest.approx(10.0)
    assert prof.fov == pytest.approx(math.pi / 2.0)
    assert prof.half_fov == pytest.approx(math.pi / 4.0)
    assert prof.range_span == pytest.approx(10.0)
    assert prof.p0 == pytest.approx(1.0)
    assert prof.beta_d == pytest.approx(0.5)
    assert prof.beta_theta == pytest.approx(0.5)


def test_opt_12_parameter_validation() -> None:
    """OPT-12: Reject Rmax <= Rmin, invalid angular apertures, non-finite parameters,
    and values outside allowed intervals.
    """
    # Rmax <= Rmin
    with pytest.raises(ValueError, match="strictly greater than Rmin"):
        CameraProfile(Rmin=5.0, Rmax=5.0)
    with pytest.raises(ValueError, match="strictly greater than Rmin"):
        CameraProfile(Rmin=5.0, Rmax=4.0)

    # Negative Rmin
    with pytest.raises(ValueError, match="Rmin must be non-negative"):
        CameraProfile(Rmin=-1.0, Rmax=10.0)

    # Invalid FOV (must be in (0, 2*pi])
    with pytest.raises(ValueError, match="fov must be in the open-closed interval"):
        CameraProfile(fov=0.0)
    with pytest.raises(ValueError, match="fov must be in the open-closed interval"):
        CameraProfile(fov=-0.5)
    with pytest.raises(ValueError, match="fov must be in the open-closed interval"):
        CameraProfile(fov=2.0 * math.pi + 0.1)

    # Invalid p0 (must be in (0, 1.0])
    with pytest.raises(ValueError, match="p0 must be in the open-closed interval"):
        CameraProfile(p0=0.0)
    with pytest.raises(ValueError, match="p0 must be in the open-closed interval"):
        CameraProfile(p0=-0.1)
    with pytest.raises(ValueError, match="p0 must be in the open-closed interval"):
        CameraProfile(p0=1.05)

    # Negative attenuation coefficients
    with pytest.raises(ValueError, match="beta_d must be non-negative"):
        CameraProfile(beta_d=-0.1)
    with pytest.raises(ValueError, match="beta_theta must be non-negative"):
        CameraProfile(beta_theta=-0.1)

    # Non-finite values
    with pytest.raises(ValueError, match="finite"):
        CameraProfile(Rmax=float("inf"))
    with pytest.raises(ValueError, match="finite"):
        CameraProfile(p0=float("nan"))

    # Invalid types
    with pytest.raises(TypeError, match="must be a number"):
        CameraProfile(Rmax="ten")  # type: ignore[arg-type]
