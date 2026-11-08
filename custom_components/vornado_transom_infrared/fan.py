import math
from dataclasses import replace
from typing import Any, override

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .device import TransomConfigEntry
from .entity import TransomEmitterEntity
from .state import MAX_SPEED, MIN_SPEED, Direction

SPEED_RANGE = (MIN_SPEED, MAX_SPEED)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TransomConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([TransomFan(entry.runtime_data, entry.entry_id)])


def _speed(percentage: int) -> int:
    return math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))


class TransomFan(TransomEmitterEntity, FanEntity):
    """Shows the target state; the executor sends what the unit needs."""

    _attr_name = None
    _attr_assumed_state = True
    _attr_speed_count = MAX_SPEED
    _attr_supported_features = (
        FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.DIRECTION
    )

    @override
    def _update(self) -> None:
        target = self._executor.target
        self._attr_percentage = (
            ranged_value_to_percentage(SPEED_RANGE, target.speed) if target.power else 0
        )
        self._attr_current_direction = (
            DIRECTION_REVERSE
            if target.direction is Direction.EXHAUST
            else DIRECTION_FORWARD
        )

    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        if percentage == 0:
            await self.async_turn_off()
            return
        target = replace(self._executor.target, power=True)
        if percentage is not None:
            target = replace(target, speed=_speed(percentage))
        self._executor.request(target)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        self._executor.request(replace(self._executor.target, power=False))

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
            return
        await self.async_turn_on(percentage)

    @override
    async def async_set_direction(self, direction: str) -> None:
        self._executor.request(
            replace(
                self._executor.target,
                direction=Direction.EXHAUST
                if direction == DIRECTION_REVERSE
                else Direction.DIRECT,
            )
        )
