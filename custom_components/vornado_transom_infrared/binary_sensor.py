from collections.abc import Callable
from datetime import datetime
from typing import override

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .device import Device, TransomConfigEntry
from .entity import TransomEntity


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
            AssumedBinarySensor(
                device,
                f"{prefix}_assumed_power",
                "assumed_power",
                lambda: executor.status.state.power,
            ),
            AssumedIdleSensor(device, f"{prefix}_assumed_idle"),
        ]
    )


class AssumedBinarySensor(TransomEntity, BinarySensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        device: Device,
        unique_id: str,
        translation_key: str,
        value: Callable[[], bool],
    ) -> None:
        self._value = value
        super().__init__(device, unique_id)
        self._attr_translation_key = translation_key

    @override
    def _update(self) -> None:
        self._attr_is_on = self._value()


class AssumedIdleSensor(TransomEntity, BinarySensorEntity):
    """On when the unit is assumed idle, so the next command needs a wake press."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "assumed_idle"

    def __init__(self, device: Device, unique_id: str) -> None:
        self._cancel_timer: CALLBACK_TYPE | None = None
        super().__init__(device, unique_id)

    @override
    def _update(self) -> None:
        self._attr_is_on = self._executor.clock() >= self._executor.status.idle_at

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._cancel)
        self.async_on_remove(self._executor.add_listener(self._schedule_refresh))
        self._schedule_refresh()

    def _cancel(self) -> None:
        if self._cancel_timer is not None:
            self._cancel_timer()
            self._cancel_timer = None

    @callback
    def _refresh(self, _now: datetime) -> None:
        self._handle_change()

    @callback
    def _schedule_refresh(self) -> None:
        self._cancel()
        remaining = self._executor.status.idle_at - self._executor.clock()
        if remaining > 0:
            self._cancel_timer = async_call_later(self.hass, remaining, self._refresh)
