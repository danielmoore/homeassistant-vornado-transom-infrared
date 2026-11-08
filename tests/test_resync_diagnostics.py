import logging
from datetime import timedelta
from typing import Any

import probatio
import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant.components.infrared import EMITTER_ENTITY_ID
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity

from custom_components.vornado_transom_infrared.const import DOMAIN
from custom_components.vornado_transom_infrared.state import Direction, FanState

from .conftest import setup_entry, state_of

FAN = "fan.fan"

START = {
    "power": True,
    "speed": 2,
    "direction": "direct",
    "auto": False,
    "setpoint": 70,
}


async def _setup_with(
    hass: HomeAssistant, hass_storage: dict[str, Any], throttle: int = 0
) -> MockConfigEntry:
    return await setup_entry(
        hass, {"throttle_interval": throttle}, hass_storage=hass_storage, state=START
    )


async def _resync(hass: HomeAssistant, entity_id: Any = FAN, **fields: Any) -> None:
    await hass.services.async_call(
        DOMAIN,
        "set_assumed_state",
        {ATTR_ENTITY_ID: entity_id, **fields},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_resync_sets_target_and_assumed_without_sending(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    entry = await _setup_with(hass, hass_storage)

    await _resync(
        hass, power=False, speed=4, direction="exhaust", auto=True, setpoint=85
    )

    executor = entry.runtime_data.executor
    expected = FanState(
        power=False, speed=4, direction=Direction.EXHAUST, auto=True, setpoint=85
    )
    assert executor.target == expected
    assert executor.status.state == expected
    assert mock_infrared_emitter_entity.send_command_calls == []


async def test_resync_keeps_unspecified_fields(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    entry = await _setup_with(hass, hass_storage)

    await _resync(hass, speed=3)

    executor = entry.runtime_data.executor
    expected = FanState(
        power=True, speed=3, direction=Direction.DIRECT, auto=False, setpoint=70
    )
    assert executor.target == expected
    assert executor.status.state == expected


@pytest.mark.parametrize(
    "fields",
    [
        {"speed": 0},
        {"speed": 5},
        {"speed": 2.5},
        {"speed": "2"},
        {"setpoint": 70.5},
        {"setpoint": 59},
        {"setpoint": 91},
        {"direction": "sideways"},
        {"power": "maybe"},
    ],
)
async def test_resync_rejects_invalid_fields(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    fields: dict[str, Any],
) -> None:
    entry = await _setup_with(hass, hass_storage)

    with pytest.raises(probatio.Invalid):
        await _resync(hass, **fields)

    assert entry.runtime_data.executor.status.state == FanState(
        power=True, speed=2, setpoint=70
    )


async def test_resync_unknown_entity_changes_nothing(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    entry = await _setup_with(hass, hass_storage)

    await _resync(hass, "fan.missing", speed=3)

    assert entry.runtime_data.executor.status.state == FanState(
        power=True, speed=2, setpoint=70
    )


async def test_resync_ignores_entities_of_other_integrations(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    entry = await _setup_with(hass, hass_storage)

    await _resync(hass, [FAN, EMITTER_ENTITY_ID], speed=3)

    assert entry.runtime_data.executor.status.state == FanState(
        power=True, speed=3, setpoint=70
    )


async def test_resync_unloaded_entry(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    entry = await _setup_with(hass, hass_storage)
    await hass.config_entries.async_unload(entry.entry_id)

    with pytest.raises(ServiceValidationError, match="is not loaded"):
        await _resync(hass, speed=3)


async def test_diagnostic_entities_show_assumed_state(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    await _setup_with(hass, hass_storage)

    assert state_of(hass, "binary_sensor.fan_assumed_power").state == "on"
    assert state_of(hass, "sensor.fan_assumed_speed").state == "2"
    assert state_of(hass, "sensor.fan_assumed_direction").state == "direct"
    assert state_of(hass, "sensor.fan_assumed_mode").state == "manual"
    assert state_of(hass, "sensor.fan_assumed_setpoint").state == "70"
    assert state_of(hass, "binary_sensor.fan_assumed_idle").state == "on"
    assert state_of(hass, "sensor.fan_last_command").state == "unknown"

    await _resync(
        hass, power=False, speed=4, direction="exhaust", auto=True, setpoint=85
    )

    assert state_of(hass, "binary_sensor.fan_assumed_power").state == "off"
    assert state_of(hass, "sensor.fan_assumed_speed").state == "4"
    assert state_of(hass, "sensor.fan_assumed_direction").state == "exhaust"
    assert state_of(hass, "sensor.fan_assumed_mode").state == "auto"
    assert state_of(hass, "sensor.fan_assumed_setpoint").state == "85"
    assert state_of(hass, "sensor.fan_last_command").state == "unknown"


async def test_diagnostic_entities_stay_available_without_emitter(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    await _setup_with(hass, hass_storage)

    hass.states.async_set(EMITTER_ENTITY_ID, STATE_UNAVAILABLE)
    await _resync(hass, speed=4)

    assert state_of(hass, "sensor.fan_assumed_speed").state == "4"
    assert state_of(hass, "binary_sensor.fan_assumed_power").state == "on"
    assert state_of(hass, "binary_sensor.fan_assumed_idle").state == "on"
    assert state_of(hass, "sensor.fan_last_command").state == "unknown"
    assert state_of(hass, "fan.fan").state == STATE_UNAVAILABLE


async def test_diagnostics_follow_a_send(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to("2026-11-07T12:00:00+00:00")
    entry = await _setup_with(hass, hass_storage)
    executor = entry.runtime_data.executor
    executor.request(FanState(power=True, speed=3, setpoint=70))
    await executor.wait_idle()
    await hass.async_block_till_done()

    assert state_of(hass, "sensor.fan_assumed_speed").state == "3"
    assert (
        state_of(hass, "sensor.fan_last_command").state == "2026-11-07T12:00:00+00:00"
    )
    assert state_of(hass, "binary_sensor.fan_assumed_idle").state == "off"


async def test_last_command_time_ignores_later_changes(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to("2026-11-07T12:00:00+00:00")
    entry = await _setup_with(hass, hass_storage)
    executor = entry.runtime_data.executor
    executor.request(FanState(power=True, speed=3, setpoint=70))
    await executor.wait_idle()
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=90))
    await _resync(hass, speed=4)

    assert (
        state_of(hass, "sensor.fan_last_command").state == "2026-11-07T12:00:00+00:00"
    )


async def test_assumed_idle_turns_on_after_idle_at(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    entry = await _setup_with(hass, hass_storage)
    executor = entry.runtime_data.executor
    executor.request(FanState(power=True, speed=3, setpoint=70))
    await executor.wait_idle()
    await hass.async_block_till_done()
    assert state_of(hass, "binary_sensor.fan_assumed_idle").state == "off"

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert state_of(hass, "binary_sensor.fan_assumed_idle").state == "on"


async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: Any,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    entry = await _setup_with(hass, hass_storage, throttle=7)
    await _resync(hass, speed=4)
    executor = entry.runtime_data.executor
    executor.request(FanState(power=True, speed=1, setpoint=70))
    await executor.wait_idle()

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert isinstance(result.pop("last_command_time"), str)
    assert result == {
        "options": {"throttle_interval": 7},
        "target": {
            "power": True,
            "speed": 1,
            "direction": "direct",
            "auto": False,
            "setpoint": 70,
        },
        "assumed": {
            "power": True,
            "speed": 1,
            "direction": "direct",
            "auto": False,
            "setpoint": 70,
        },
        "assumed_idle": False,
    }


async def test_resync_cancels_a_send_waiting_on_the_throttle(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    entry = await _setup_with(hass, hass_storage, throttle=3600)
    executor = entry.runtime_data.executor
    executor.request(FanState(power=True, speed=3, setpoint=70))
    await executor.wait_idle()
    assert len(mock_infrared_emitter_entity.send_command_calls) == 1

    executor.request(FanState(power=True, speed=4, setpoint=70))
    await _resync(hass, speed=1)
    await executor.wait_idle()
    await hass.async_block_till_done()

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    assert state_of(hass, "fan.fan").attributes["percentage"] == 25


async def test_unload_cancels_the_idle_timer(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    entry = await _setup_with(hass, hass_storage)
    executor = entry.runtime_data.executor
    executor.request(FanState(power=True, speed=3, setpoint=70))
    await executor.wait_idle()
    await hass.async_block_till_done()
    assert state_of(hass, "binary_sensor.fan_assumed_idle").state == "off"

    await hass.config_entries.async_unload(entry.entry_id)
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert state_of(hass, "binary_sensor.fan_assumed_idle").state == "unavailable"
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
