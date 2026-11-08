from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .executor import Executor
from .state import FanState

STORAGE_VERSION = 1
SAVE_DELAY = 1


def create_store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}")


async def load_states(store: Store[dict[str, Any]]) -> tuple[FanState, FanState]:
    """Return the stored target and assumed states, off when missing or invalid."""
    data = await store.async_load()
    if data is None:
        return FanState(), FanState()
    try:
        return FanState.from_dict(data["target"]), FanState.from_dict(data["assumed"])
    except KeyError, TypeError, ValueError:
        return FanState(), FanState()


class Persistence:
    """Saves an executor's target and assumed states."""

    def __init__(self, store: Store[dict[str, Any]], executor: Executor) -> None:
        self.store = store
        self.executor = executor

    def _snapshot(self) -> dict[str, Any]:
        return {
            "target": self.executor.target.as_dict(),
            "assumed": self.executor.status.state.as_dict(),
        }

    def save(self) -> None:
        self.store.async_delay_save(self._snapshot, SAVE_DELAY)

    async def flush(self) -> None:
        await self.store.async_save(self._snapshot())
