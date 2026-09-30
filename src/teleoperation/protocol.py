from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .models import AXES, Pose

PROTOCOL_NAME = "teleop-demo-v1"


class ProtocolError(ValueError):
    pass


def encode_move(pose: Pose) -> str:
    """Encode a synthetic newline-delimited JSON movement command."""
    message = {"protocol": PROTOCOL_NAME, "type": "move", "pose": pose.as_dict()}
    return json.dumps(message, separators=(",", ":"), sort_keys=True) + "\n"


def encode_telemetry(pose: Pose) -> str:
    message = {"protocol": PROTOCOL_NAME, "type": "telemetry", "pose": pose.as_dict()}
    return json.dumps(message, separators=(",", ":"), sort_keys=True) + "\n"


def decode_message(line: str, *, expected_type: str | None = None) -> dict[str, Any]:
    try:
        message = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"Invalid JSON: {exc.msg}") from exc

    if not isinstance(message, dict) or message.get("protocol") != PROTOCOL_NAME:
        raise ProtocolError("Unsupported or missing synthetic protocol identifier")
    if message.get("type") not in {"move", "telemetry"}:
        raise ProtocolError("Unsupported message type")
    if expected_type is not None and message["type"] != expected_type:
        raise ProtocolError(f"Expected {expected_type!r}, received {message['type']!r}")
    message["pose"] = _validated_pose_values(message.get("pose"))
    return message


def decode_move(line: str) -> Pose:
    return Pose(**decode_message(line, expected_type="move")["pose"])


def _validated_pose_values(raw: object) -> dict[str, float]:
    if not isinstance(raw, Mapping):
        raise ProtocolError("Pose must be an object")
    unknown = set(raw) - set(AXES)
    if unknown:
        raise ProtocolError(f"Unknown pose axes: {sorted(unknown)}")
    values: dict[str, float] = {}
    for key, value in raw.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ProtocolError(f"Pose axis {key!r} must be numeric")
        values[key] = float(value)
    return values
