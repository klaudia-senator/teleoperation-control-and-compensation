from __future__ import annotations

from dataclasses import dataclass

from .config import SafetyConfig
from .models import Pose


@dataclass(frozen=True, slots=True)
class SafetyResult:
    pose: Pose
    clamped_axes: tuple[str, ...]


def clamp_pose(pose: Pose, config: SafetyConfig) -> SafetyResult:
    """Apply scene-space limits without mutating the caller's pose."""
    x_min, x_max = sorted((config.x_min, config.x_max))
    y_min, y_max = sorted((config.y_min, config.y_max))
    changes: dict[str, float] = {}

    if config.enabled:
        changes["x"] = min(x_max, max(x_min, pose.x))
        changes["y"] = min(y_max, max(y_min, pose.y))
    if config.fixed_z_enabled:
        changes["z"] = config.fixed_z

    safe_pose = pose.updated(**changes)
    clamped = tuple(axis for axis in changes if getattr(pose, axis) != getattr(safe_pose, axis))
    return SafetyResult(safe_pose, clamped)
