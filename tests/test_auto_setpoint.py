from typing import Any

from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
)
from homeassistant.components.number import SERVICE_SET_VALUE
from homeassistant.components.select import (
    ATTR_OPTION,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import (
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity

from custom_components.vornado_transom_infrared.codes import Key
from custom_components.vornado_transom_infrared.state import FanState

from .conftest import call, sent, setup_entry, state_of

SELECT = "select.fan_mode"
NUMBER = "number.fan_setpoint"

ON_AUTO_OFF = {
    "power": True,
    "speed": 1,
    "direction": "direct",
    "auto": False,
    "setpoint": 70,
}
OFF = {**ON_AUTO_OFF, "power": False}


async def _setup_with(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    state: dict[str, Any],
    units: UnitSystem = US_CUSTOMARY_SYSTEM,
) -> MockConfigEntry:
    hass.config.units = units
    return await setup_entry(
        hass, {"throttle_interval": 0}, hass_storage=hass_storage, state=state
    )


async def test_switch_turn_on_sends_auto(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    entry = await _setup_with(hass, hass_storage, ON_AUTO_OFF)
    assert state_of(hass, SELECT).state == "manual"

    await call(
        hass, SELECT_DOMAIN, SERVICE_SELECT_OPTION, SELECT, **{ATTR_OPTION: "auto"}
    )
    await entry.runtime_data.executor.wait_idle()

    assert state_of(hass, SELECT).state == "auto"
    assert entry.runtime_data.executor.target.auto is True
    assert sent(mock_infrared_emitter_entity) == [[Key.AUTO, Key.AUTO]]


async def test_switch_turn_off_sends_double_auto(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    entry = await _setup_with(hass, hass_storage, {**ON_AUTO_OFF, "auto": True})
    assert state_of(hass, SELECT).state == "auto"

    await call(
        hass, SELECT_DOMAIN, SERVICE_SELECT_OPTION, SELECT, **{ATTR_OPTION: "manual"}
    )
    await entry.runtime_data.executor.wait_idle()

    assert state_of(hass, SELECT).state == "manual"
    assert sent(mock_infrared_emitter_entity) == [[Key.AUTO], [Key.AUTO, Key.AUTO]]


async def test_switch_while_power_off_only_stores_target(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    entry = await _setup_with(hass, hass_storage, OFF)

    await call(
        hass, SELECT_DOMAIN, SERVICE_SELECT_OPTION, SELECT, **{ATTR_OPTION: "auto"}
    )
    await entry.runtime_data.executor.wait_idle()

    assert state_of(hass, SELECT).state == "auto"
    assert entry.runtime_data.executor.target == FanState(auto=True, setpoint=70)
    assert sent(mock_infrared_emitter_entity) == []


async def test_number_shows_target_setpoint(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    await _setup_with(hass, hass_storage, ON_AUTO_OFF)

    state = state_of(hass, NUMBER)
    assert state.state == "70"
    assert state.attributes["min"] == 60
    assert state.attributes["max"] == 90
    assert state.attributes["step"] == 1
    assert state.attributes["unit_of_measurement"] == "°F"


async def test_number_with_auto_on_sends_auto_and_steps(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    entry = await _setup_with(hass, hass_storage, {**ON_AUTO_OFF, "auto": True})

    await call(hass, NUMBER_DOMAIN, SERVICE_SET_VALUE, NUMBER, value=72)
    await entry.runtime_data.executor.wait_idle()

    assert state_of(hass, NUMBER).state == "72"
    assert entry.runtime_data.executor.target.setpoint == 72
    assert sent(mock_infrared_emitter_entity) == [
        [Key.AUTO, Key.AUTO],
        [Key.UP, Key.UP],
    ]


async def test_number_with_auto_off_sends_nothing(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    entry = await _setup_with(hass, hass_storage, ON_AUTO_OFF)

    await call(hass, NUMBER_DOMAIN, SERVICE_SET_VALUE, NUMBER, value=65)
    await entry.runtime_data.executor.wait_idle()

    assert state_of(hass, NUMBER).state == "65"
    assert entry.runtime_data.executor.target.setpoint == 65
    assert sent(mock_infrared_emitter_entity) == []


async def test_entities_unavailable_with_emitter(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    await _setup_with(hass, hass_storage, ON_AUTO_OFF)

    mock_infrared_emitter_entity._attr_available = False
    mock_infrared_emitter_entity.async_write_ha_state()
    await hass.async_block_till_done()

    assert state_of(hass, SELECT).state == STATE_UNAVAILABLE
    assert state_of(hass, NUMBER).state == STATE_UNAVAILABLE


async def test_number_converts_to_celsius_under_metric_units(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    entry = await _setup_with(
        hass, hass_storage, {**ON_AUTO_OFF, "auto": True}, units=METRIC_SYSTEM
    )

    assert state_of(hass, NUMBER).state == "21.0"
    assert state_of(hass, NUMBER).attributes["unit_of_measurement"] == "°C"

    await call(hass, NUMBER_DOMAIN, SERVICE_SET_VALUE, NUMBER, value=24)
    await entry.runtime_data.executor.wait_idle()

    assert entry.runtime_data.executor.target.setpoint == 75


async def test_auto_on_after_setpoint_changed_with_auto_off(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    entry = await _setup_with(hass, hass_storage, ON_AUTO_OFF)
    await call(hass, NUMBER_DOMAIN, SERVICE_SET_VALUE, NUMBER, value=72)
    assert sent(mock_infrared_emitter_entity) == []

    await call(
        hass, SELECT_DOMAIN, SERVICE_SELECT_OPTION, SELECT, **{ATTR_OPTION: "auto"}
    )
    await entry.runtime_data.executor.wait_idle()

    assert state_of(hass, SELECT).state == "auto"
    assert state_of(hass, NUMBER).state == "72"
    assert sent(mock_infrared_emitter_entity) == [
        [Key.AUTO, Key.AUTO],
        [Key.UP, Key.UP],
    ]
