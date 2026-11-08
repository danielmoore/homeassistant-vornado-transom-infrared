from collections.abc import Sequence

from .codes import Key, MultiPressCommand, press_command

DEFAULT_MAX_TIMINGS = 288


class GroupTooLargeError(ValueError):
    """A group of presses that must share a payload exceeds the maximum."""


def plan_payloads(
    groups: Sequence[Sequence[Key]],
    frames: int,
    max_timings: int = DEFAULT_MAX_TIMINGS,
) -> list[MultiPressCommand]:
    """Pack groups of presses into payloads, in order, within max_timings.

    The presses of a group always share a payload.
    """
    payloads: list[MultiPressCommand] = []
    current: list[Key] = []
    for group in groups:
        if _timing_count(group, frames) > max_timings:
            raise GroupTooLargeError(
                f"{len(group)} presses at {frames} frames exceed {max_timings} timings"
            )
        if current and _timing_count([*current, *group], frames) > max_timings:
            payloads.append(_command(current, frames))
            current = []
        current.extend(group)
    if current:
        payloads.append(_command(current, frames))
    return payloads


def _command(keys: Sequence[Key], frames: int) -> MultiPressCommand:
    return MultiPressCommand([press_command(key, frames) for key in keys])


def _timing_count(keys: Sequence[Key], frames: int) -> int:
    return len(_command(keys, frames).get_raw_timings())
