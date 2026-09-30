import pytest

from teleoperation.config import MappingConfig
from teleoperation.mapping import map_scene_to_robot, transform_xy
from teleoperation.models import Pose


def test_transform_xy_preserves_source_order_swap_sign_then_rotation() -> None:
    config = MappingConfig(swap_xy=True, x_sign=-1, y_sign=1, rotation_degrees=90)
    x, y = transform_xy(2.0, 5.0, config)
    assert x == pytest.approx(-2.0)
    assert y == pytest.approx(-5.0)


def test_transform_rejects_invalid_sign() -> None:
    with pytest.raises(ValueError, match="x_sign"):
        transform_xy(1.0, 2.0, MappingConfig(x_sign=0))


def test_optional_output_channel_swaps() -> None:
    pose = Pose(x=1, y=2, z=3, r=4, p=5, w=6, g=7)
    mapped = map_scene_to_robot(pose, MappingConfig(swap_yz=True, swap_rw=True))
    assert mapped == Pose(x=1, y=3, z=2, r=6, p=5, w=4, g=7)
