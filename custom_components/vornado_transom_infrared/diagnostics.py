from typing import Any

from homeassistant.core import HomeAssistant

from .device import TransomConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TransomConfigEntry
) -> dict[str, Any]:
    executor = entry.runtime_data.executor
    return {
        "options": dict(entry.options),
        "target": executor.target.as_dict(),
        "assumed": executor.status.state.as_dict(),
        "last_command_time": (
            executor.last_command_time.isoformat()
            if executor.last_command_time
            else None
        ),
        "assumed_idle": executor.clock() >= executor.status.idle_at,
    }
