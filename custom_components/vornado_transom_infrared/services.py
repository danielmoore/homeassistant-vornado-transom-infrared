from dataclasses import replace

import probatio
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service

from .const import DOMAIN
from .device import TransomConfigEntry
from .state import MAX_SETPOINT, MAX_SPEED, MIN_SETPOINT, MIN_SPEED, Direction

SERVICE_SET_ASSUMED_STATE = "set_assumed_state"

ATTR_POWER = "power"
ATTR_SPEED = "speed"
ATTR_DIRECTION = "direction"
ATTR_AUTO = "auto"
ATTR_SETPOINT = "setpoint"

SET_ASSUMED_STATE_SCHEMA = cv.make_entity_service_schema(
    {
        probatio.Optional(ATTR_POWER): cv.boolean,
        probatio.Optional(ATTR_SPEED): probatio.All(
            int, probatio.Range(min=MIN_SPEED, max=MAX_SPEED)
        ),
        probatio.Optional(ATTR_DIRECTION): probatio.Coerce(Direction),
        probatio.Optional(ATTR_AUTO): cv.boolean,
        probatio.Optional(ATTR_SETPOINT): probatio.All(
            int, probatio.Range(min=MIN_SETPOINT, max=MAX_SETPOINT)
        ),
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    # Not an entity service: those skip unavailable entities, and resync has to
    # work while the emitter is down.
    async def set_assumed_state(call: ServiceCall) -> None:
        changes = {
            k: v for k, v in call.data.items() if k not in cv.ENTITY_SERVICE_FIELDS
        }
        targeted = await service.async_extract_config_entry_ids(call)
        own = {entry.entry_id for entry in hass.config_entries.async_entries(DOMAIN)}
        for entry_id in targeted & own:
            entry: TransomConfigEntry = service.async_get_config_entry(
                hass, DOMAIN, entry_id
            )
            executor = entry.runtime_data.executor
            executor.resync(replace(executor.status.state, **changes))

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ASSUMED_STATE,
        set_assumed_state,
        SET_ASSUMED_STATE_SCHEMA,
    )
