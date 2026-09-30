from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

AXES = ("x", "y", "z", "r", "p", "w", "g")


@dataclass(frozen=True, slots=True)
class Pose:
    """Seven-axis pose used by the public demo.

    X/Y/Z are linear axes, R/P/W are orientation axes, and G is a generic
    gripper axis. Units are millimetres and degrees in the sample config.
    """

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    r: float = 0.0
    p: float = 0.0
    w: float = 0.0
    g: float = 0.0

    def updated(self, **changes: float) -> Pose:
        unknown = set(changes) - set(AXES)
        if unknown:
            raise ValueError(f"Unknown pose axes: {sorted(unknown)}")
        return replace(self, **{key: float(value) for key, value in changes.items()})

    def merged(self, values: Mapping[str, float]) -> Pose:
        """Return a copy with only the supplied axes updated."""
        return self.updated(**{key.lower(): value for key, value in values.items()})

    def as_dict(self) -> dict[str, float]:
        return {axis: getattr(self, axis) for axis in AXES}


@dataclass(frozen=True, slots=True)
class CompensationOrigin:
    x: float = 0.0
    y: float = 0.0
