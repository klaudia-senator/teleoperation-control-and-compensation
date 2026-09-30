from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .compensation import compensate_robot_r, compensate_z
from .config import AppConfig
from .mapping import map_planar_axes, map_scene_to_robot
from .models import AXES, CompensationOrigin, Pose
from .protocol import encode_move
from .safety import SafetyResult, clamp_pose


class Sender(Protocol):
    def send(self, message: str) -> None: ...


@dataclass(frozen=True, slots=True)
class CommandResult:
    requested_pose: Pose
    safe_scene_pose: Pose
    mapped_planar_pose: Pose
    robot_pose: Pose
    clamped_axes: tuple[str, ...]
    payload: str


class TeleoperationController:
    """Own commanded/measured state and orchestrate the pure control pipeline."""

    def __init__(self, config: AppConfig | None = None, sender: Sender | None = None) -> None:
        self.config = config or AppConfig()
        self.sender = sender
        self.commanded_pose = Pose()
        self.measured_pose = Pose()
        self.compensation_origin = CompensationOrigin()

    def set_absolute(self, pose: Pose, *, transmit: bool = True) -> CommandResult:
        self.commanded_pose = pose
        return self.build_and_maybe_send(transmit=transmit)

    def apply_delta(self, **deltas: float) -> CommandResult:
        unknown = set(deltas) - set(AXES)
        if unknown:
            raise ValueError(f"Unknown pose axes: {sorted(unknown)}")
        values = {
            axis: getattr(self.commanded_pose, axis) + float(delta)
            for axis, delta in deltas.items()
        }
        self.commanded_pose = self.commanded_pose.updated(**values)
        return self.build_and_maybe_send()

    def jog(self, axis: str, step: float) -> CommandResult:
        normalized = axis.lower()
        if normalized not in AXES:
            raise ValueError(f"Unknown pose axis: {axis}")
        return self.apply_delta(**{normalized: step})

    def update_measured_pose(self, pose: Pose) -> None:
        """Telemetry affects measured state only, never the active command."""
        self.measured_pose = pose

    def set_compensation_origin(self) -> CompensationOrigin:
        """Capture the current command in the transformed planar coordinate frame."""
        planar = map_planar_axes(self.commanded_pose, self.config.mapping)
        self.compensation_origin = CompensationOrigin(planar.x, planar.y)
        return self.compensation_origin

    def send_zero_command(self) -> CommandResult:
        """Explicit synthetic zero command, separate from origin capture."""
        return self.set_absolute(Pose())

    def build_command(self) -> CommandResult:
        safety: SafetyResult = clamp_pose(self.commanded_pose, self.config.safety)
        planar = map_planar_axes(safety.pose, self.config.mapping)
        z_compensated = compensate_z(planar, self.compensation_origin, self.config.compensation)
        robot_pose = map_scene_to_robot(z_compensated, self.config.mapping)
        robot_pose = compensate_robot_r(
            robot_pose,
            planar,
            self.compensation_origin,
            self.config.compensation,
        )
        return CommandResult(
            requested_pose=self.commanded_pose,
            safe_scene_pose=safety.pose,
            mapped_planar_pose=planar,
            robot_pose=robot_pose,
            clamped_axes=safety.clamped_axes,
            payload=encode_move(robot_pose),
        )

    def build_and_maybe_send(self, *, transmit: bool = True) -> CommandResult:
        result = self.build_command()
        if transmit:
            if self.sender is None:
                raise RuntimeError("No command transport configured")
            self.sender.send(result.payload)
        return result
