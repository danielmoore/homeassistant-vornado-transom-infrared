from typing import Any

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_PERCENTAGE,
    SERVICE_SET_DIRECTION,
    SERVICE_SET_PERCENTAGE,
)
from homeassistant.components.fan import (
    DOMAIN as FAN_DOMAIN,
)
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.number import SERVICE_SET_VALUE
from homeassistant.components.select import ATTR_OPTION, SERVICE_SELECT_OPTION
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
from pytest_homeassistant.components.infrared import EMITTER_ENTITY_ID
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity

from custom_components.vornado_transom_infrared.codes import Key
from custom_components.vornado_transom_infrared.state import Direction, FanState

from .conftest import call, sent, setup_entry, state_of

FAN = "fan.fan"

RUNNING = {
    "power": True,
    "speed": 2,
    "direction": "direct",
    "auto": False,
    "setpoint": 70,
}
IMMEDIATE = {"throttle_interval": 0}


async def _call(hass: HomeAssistant, service: str, **data: object) -> None:
    await call(hass, FAN_DOMAIN, service, FAN, **data)


def _fan(hass: HomeAssistant) -> State:
    return state_of(hass, FAN)


async def test_turn_on_sends_power(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    entry = await setup_entry(hass)

    await _call(hass, SERVICE_TURN_ON)
    await entry.runtime_data.executor.wait_idle()

    assert _fan(hass).state == STATE_ON
    assert entry.runtime_data.executor.target == FanState(power=True)
    assert sent(mock_infrared_emitter_entity) == [[Key.POWER]]


async def test_turn_on_with_percentage_sends_power_and_speed_presses_in_two_payloads(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    entry = await setup_entry(hass)

    await _call(hass, SERVICE_TURN_ON, **{ATTR_PERCENTAGE: 75})
    await entry.runtime_data.executor.wait_idle()

    assert entry.runtime_data.executor.target == FanState(power=True, speed=3)
    assert _fan(hass).attributes[ATTR_PERCENTAGE] == 75
    assert sent(mock_infrared_emitter_entity) == [[Key.POWER, Key.UP], [Key.UP]]


async def test_percentage_maps_to_speed(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    entry = await setup_entry(hass, {"throttle_interval": 3600})
    await _call(hass, SERVICE_TURN_ON)
    await entry.runtime_data.executor.wait_idle()

    for percentage, speed in [(1, 1), (25, 1), (26, 2), (50, 2), (75, 3), (100, 4)]:
        await _call(hass, SERVICE_SET_PERCENTAGE, **{ATTR_PERCENTAGE: percentage})
        assert entry.runtime_data.executor.target.speed == speed

    assert _fan(hass).attributes[ATTR_PERCENTAGE] == 100


async def test_turn_off_sets_target_off(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    entry = await setup_entry(hass, {"throttle_interval": 3600})
    await _call(hass, SERVICE_TURN_ON)
    await entry.runtime_data.executor.wait_idle()

    await _call(hass, SERVICE_TURN_OFF)

    assert _fan(hass).state == STATE_OFF
    assert entry.runtime_data.executor.target == FanState(power=False)


async def test_set_percentage_zero_turns_off(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    entry = await setup_entry(hass, {"throttle_interval": 3600})
    await _call(hass, SERVICE_TURN_ON)
    await entry.runtime_data.executor.wait_idle()

    await _call(hass, SERVICE_SET_PERCENTAGE, **{ATTR_PERCENTAGE: 0})

    assert entry.runtime_data.executor.target.power is False


async def test_set_percentage_while_off_turns_on(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    entry = await setup_entry(hass)

    await _call(hass, SERVICE_SET_PERCENTAGE, **{ATTR_PERCENTAGE: 50})
    await entry.runtime_data.executor.wait_idle()

    assert entry.runtime_data.executor.target == FanState(power=True, speed=2)
    assert sent(mock_infrared_emitter_entity) == [[Key.POWER, Key.UP]]


async def test_set_direction_while_off_is_stored_and_not_sent(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    entry = await setup_entry(hass)

    await _call(hass, SERVICE_SET_DIRECTION, **{ATTR_DIRECTION: "reverse"})
    await entry.runtime_data.executor.wait_idle()

    assert _fan(hass).state == STATE_OFF
    assert _fan(hass).attributes[ATTR_DIRECTION] == "reverse"
    assert entry.runtime_data.executor.target == FanState(direction=Direction.EXHAUST)
    assert mock_infrared_emitter_entity.send_command_calls == []


async def test_turn_on_after_direction_stored_sends_direction_press(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    entry = await setup_entry(hass)
    await _call(hass, SERVICE_SET_DIRECTION, **{ATTR_DIRECTION: "reverse"})

    await _call(hass, SERVICE_TURN_ON)
    await entry.runtime_data.executor.wait_idle()

    assert sent(mock_infrared_emitter_entity) == [[Key.POWER, Key.DIRECT_EXHAUST]]


async def test_unavailable_when_emitter_unavailable(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    await setup_entry(hass)
    assert _fan(hass).state == STATE_OFF

    hass.states.async_set(EMITTER_ENTITY_ID, STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    assert _fan(hass).state == STATE_UNAVAILABLE


async def test_turn_on_with_percentage_zero_stays_off(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    await setup_entry(hass)

    await _call(hass, SERVICE_TURN_ON, **{ATTR_PERCENTAGE: 0})

    assert _fan(hass).state == STATE_OFF
    assert sent(mock_infrared_emitter_entity) == []


async def test_turn_off_running_unit_sends_wake_and_power(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    entry = await setup_entry(hass, IMMEDIATE, hass_storage=hass_storage, state=RUNNING)
    assert _fan(hass).state == STATE_ON

    await _call(hass, SERVICE_TURN_OFF)
    await entry.runtime_data.executor.wait_idle()

    assert _fan(hass).state == STATE_OFF
    assert sent(mock_infrared_emitter_entity) == [[Key.POWER, Key.POWER]]


async def test_speed_change_on_running_unit_sends_wake_and_steps(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    entry = await setup_entry(hass, IMMEDIATE, hass_storage=hass_storage, state=RUNNING)

    await _call(hass, SERVICE_SET_PERCENTAGE, **{ATTR_PERCENTAGE: 100})
    await entry.runtime_data.executor.wait_idle()

    assert _fan(hass).attributes[ATTR_PERCENTAGE] == 100
    assert sent(mock_infrared_emitter_entity) == [[Key.UP, Key.UP], [Key.UP]]


async def test_turn_on_after_auto_and_setpoint_stored_while_off(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    hass.config.units = US_CUSTOMARY_SYSTEM
    entry = await setup_entry(
        hass,
        IMMEDIATE,
        hass_storage=hass_storage,
        state={**RUNNING, "power": False, "speed": 1},
    )
    await call(
        hass,
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        "select.fan_mode",
        **{ATTR_OPTION: "auto"},
    )
    await call(hass, NUMBER_DOMAIN, SERVICE_SET_VALUE, "number.fan_setpoint", value=72)
    assert sent(mock_infrared_emitter_entity) == []

    await _call(hass, SERVICE_TURN_ON)
    await entry.runtime_data.executor.wait_idle()

    assert sent(mock_infrared_emitter_entity) == [
        [Key.POWER, Key.AUTO],
        [Key.UP, Key.UP],
    ]
