from dataclasses import replace
from typing import override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .device import TransomConfigEntry
from .entity import TransomEmitterEntity
from .state import MAX_SETPOINT, MIN_SETPOINT


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TransomConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        [SetpointNumber(entry.runtime_data, f"{entry.entry_id}_setpoint")]
    )


class SetpointNumber(TransomEmitterEntity, NumberEntity):
    _attr_translation_key = "setpoint"
    _attr_assumed_state = True
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_native_min_value = MIN_SETPOINT
    _attr_native_max_value = MAX_SETPOINT
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    @override
    def _update(self) -> None:
        self._attr_native_value = self._executor.target.setpoint

    @override
    async def async_set_native_value(self, value: float) -> None:
        self._executor.request(replace(self._executor.target, setpoint=round(value)))
