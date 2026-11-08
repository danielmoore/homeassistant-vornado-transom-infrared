from dataclasses import replace
from typing import override

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .device import TransomConfigEntry
from .entity import TransomEmitterEntity
from .state import Mode


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TransomConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([ModeSelect(entry.runtime_data, f"{entry.entry_id}_auto")])


class ModeSelect(TransomEmitterEntity, SelectEntity):
    _attr_translation_key = "mode"
    _attr_options = [mode.value for mode in Mode]
    _attr_assumed_state = True

    @override
    def _update(self) -> None:
        self._attr_current_option = self._executor.target.mode

    @override
    async def async_select_option(self, option: str) -> None:
        self._executor.request(replace(self._executor.target, auto=option == Mode.AUTO))
