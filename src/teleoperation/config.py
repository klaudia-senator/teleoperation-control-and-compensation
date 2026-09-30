from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class NetworkConfig:
    """Local simulator defaults; no deployment addresses are included."""

    host: str = "127.0.0.1"
    port: int = 8765
    timeout_seconds: float = 1.0


@dataclass(slots=True)
class MappingConfig:
    swap_xy: bool = False
    x_sign: int = 1
    y_sign: int = 1
    rotation_degrees: float = 0.0
    swap_yz: bool = False
    swap_rw: bool = False


@dataclass(slots=True)
class CompensationConfig:
    z_enabled: bool = False
    z_kx: float = 0.0
    z_ky: float = 0.0
    z_sign: int = -1
    r_enabled: bool = False
    r_kx: float = 0.0
    r_ky: float = 0.0
    r_sign: int = 1


@dataclass(slots=True)
class SafetyConfig:
    """Synthetic demonstration limits, unrelated to any physical robot."""

    enabled: bool = True
    x_min: float = -500.0
    x_max: float = 500.0
    y_min: float = -400.0
    y_max: float = 400.0
    fixed_z_enabled: bool = False
    fixed_z: float = 250.0


@dataclass(slots=True)
class AppConfig:
    network: NetworkConfig = field(default_factory=NetworkConfig)
    mapping: MappingConfig = field(default_factory=MappingConfig)
    compensation: CompensationConfig = field(default_factory=CompensationConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
