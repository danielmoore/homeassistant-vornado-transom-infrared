import json
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component


async def test_integration_is_discovered(hass: HomeAssistant) -> None:
    integration = await async_get_integration(hass, "vornado_transom_infrared")

    assert integration.name == "Vornado Transom (Infrared)"
    assert integration.dependencies == ["infrared"]
    assert integration.iot_class == "assumed_state"


async def test_component_sets_up(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, "vornado_transom_infrared", {})


COMPONENT_DIR = (
    Path(__file__).parent.parent / "custom_components" / "vornado_transom_infrared"
)


def test_en_translations_match_strings() -> None:
    strings = (COMPONENT_DIR / "strings.json").read_text()
    assert (COMPONENT_DIR / "translations" / "en.json").read_text() == strings


def test_icons_and_exceptions_have_strings() -> None:
    strings = json.loads((COMPONENT_DIR / "strings.json").read_text())
    icons = json.loads((COMPONENT_DIR / "icons.json").read_text())
    for platform, keys in icons["entity"].items():
        assert keys.keys() <= strings["entity"][platform].keys()
    assert icons["services"].keys() <= strings["services"].keys()
    assert "emitter_not_in_registry" in strings["exceptions"]
