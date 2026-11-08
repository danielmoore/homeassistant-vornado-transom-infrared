from collections.abc import Mapping
from typing import Any, override

import probatio
from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
)
from homeassistant.components.infrared import (
    async_get_emitters,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    Selector,
)

from .codes import TIMINGS_PER_FRAME
from .const import (
    CONF_FRAMES_PER_PRESS,
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_ENTITY_REGISTRY_ID,
    CONF_MAX_TIMINGS_PER_PAYLOAD,
    CONF_THROTTLE_INTERVAL,
    DEFAULT_FRAMES_PER_PRESS,
    DEFAULT_MAX_TIMINGS_PER_PAYLOAD,
    DEFAULT_NAME,
    DEFAULT_THROTTLE_INTERVAL,
    DOMAIN,
    MAX_FRAMES_PER_PRESS,
    MAX_MAX_TIMINGS_PER_PAYLOAD,
    MAX_THROTTLE_INTERVAL,
    MIN_FRAMES_PER_PRESS,
    MIN_MAX_TIMINGS_PER_PAYLOAD,
    MIN_THROTTLE_INTERVAL,
)


class VornadoTransomConfigFlow(ConfigFlow, domain=DOMAIN):
    @override
    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return VornadoTransomOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        emitter_entity_ids = async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_infrared_entities")

        if user_input is not None:
            registry = er.async_get(self.hass)
            registry_entry = registry.async_get(user_input[CONF_INFRARED_ENTITY_ID])
            if registry_entry is None:
                return self.async_abort(reason="emitter_not_in_registry")
            # Keyed by registry ID so renaming the entity keeps the entry valid.
            await self.async_set_unique_id(registry_entry.id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={CONF_INFRARED_ENTITY_REGISTRY_ID: registry_entry.id},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_INFRARED_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=emitter_entity_ids,
                        )
                    ),
                }
            ),
        )


def _number(minimum: int, maximum: int) -> Selector[Any]:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum, max=maximum, step=1, mode=NumberSelectorMode.BOX
        )
    )


def _options_schema(values: Mapping[str, Any]) -> probatio.Schema:
    return probatio.Schema(
        {
            probatio.Required(
                CONF_FRAMES_PER_PRESS,
                default=values.get(CONF_FRAMES_PER_PRESS, DEFAULT_FRAMES_PER_PRESS),
            ): _number(MIN_FRAMES_PER_PRESS, MAX_FRAMES_PER_PRESS),
            probatio.Required(
                CONF_MAX_TIMINGS_PER_PAYLOAD,
                default=values.get(
                    CONF_MAX_TIMINGS_PER_PAYLOAD, DEFAULT_MAX_TIMINGS_PER_PAYLOAD
                ),
            ): _number(MIN_MAX_TIMINGS_PER_PAYLOAD, MAX_MAX_TIMINGS_PER_PAYLOAD),
            probatio.Required(
                CONF_THROTTLE_INTERVAL,
                default=values.get(CONF_THROTTLE_INTERVAL, DEFAULT_THROTTLE_INTERVAL),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_THROTTLE_INTERVAL,
                    max=MAX_THROTTLE_INTERVAL,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),
        }
    )


class VornadoTransomOptionsFlow(OptionsFlowWithReload):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            options = {key: int(value) for key, value in user_input.items()}
            # The wake press shares a payload with the press that follows it.
            minimum = 2 * options[CONF_FRAMES_PER_PRESS] * TIMINGS_PER_FRAME
            if options[CONF_MAX_TIMINGS_PER_PAYLOAD] >= minimum:
                return self.async_create_entry(data=options)
            errors["base"] = "payload_too_small"

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(user_input or self.config_entry.options),
            errors=errors,
        )
