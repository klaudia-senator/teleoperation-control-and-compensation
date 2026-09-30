from __future__ import annotations

from dataclasses import dataclass

from .models import Pose
from .protocol import ProtocolError, decode_message


@dataclass(frozen=True, slots=True)
class TelemetrySample:
    pose: Pose
    raw_line: str


def parse_telemetry(line: str, previous: Pose | None = None) -> TelemetrySample:
    """Parse synthetic telemetry and merge partial samples into measured state."""
    message = decode_message(line, expected_type="telemetry")
    pose = (previous or Pose()).merged(message["pose"])
    return TelemetrySample(pose=pose, raw_line=line.rstrip("\r\n"))


__all__ = ["ProtocolError", "TelemetrySample", "parse_telemetry"]
