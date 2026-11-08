import pytest
from homeassistant import config_entries
from homeassistant.components.infrared import DATA_COMPONENT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared import EMITTER_ENTITY_ID
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity

from custom_components.vornado_transom_infrared.const import DOMAIN


def _registry_id(hass: HomeAssistant) -> str:
    registry_entry = er.async_get(hass).async_get(EMITTER_ENTITY_ID)
    assert registry_entry is not None
    return registry_entry.id


async def _start_flow(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_user_flow_creates_entry(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    registry_id = _registry_id(hass)

    result = await _start_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"infrared_entity_id": EMITTER_ENTITY_ID},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Vornado Transom Fan"
    assert result["data"] == {"infrared_entity_registry_id": registry_id}
    assert result["result"].unique_id == registry_id


async def test_user_flow_aborts_without_emitters(hass: HomeAssistant) -> None:
    result = await _start_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_entities"


async def test_user_flow_aborts_for_duplicate_emitter(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    registry_id = _registry_id(hass)
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=registry_id,
        data={"infrared_entity_registry_id": registry_id},
    ).add_to_hass(hass)

    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"infrared_entity_id": EMITTER_ENTITY_ID}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_defaults_and_round_trip(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={"infrared_entity_registry_id": "abc"})
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        "frames_per_press": 5,
        "max_timings_per_payload": 288,
        "throttle_interval": 5,
    }

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "frames_per_press": 3,
            "max_timings_per_payload": 200,
            "throttle_interval": 8,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        "frames_per_press": 3,
        "max_timings_per_payload": 200,
        "throttle_interval": 8,
    }

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert entry.options == {
        "frames_per_press": 3,
        "max_timings_per_payload": 200,
        "throttle_interval": 8,
    }


async def test_user_flow_aborts_when_emitter_not_in_registry(
    hass: HomeAssistant, init_infrared: None
) -> None:
    emitter = MockInfraredEmitterEntity("unused")
    emitter._attr_unique_id = None
    emitter.entity_id = "infrared.unregistered"
    await hass.data[DATA_COMPONENT].async_add_entities([emitter])

    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"infrared_entity_id": "infrared.unregistered"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "emitter_not_in_registry"


async def test_options_flow_rejects_payload_too_small(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={"infrared_entity_registry_id": "abc"})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"frames_per_press": 5, "max_timings_per_payload": 239}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "payload_too_small"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"frames_per_press": 5, "max_timings_per_payload": 240}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_rejects_out_of_range(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={"infrared_entity_registry_id": "abc"})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)

    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"], {"frames_per_press": 0}
        )
