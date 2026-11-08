from abc import abstractmethod
from typing import override

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from .device import Device


class TransomEntity(Entity):
    """Base for entities of the fan; they refresh when the executor's state changes."""

    _attr_has_entity_name = True

    def __init__(self, device: Device, unique_id: str) -> None:
        self._executor = device.executor
        self._attr_unique_id = unique_id
        self._attr_device_info = device.device_info
        self._update()

    @abstractmethod
    def _update(self) -> None:
        """Copy the executor's state into the entity's _attr_* fields."""

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._executor.add_listener(self._handle_change))

    @callback
    def _handle_change(self) -> None:
        self._update()
        self.async_write_ha_state()


class TransomEmitterEntity(TransomEntity, InfraredEmitterConsumerEntity):
    """Entity that is unavailable while the infrared emitter is."""

    def __init__(self, device: Device, unique_id: str) -> None:
        self._infrared_emitter_entity_id = device.emitter_entity_id
        super().__init__(device, unique_id)
