from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

MIN_SPEED = 1
MAX_SPEED = 4
MIN_SETPOINT = 60
MAX_SETPOINT = 90


class Direction(StrEnum):
    DIRECT = "direct"
    EXHAUST = "exhaust"


class Mode(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"


@dataclass(frozen=True)
class FanState:
    """Fan settings."""

    power: bool = False
    speed: int = MIN_SPEED
    direction: Direction = Direction.DIRECT
    auto: bool = False
    setpoint: int = MIN_SETPOINT

    def __post_init__(self) -> None:
        if not MIN_SPEED <= self.speed <= MAX_SPEED:
            raise ValueError(f"speed out of range: {self.speed}")
        if not MIN_SETPOINT <= self.setpoint <= MAX_SETPOINT:
            raise ValueError(f"setpoint out of range: {self.setpoint}")

    @property
    def mode(self) -> Mode:
        return Mode.AUTO if self.auto else Mode.MANUAL

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FanState":
        if not isinstance(data["power"], bool) or not isinstance(data["auto"], bool):
            raise TypeError("power and auto must be booleans")
        return cls(
            power=data["power"],
            speed=data["speed"],
            direction=Direction(data["direction"]),
            auto=data["auto"],
            setpoint=data["setpoint"],
        )


@dataclass(frozen=True)
class UnitStatus:
    """Assumed unit state and when it is assumed to go idle.

    Times are float seconds from an injected clock.
    """

    state: FanState
    idle_at: float = 0.0
