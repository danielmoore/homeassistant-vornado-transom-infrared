import pytest

from custom_components.vornado_transom_infrared.codes import Key, MultiPressCommand
from custom_components.vornado_transom_infrared.payloads import (
    GroupTooLargeError,
    plan_payloads,
)


def keys_of(payloads: list[MultiPressCommand]) -> list[list[Key]]:
    return [[Key(p.control_word) for p in payload.presses] for payload in payloads]


def ups(count: int) -> list[list[Key]]:
    return [[Key.UP] for _ in range(count)]


def test_no_groups() -> None:
    assert plan_payloads([], frames=5) == []


def test_one_press() -> None:
    assert keys_of(plan_payloads(ups(1), frames=5)) == [[Key.UP]]


def test_two_presses_share_a_payload() -> None:
    assert keys_of(plan_payloads(ups(2), frames=5)) == [[Key.UP, Key.UP]]


def test_three_presses_split_after_two() -> None:
    assert keys_of(plan_payloads(ups(3), frames=5)) == [
        [Key.UP, Key.UP],
        [Key.UP],
    ]


def test_thirty_presses() -> None:
    result = keys_of(plan_payloads(ups(30), frames=5))
    assert len(result) == 15
    assert all(payload == [Key.UP, Key.UP] for payload in result)


def test_payload_timings_within_maximum() -> None:
    for payload in plan_payloads(ups(30), frames=5):
        assert len(payload.get_raw_timings()) == 240


def test_wake_press_is_packed_like_any_other_press() -> None:
    groups = [[Key.POWER], [Key.UP], [Key.UP]]
    assert keys_of(plan_payloads(groups, frames=5)) == [
        [Key.POWER, Key.UP],
        [Key.UP],
    ]


def test_double_auto_moves_whole_to_next_payload() -> None:
    groups = [[Key.UP], [Key.AUTO, Key.AUTO]]
    assert keys_of(plan_payloads(groups, frames=5)) == [
        [Key.UP],
        [Key.AUTO, Key.AUTO],
    ]


def test_order_preserved_when_small_group_follows_large() -> None:
    groups = [[Key.UP], [Key.AUTO, Key.AUTO], [Key.DOWN]]
    assert keys_of(plan_payloads(groups, frames=5)) == [
        [Key.UP],
        [Key.AUTO, Key.AUTO],
        [Key.DOWN],
    ]


def test_group_that_does_not_fit() -> None:
    with pytest.raises(GroupTooLargeError):
        plan_payloads([[Key.UP, Key.UP, Key.UP]], frames=5)


def test_different_maximum() -> None:
    assert keys_of(plan_payloads(ups(3), frames=5, max_timings=360)) == [
        [Key.UP, Key.UP, Key.UP]
    ]
    assert keys_of(plan_payloads(ups(2), frames=5, max_timings=239)) == [
        [Key.UP],
        [Key.UP],
    ]


def test_fewer_frames_fit_more_presses() -> None:
    assert keys_of(plan_payloads(ups(5), frames=3)) == [
        [Key.UP, Key.UP, Key.UP, Key.UP],
        [Key.UP],
    ]
