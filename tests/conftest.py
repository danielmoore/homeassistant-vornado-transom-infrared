from typing import Any

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared import EMITTER_ENTITY_ID
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity

from custom_components.vornado_transom_infrared.codes import Key, MultiPressCommand
from custom_components.vornado_transom_infrared.const import DOMAIN


def registry_id(hass: HomeAssistant) -> str:
    registry_entry = er.async_get(hass).async_get(EMITTER_ENTITY_ID)
    assert registry_entry is not None
    return registry_entry.id


async def setup_entry(
    hass: HomeAssistant,
    options: dict[str, Any] | None = None,
    *,
    hass_storage: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    assumed: dict[str, Any] | None = None,
) -> MockConfigEntry:
    """Set up the integration, restoring `state` (and `assumed`, default `state`)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Fan",
        data={"infrared_entity_registry_id": registry_id(hass)},
        options=options or {},
    )
    entry.add_to_hass(hass)
    if state is not None:
        assert hass_storage is not None
        hass_storage[f"{DOMAIN}.{entry.entry_id}"] = {
            "version": 1,
            "key": f"{DOMAIN}.{entry.entry_id}",
            "data": {"target": state, "assumed": assumed or state},
        }
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def state_of(hass: HomeAssistant, entity_id: str) -> State:
    state = hass.states.get(entity_id)
    assert state is not None
    return state


async def call(
    hass: HomeAssistant, domain: str, service: str, entity_id: str, **data: object
) -> None:
    await hass.services.async_call(
        domain, service, {ATTR_ENTITY_ID: entity_id, **data}, blocking=True
    )


def sent(emitter: MockInfraredEmitterEntity) -> list[list[Key]]:
    """Keys of each payload sent through the emitter."""
    payloads = []
    for command in emitter.send_command_calls:
        assert isinstance(command, MultiPressCommand)
        payloads.append([Key(press.control_word) for press in command.presses])
    return payloads
