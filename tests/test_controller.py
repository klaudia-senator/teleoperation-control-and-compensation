import pytest

from teleoperation.config import AppConfig
from teleoperation.controller import TeleoperationController
from teleoperation.models import Pose
from teleoperation.protocol import decode_move


class RecordingSender:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send(self, message: str) -> None:
        self.messages.append(message)


def test_telemetry_updates_measured_but_not_commanded_pose() -> None:
    controller = TeleoperationController()
    controller.set_absolute(Pose(x=10), transmit=False)
    controller.update_measured_pose(Pose(x=8))
    assert controller.commanded_pose.x == 10
    assert controller.measured_pose.x == 8


def test_pipeline_preserves_mapping_and_compensation_order() -> None:
    config = AppConfig()
    config.safety.enabled = False
    config.mapping.swap_yz = True
    config.mapping.swap_rw = True
    config.compensation.z_enabled = True
    config.compensation.z_kx = 1.0
    config.compensation.z_sign = 1
    config.compensation.r_enabled = True
    config.compensation.r_kx = 0.5
    sender = RecordingSender()
    controller = TeleoperationController(config, sender)

    result = controller.set_absolute(Pose(x=10, y=20, z=30, r=4, p=5, w=6, g=7))

    assert result.robot_pose == Pose(x=10, y=40, z=20, r=11, p=5, w=4, g=7)
    assert decode_move(sender.messages[0]) == result.robot_pose


def test_origin_capture_is_separate_from_zero_command() -> None:
    config = AppConfig()
    config.safety.enabled = False
    config.mapping.rotation_degrees = 90
    sender = RecordingSender()
    controller = TeleoperationController(config, sender)
    controller.set_absolute(Pose(x=10), transmit=False)

    origin = controller.set_compensation_origin()

    assert origin.x == pytest.approx(0)
    assert origin.y == pytest.approx(10)
    assert sender.messages == []
    controller.send_zero_command()
    assert decode_move(sender.messages[0]) == Pose()


def test_jog_and_delta_are_relative_to_commanded_state() -> None:
    config = AppConfig()
    config.safety.enabled = False
    sender = RecordingSender()
    controller = TeleoperationController(config, sender)
    controller.set_absolute(Pose(x=1, y=2), transmit=False)
    controller.jog("x", 4)
    controller.apply_delta(y=-1, z=3)
    assert controller.commanded_pose == Pose(x=5, y=1, z=3)
