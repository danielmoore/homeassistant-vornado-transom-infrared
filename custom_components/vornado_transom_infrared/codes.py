from collections.abc import Sequence
from enum import IntEnum
from typing import override

from infrared_protocols.commands import Command
from infrared_protocols.commands.symphony import MODULATION_HZ, SymphonyCommand

CUSTOM_CODE = 3
TIMINGS_PER_FRAME = 24
PRESS_JOIN_SPACE_US = 65000


class Key(IntEnum):
    """Transom remote keys, valued by Symphony control word."""

    POWER = 0x04
    UP = 0x46
    DOWN = 0x02
    DIRECT_EXHAUST = 0x01
    AUTO = 0x43


def press_command(key: Key, frames: int) -> SymphonyCommand:
    return SymphonyCommand(
        custom_code=CUSTOM_CODE, control_word=key, repeat_count=frames - 1
    )


class MultiPressCommand(Command):
    """Several key presses sent as one payload, separated by a long idle gap."""

    presses: Sequence[SymphonyCommand]

    def __init__(self, presses: Sequence[SymphonyCommand]) -> None:
        super().__init__(modulation=MODULATION_HZ, repeat_count=0)
        self.presses = presses

    @override
    def get_raw_timings(self) -> list[int]:
        timings: list[int] = []
        for press in self.presses[:-1]:
            timings.extend(press.get_raw_timings()[:-1])
            timings.append(-PRESS_JOIN_SPACE_US)
        if self.presses:
            timings.extend(self.presses[-1].get_raw_timings())
        return timings
