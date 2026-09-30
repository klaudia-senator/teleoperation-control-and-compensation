from __future__ import annotations

from .config import CompensationConfig
from .models import CompensationOrigin, Pose


def planar_offsets(pose: Pose, origin: CompensationOrigin) -> tuple[float, float]:
    return pose.x - origin.x, pose.y - origin.y


def compensate_z(
    pose: Pose,
    origin: CompensationOrigin,
    config: CompensationConfig,
) -> Pose:
    """Correct Z for a planar tilt using transformed X/Y coordinates."""
    if not config.z_enabled:
        return pose
    dx, dy = planar_offsets(pose, origin)
    correction = _sign(config.z_sign, "z_sign") * (config.z_kx * dx + config.z_ky * dy)
    return pose.updated(z=pose.z + correction)


def compensate_robot_r(
    robot_pose: Pose,
    planar_pose: Pose,
    origin: CompensationOrigin,
    config: CompensationConfig,
) -> Pose:
    """Correct the outgoing R channel after optional R/W mapping."""
    if not config.r_enabled:
        return robot_pose
    dx, dy = planar_offsets(planar_pose, origin)
    correction = _sign(config.r_sign, "r_sign") * (config.r_kx * dx + config.r_ky * dy)
    return robot_pose.updated(r=robot_pose.r + correction)


def _sign(value: int, name: str) -> int:
    if value not in (-1, 1):
        raise ValueError(f"{name} must be -1 or 1")
    return value
