import asyncio

from homeassistant.components.infrared import async_send_command
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_registry import EventEntityRegistryUpdatedData
from homeassistant.helpers.event import async_track_entity_registry_updated_event
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util
from infrared_protocols.commands import Command

from .const import (
    CONF_FRAMES_PER_PRESS,
    CONF_INFRARED_ENTITY_REGISTRY_ID,
    CONF_MAX_TIMINGS_PER_PAYLOAD,
    CONF_THROTTLE_INTERVAL,
    DEFAULT_FRAMES_PER_PRESS,
    DEFAULT_MAX_TIMINGS_PER_PAYLOAD,
    DEFAULT_THROTTLE_INTERVAL,
    DOMAIN,
)
from .device import Device, TransomConfigEntry
from .executor import Executor
from .persistence import Persistence, create_store, load_states
from .services import async_setup_services
from .state import UnitStatus

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.FAN,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: TransomConfigEntry) -> bool:
    registry_id = entry.data[CONF_INFRARED_ENTITY_REGISTRY_ID]
    registry_entry = er.async_get(hass).async_get(registry_id)
    if registry_entry is None:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="emitter_not_in_registry"
        )
    emitter_entity_id = registry_entry.entity_id

    async def send(command: Command) -> None:
        await async_send_command(hass, registry_id, command)

    store = create_store(hass, entry.entry_id)
    target, assumed = await load_states(store)

    executor = Executor(
        send=send,
        clock=hass.loop.time,
        utcnow=dt_util.utcnow,
        sleep=asyncio.sleep,
        create_task=lambda coro: entry.async_create_background_task(
            hass, coro, "vornado_transom_infrared send"
        ),
        frames_per_press=entry.options.get(
            CONF_FRAMES_PER_PRESS, DEFAULT_FRAMES_PER_PRESS
        ),
        max_timings=entry.options.get(
            CONF_MAX_TIMINGS_PER_PAYLOAD, DEFAULT_MAX_TIMINGS_PER_PAYLOAD
        ),
        throttle_interval=entry.options.get(
            CONF_THROTTLE_INTERVAL, DEFAULT_THROTTLE_INTERVAL
        ),
        target=target,
        status=UnitStatus(assumed),
    )

    persistence = Persistence(store, executor)

    entry.runtime_data = Device(
        executor=executor,
        emitter_entity_id=emitter_entity_id,
        device_info=DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Vornado",
            model="Transom",
        ),
    )

    @callback
    def emitter_changed(event: Event[EventEntityRegistryUpdatedData]) -> None:
        if event.data["action"] == "remove" or "old_entity_id" in event.data:
            hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(executor.add_listener(persistence.save))
    entry.async_on_unload(
        async_track_entity_registry_updated_event(
            hass, emitter_entity_id, emitter_changed
        )
    )
    entry.async_on_unload(persistence.flush)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TransomConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.executor.stop()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: TransomConfigEntry) -> None:
    await create_store(hass, entry.entry_id).async_remove()
