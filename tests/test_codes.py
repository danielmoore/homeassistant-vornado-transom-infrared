import pytest

from custom_components.vornado_transom_infrared.codes import (
    Key,
    MultiPressCommand,
    press_command,
)

# Frame head 110, custom code 11, then the 7-bit control word, MSB first.
# 1 = 1265 mark + 420 space, 0 = 420 mark + 1265 space. The last space also
# carries the 6740 us footer gap.
# fmt: off
FIRST_FRAMES = {
    Key.POWER: [
        1265, -420,  # 1
        1265, -420,  # 1
        420, -1265,  # 0
        1265, -420,  # 1
        1265, -420,  # 1
        420, -1265,  # 0
        420, -1265,  # 0
        420, -1265,  # 0
        420, -1265,  # 0
        1265, -420,  # 1
        420, -1265,  # 0
        420, -8005,  # 0
    ],
    Key.UP: [
        1265, -420,  # 1
        1265, -420,  # 1
        420, -1265,  # 0
        1265, -420,  # 1
        1265, -420,  # 1
        1265, -420,  # 1
        420, -1265,  # 0
        420, -1265,  # 0
        420, -1265,  # 0
        1265, -420,  # 1
        1265, -420,  # 1
        420, -8005,  # 0
    ],
    Key.DOWN: [
        1265, -420,  # 1
        1265, -420,  # 1
        420, -1265,  # 0
        1265, -420,  # 1
        1265, -420,  # 1
        420, -1265,  # 0
        420, -1265,  # 0
        420, -1265,  # 0
        420, -1265,  # 0
        420, -1265,  # 0
        1265, -420,  # 1
        420, -8005,  # 0
    ],
    Key.DIRECT_EXHAUST: [
        1265, -420,  # 1
        1265, -420,  # 1
        420, -1265,  # 0
        1265, -420,  # 1
        1265, -420,  # 1
        420, -1265,  # 0
        420, -1265,  # 0
        420, -1265,  # 0
        420, -1265,  # 0
        420, -1265,  # 0
        420, -1265,  # 0
        1265, -7160,  # 1
    ],
    Key.AUTO: [
        1265, -420,  # 1
        1265, -420,  # 1
        420, -1265,  # 0
        1265, -420,  # 1
        1265, -420,  # 1
        1265, -420,  # 1
        420, -1265,  # 0
        420, -1265,  # 0
        420, -1265,  # 0
        420, -1265,  # 0
        1265, -420,  # 1
        1265, -7160,  # 1
    ],
}
# fmt: on


@pytest.mark.parametrize("key", list(FIRST_FRAMES))
def test_first_frame(key: Key) -> None:
    timings = press_command(key, 5).get_raw_timings()

    assert timings[:24] == FIRST_FRAMES[key]


def test_second_frame_follows_first() -> None:
    timings = press_command(Key.POWER, 5).get_raw_timings()

    assert timings[47] == -8005
    assert timings[48] == 1265


def test_five_frames_have_120_timings() -> None:
    assert len(press_command(Key.UP, 5).get_raw_timings()) == 120


def test_three_frames_have_72_timings() -> None:
    assert len(press_command(Key.UP, 3).get_raw_timings()) == 72


def test_modulation_is_38khz() -> None:
    assert press_command(Key.POWER, 5).modulation == 38000


def test_two_press_sequence_joins_with_65ms_space() -> None:
    command = MultiPressCommand([press_command(Key.POWER, 5), press_command(Key.UP, 5)])

    timings = command.get_raw_timings()

    assert len(timings) == 240
    assert timings[118] == 420
    assert timings[119] == -65000
    assert timings[120:122] == [1265, -420]
    assert timings[-1] == -8005


def test_single_press_sequence_matches_the_press() -> None:
    press = press_command(Key.AUTO, 5)

    assert MultiPressCommand([press]).get_raw_timings() == press.get_raw_timings()


def test_sequence_has_no_repeat_and_38khz_modulation() -> None:
    command = MultiPressCommand([press_command(Key.POWER, 5)])

    assert command.repeat_count == 0
    assert command.modulation == 38000
