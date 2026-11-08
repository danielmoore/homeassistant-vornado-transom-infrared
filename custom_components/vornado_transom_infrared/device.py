from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .executor import Executor


@dataclass(frozen=True)
class Device:
    """What a config entry's entities share."""

    executor: Executor
    emitter_entity_id: str
    device_info: DeviceInfo


type TransomConfigEntry = ConfigEntry[Device]
