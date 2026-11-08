from collections.abc import Callable
from typing import override

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .device import Device, TransomConfigEntry
from .entity import TransomEntity
from .state import Direction, Mode


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TransomConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    device = entry.runtime_data
    executor = device.executor
    prefix = entry.entry_id
    async_add_entities(
        [
            AssumedSensor(
                device,
                f"{prefix}_assumed_speed",
                "assumed_speed",
                lambda: executor.status.state.speed,
            ),
            AssumedSensor(
                device,
                f"{prefix}_assumed_direction",
                "assumed_direction",
                lambda: executor.status.state.direction,
                device_class=SensorDeviceClass.ENUM,
                options=[direction.value for direction in Direction],
            ),
            AssumedSensor(
                device,
                f"{prefix}_assumed_mode",
                "assumed_mode",
                lambda: executor.status.state.mode,
                device_class=SensorDeviceClass.ENUM,
                options=[mode.value for mode in Mode],
            ),
            AssumedSensor(
                device,
                f"{prefix}_assumed_setpoint",
                "assumed_setpoint",
                lambda: executor.status.state.setpoint,
                unit=UnitOfTemperature.FAHRENHEIT,
            ),
            LastCommandSensor(device, f"{prefix}_last_command"),
        ]
    )


class AssumedSensor(TransomEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        device: Device,
        unique_id: str,
        translation_key: str,
        value: Callable[[], int | str],
        *,
        device_class: SensorDeviceClass | None = None,
        options: list[str] | None = None,
        unit: str | None = None,
    ) -> None:
        self._value = value
        super().__init__(device, unique_id)
        self._attr_translation_key = translation_key
        self._attr_device_class = device_class
        self._attr_options = options
        self._attr_native_unit_of_measurement = unit

    @override
    def _update(self) -> None:
        self._attr_native_value = self._value()


class LastCommandSensor(TransomEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "last_command"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @override
    def _update(self) -> None:
        self._attr_native_value = self._executor.last_command_time
