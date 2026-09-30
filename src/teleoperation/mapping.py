from __future__ import annotations

import math

from .config import MappingConfig
from .models import Pose


def transform_xy(x: float, y: float, config: MappingConfig) -> tuple[float, float]:
    """Apply the source project's swap → signs → rotation sequence."""
    if config.swap_xy:
        x, y = y, x

    x *= _validated_sign(config.x_sign, "x_sign")
    y *= _validated_sign(config.y_sign, "y_sign")

    angle = math.radians(config.rotation_degrees)
    cosine, sine = math.cos(angle), math.sin(angle)
    return x * cosine - y * sine, x * sine + y * cosine


def map_planar_axes(pose: Pose, config: MappingConfig) -> Pose:
    x, y = transform_xy(pose.x, pose.y, config)
    return pose.updated(x=x, y=y)


def map_scene_to_robot(pose: Pose, config: MappingConfig) -> Pose:
    """Apply optional public-demo Y/Z and R/W channel swaps."""
    y, z = (pose.z, pose.y) if config.swap_yz else (pose.y, pose.z)
    r, w = (pose.w, pose.r) if config.swap_rw else (pose.r, pose.w)
    return pose.updated(y=y, z=z, r=r, w=w)


def _validated_sign(value: int, name: str) -> int:
    if value not in (-1, 1):
        raise ValueError(f"{name} must be -1 or 1")
    return value
