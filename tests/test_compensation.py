import pytest

from teleoperation.compensation import compensate_robot_r, compensate_z
from teleoperation.config import CompensationConfig
from teleoperation.models import CompensationOrigin, Pose


def test_z_tilt_compensation_uses_both_planar_offsets() -> None:
    config = CompensationConfig(z_enabled=True, z_kx=0.5, z_ky=0.25, z_sign=-1)
    pose = Pose(x=14, y=28, z=100)
    result = compensate_z(pose, CompensationOrigin(x=10, y=20), config)
    assert result.z == pytest.approx(96.0)
    assert pose.z == 100  # pure function: input is unchanged


def test_r_compensation_targets_outgoing_r_channel() -> None:
    config = CompensationConfig(r_enabled=True, r_kx=0.1, r_ky=0.2, r_sign=1)
    planar = Pose(x=5, y=10)
    robot = Pose(r=30)
    result = compensate_robot_r(robot, planar, CompensationOrigin(), config)
    assert result.r == pytest.approx(32.5)


def test_disabled_compensation_is_identity() -> None:
    pose = Pose(x=1, y=2, z=3)
    assert compensate_z(pose, CompensationOrigin(), CompensationConfig()) is pose
