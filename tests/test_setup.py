from typing import Any

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared import EMITTER_ENTITY_ID
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity

from custom_components.vornado_transom_infrared.const import DOMAIN
from custom_components.vornado_transom_infrared.state import Direction, FanState

from .conftest import registry_id, setup_entry

ON_STATE = {
    "power": True,
    "speed": 3,
    "direction": "exhaust",
    "auto": True,
    "setpoint": 72,
}
ASSUMED_STATE = {
    "power": True,
    "speed": 2,
    "direction": "direct",
    "auto": False,
    "setpoint": 80,
}


async def test_setup_and_unload(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    entry = await setup_entry(hass)

    assert entry.state is ConfigEntryState.LOADED
    device = entry.runtime_data
    assert device.emitter_entity_id == EMITTER_ENTITY_ID
    assert device.device_info["identifiers"] == {(DOMAIN, entry.entry_id)}
    assert device.device_info["manufacturer"] == "Vornado"
    assert device.device_info["model"] == "Transom"
    assert device.executor.target == FanState()
    assert device.executor.status.state == FanState()
    assert device.executor.frames_per_press == 5
    assert device.executor.max_timings == 288
    assert device.executor.throttle_interval == 5

    await hass.config_entries.async_unload(entry.entry_id)

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_when_emitter_missing(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, data={"infrared_entity_registry_id": "missing"}
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_options_are_applied(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    entry = await setup_entry(
        hass,
        {"frames_per_press": 3, "max_timings_per_payload": 200, "throttle_interval": 8},
    )

    executor = entry.runtime_data.executor
    assert executor.frames_per_press == 3
    assert executor.max_timings == 200
    assert executor.throttle_interval == 8


async def test_options_change_reloads(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    entry = await setup_entry(hass)
    before = entry.runtime_data

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"], {"throttle_interval": 9}
    )
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not before
    assert entry.runtime_data.executor.throttle_interval == 9


async def test_emitter_rename_reloads(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    entry = await setup_entry(hass)

    er.async_get(hass).async_update_entity(
        EMITTER_ENTITY_ID, new_entity_id="infrared.renamed_emitter"
    )
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.emitter_entity_id == "infrared.renamed_emitter"


async def test_state_restored_from_storage(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    entry = await setup_entry(
        hass, hass_storage=hass_storage, state=ON_STATE, assumed=ASSUMED_STATE
    )

    executor = entry.runtime_data.executor
    assert executor.target == FanState(
        power=True, speed=3, direction=Direction.EXHAUST, auto=True, setpoint=72
    )
    assert executor.status.state == FanState(
        power=True, speed=2, direction=Direction.DIRECT, auto=False, setpoint=80
    )


async def test_state_saved_on_unload(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    entry = await setup_entry(hass, {"throttle_interval": 60})
    executor = entry.runtime_data.executor
    executor.request(FanState(power=True))
    await executor.wait_idle()
    executor.request(FanState(power=True, speed=4, auto=True, setpoint=75))

    await hass.config_entries.async_unload(entry.entry_id)

    assert hass_storage[f"{DOMAIN}.{entry.entry_id}"]["data"] == {
        "target": {
            "power": True,
            "speed": 4,
            "direction": "direct",
            "auto": True,
            "setpoint": 75,
        },
        "assumed": {
            "power": True,
            "speed": 1,
            "direction": "direct",
            "auto": False,
            "setpoint": 60,
        },
    }


@pytest.mark.parametrize(
    "data",
    [
        {"target": {**ON_STATE, "direction": "sideways"}, "assumed": ON_STATE},
        {"target": ON_STATE, "assumed": {**ON_STATE, "speed": 9}},
        {"target": "on", "assumed": ON_STATE},
        {"target": {**ON_STATE, "power": "yes"}, "assumed": ON_STATE},
        {"assumed": ON_STATE},
    ],
)
async def test_corrupt_storage_restores_off(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    data: dict[str, Any],
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, data={"infrared_entity_registry_id": registry_id(hass)}
    )
    entry.add_to_hass(hass)
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = {
        "version": 1,
        "key": f"{DOMAIN}.{entry.entry_id}",
        "data": data,
    }

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.executor.target == FanState()
    assert entry.runtime_data.executor.status.state == FanState()


async def test_emitter_removal_retries_setup(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    entry = await setup_entry(hass)

    er.async_get(hass).async_remove(EMITTER_ENTITY_ID)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_remove_entry_deletes_storage(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    entry = await setup_entry(hass)
    await hass.config_entries.async_unload(entry.entry_id)
    assert f"{DOMAIN}.{entry.entry_id}" in hass_storage

    await hass.config_entries.async_remove(entry.entry_id)

    assert f"{DOMAIN}.{entry.entry_id}" not in hass_storage


async def test_request_sends_to_emitter(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    entry = await setup_entry(hass)
    executor = entry.runtime_data.executor

    executor.request(FanState(power=True))
    await executor.wait_idle()

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    assert executor.status.state == FanState(power=True)
