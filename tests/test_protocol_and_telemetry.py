import json

import pytest

from teleoperation.models import Pose
from teleoperation.protocol import PROTOCOL_NAME, ProtocolError, decode_move, encode_move
from teleoperation.telemetry import parse_telemetry


def test_move_protocol_round_trip() -> None:
    pose = Pose(x=1.25, y=-2.5, g=4)
    assert decode_move(encode_move(pose)) == pose


def test_rejects_messages_without_public_protocol_identifier() -> None:
    with pytest.raises(ProtocolError, match="protocol"):
        decode_move('{"type":"move","pose":{"x":1}}')


def test_partial_telemetry_merges_into_measured_pose() -> None:
    message = json.dumps({"protocol": PROTOCOL_NAME, "type": "telemetry", "pose": {"x": 9, "r": 3}})
    sample = parse_telemetry(message, Pose(y=7, z=8))
    assert sample.pose == Pose(x=9, y=7, z=8, r=3)


def test_rejects_unknown_axes() -> None:
    message = json.dumps(
        {"protocol": PROTOCOL_NAME, "type": "telemetry", "pose": {"secret_axis": 9}}
    )
    with pytest.raises(ProtocolError, match="Unknown pose axes"):
        parse_telemetry(message)
