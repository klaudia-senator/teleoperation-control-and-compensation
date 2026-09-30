from teleoperation.config import SafetyConfig
from teleoperation.models import Pose
from teleoperation.safety import clamp_pose


def test_clamps_xy_and_reports_changed_axes() -> None:
    result = clamp_pose(
        Pose(x=20, y=-20, z=3),
        SafetyConfig(x_min=-10, x_max=10, y_min=-5, y_max=5),
    )
    assert result.pose == Pose(x=10, y=-5, z=3)
    assert result.clamped_axes == ("x", "y")


def test_reversed_bounds_are_normalized() -> None:
    result = clamp_pose(Pose(x=100), SafetyConfig(x_min=10, x_max=-10))
    assert result.pose.x == 10


def test_fixed_z_can_be_applied_independently() -> None:
    result = clamp_pose(
        Pose(x=1000, z=15),
        SafetyConfig(enabled=False, fixed_z_enabled=True, fixed_z=42),
    )
    assert result.pose.x == 1000
    assert result.pose.z == 42
    assert result.clamped_axes == ("z",)
