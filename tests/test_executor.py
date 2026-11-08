import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from infrared_protocols.commands import Command

from custom_components.vornado_transom_infrared.codes import Key, MultiPressCommand
from custom_components.vornado_transom_infrared.executor import Executor
from custom_components.vornado_transom_infrared.state import FanState, UnitStatus

OFF = FanState()
ON = FanState(power=True)


async def no_hook(sent_count: int) -> None:
    pass


class Fake:
    """Fake clock, sleep and send. Sleeps block until advance() reaches them."""

    def __init__(self, on_send: Callable[[int], Awaitable[None]] = no_hook) -> None:
        self.now = 100.0
        self.on_send = on_send
        self.sent: list[tuple[float, list[Key]]] = []
        self.sleeps: list[float] = []
        self.fail_on: int | None = None
        self._waiters: list[tuple[float, asyncio.Future[None]]] = []

    def clock(self) -> float:
        return self.now

    def utcnow(self) -> datetime:
        return datetime(2026, 11, 7, 12, 0, tzinfo=UTC) + timedelta(
            seconds=self.now - 100.0
        )

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        future: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._waiters.append((self.now + seconds, future))
        await future

    async def settle(self) -> None:
        for _ in range(10):
            await asyncio.sleep(0)

    async def advance(self, seconds: float) -> None:
        await self.settle()
        self.now += seconds
        for deadline, future in self._waiters:
            if deadline <= self.now and not future.done():
                future.set_result(None)
        await self.settle()

    async def send(self, command: Command) -> None:
        assert isinstance(command, MultiPressCommand)
        self.sent.append((self.now, [Key(p.control_word) for p in command.presses]))
        await self.on_send(len(self.sent))
        if self.fail_on == len(self.sent):
            raise RuntimeError("timed out")

    def keys(self) -> list[list[Key]]:
        return [keys for _, keys in self.sent]


def make(
    fake: Fake,
    target: FanState = OFF,
    status: UnitStatus | None = None,
    throttle: float = 5.0,
    max_timings: int = 288,
) -> Executor:
    return Executor(
        send=fake.send,
        clock=fake.clock,
        utcnow=fake.utcnow,
        sleep=fake.sleep,
        create_task=asyncio.create_task,
        frames_per_press=5,
        max_timings=max_timings,
        throttle_interval=throttle,
        target=target,
        status=status or UnitStatus(target),
    )


async def test_power_on_sends_power_and_updates_state() -> None:
    fake = Fake()
    ex = make(fake)
    ex.request(ON)
    await ex.wait_idle()
    assert fake.sent == [(100.0, [Key.POWER])]
    assert ex.status == UnitStatus(ON, idle_at=105.0)
    assert ex.last_command_at == 100.0
    assert ex.last_command_time == datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


async def test_no_change_sends_nothing() -> None:
    fake = Fake()
    ex = make(fake)
    ex.request(replace(OFF, speed=3))
    await ex.wait_idle()
    assert fake.sent == []
    assert ex.last_command_at is None
    assert ex.last_command_time is None


async def test_payloads_are_split_in_order_and_idle_at_spans_them() -> None:
    fake = Fake()
    ex = make(fake, ON, UnitStatus(ON, idle_at=0.0))
    ex.request(replace(ON, speed=4))
    await ex.wait_idle()
    assert fake.keys() == [[Key.UP, Key.UP], [Key.UP, Key.UP]]
    assert {t for t, _ in fake.sent} == {100.0}
    assert ex.status.state.speed == 4
    assert ex.status.idle_at == 108.0


async def test_planner_wait_for_idle_is_honored() -> None:
    fake = Fake()
    ex = make(fake, ON, UnitStatus(ON, idle_at=110.0), throttle=0.0)
    ex.request(replace(ON, speed=2))
    await fake.settle()
    assert fake.sleeps == [13.0]
    assert fake.sent == []
    await fake.advance(13.0)
    await ex.wait_idle()
    assert fake.sent == [(113.0, [Key.UP, Key.UP])]


async def test_throttle_waits_for_interval_after_last_send() -> None:
    fake = Fake()
    ex = make(fake, throttle=20.0)
    ex.request(ON)
    await ex.wait_idle()
    ex.request(OFF)
    await fake.settle()
    assert fake.sleeps == [20.0]
    await fake.advance(20.0)
    await ex.wait_idle()
    assert fake.sent == [
        (100.0, [Key.POWER]),
        (120.0, [Key.POWER, Key.POWER]),
    ]


async def test_planner_wait_wins_over_shorter_throttle() -> None:
    fake = Fake()
    ex = make(fake, throttle=5.0)
    ex.request(ON)
    await ex.wait_idle()
    ex.request(OFF)
    await fake.settle()
    assert fake.sleeps == [8.0]
    await fake.advance(8.0)
    await ex.wait_idle()
    assert fake.sent[1][0] == 108.0


async def test_requests_during_wait_coalesce() -> None:
    fake = Fake()
    ex = make(fake, ON, UnitStatus(ON, idle_at=110.0), throttle=0.0)
    ex.request(replace(ON, speed=2))
    await fake.settle()
    ex.request(replace(ON, speed=3))
    await fake.settle()
    assert fake.sent == []
    await fake.advance(13.0)
    await ex.wait_idle()
    assert fake.keys() == [[Key.UP, Key.UP], [Key.UP]]
    assert ex.status.state.speed == 3


async def test_change_allowing_earlier_send_interrupts_wait() -> None:
    fake = Fake()
    ex = make(fake, ON, UnitStatus(ON, idle_at=200.0), throttle=0.0)
    ex.request(replace(ON, speed=2))
    await fake.settle()
    ex.resync(OFF)
    ex.request(ON)
    await ex.wait_idle()
    assert fake.sent == [(100.0, [Key.POWER])]


async def test_quick_requests_before_first_send_coalesce() -> None:
    fake = Fake()
    ex = make(fake, ON, UnitStatus(ON, idle_at=0.0))
    ex.request(replace(ON, speed=2))
    ex.request(replace(ON, speed=3))
    await ex.wait_idle()
    assert fake.keys() == [[Key.UP, Key.UP], [Key.UP]]


async def test_request_during_send_is_sent_next() -> None:
    async def on_send(count: int) -> None:
        if count == 1:
            ex.request(replace(ON, speed=1))

    fake = Fake(on_send)
    ex = make(fake, ON, UnitStatus(ON, idle_at=0.0))
    ex.request(replace(ON, speed=2))
    await fake.settle()
    assert fake.keys() == [[Key.UP, Key.UP]]
    await fake.advance(8.0)
    await ex.wait_idle()
    assert fake.keys() == [[Key.UP, Key.UP], [Key.DOWN, Key.DOWN]]
    assert fake.sent[1][0] == 108.0


async def test_error_stops_remaining_payloads_and_keeps_planned_state() -> None:
    fake = Fake()
    fake.fail_on = 1
    ex = make(fake, ON, UnitStatus(ON, idle_at=0.0))
    ex.request(replace(ON, speed=4))
    await ex.wait_idle()
    assert fake.keys() == [[Key.UP, Key.UP]]
    assert ex.status == UnitStatus(replace(ON, speed=4), idle_at=105.0)
    assert ex.last_command_at == 100.0


async def test_cancel_mid_send_keeps_planned_state() -> None:
    async def on_send(count: int) -> None:
        await asyncio.Event().wait()

    fake = Fake(on_send)
    ex = make(fake, ON, UnitStatus(ON, idle_at=0.0))
    ex.request(replace(ON, speed=4))
    await fake.settle()
    await ex.stop()
    assert ex.status == UnitStatus(replace(ON, speed=4), idle_at=105.0)


async def test_resync_sets_both_states_without_sending() -> None:
    fake = Fake()
    ex = make(fake)
    ex.resync(replace(ON, speed=3))
    await ex.wait_idle()
    assert fake.sent == []
    assert ex.target == replace(ON, speed=3)
    assert ex.status.state == replace(ON, speed=3)


async def test_resync_cancels_pending_send() -> None:
    fake = Fake()
    ex = make(fake, ON, UnitStatus(ON, idle_at=110.0), throttle=0.0)
    ex.request(replace(ON, speed=2))
    await fake.settle()
    ex.resync(ON)
    await ex.wait_idle()
    assert fake.sent == []
    assert ex.target == ON


async def test_resync_during_send_keeps_resynced_state_and_counts_idle() -> None:
    async def on_send(count: int) -> None:
        ex.resync(replace(ON, speed=2))

    fake = Fake(on_send)
    ex = make(fake, ON, UnitStatus(ON, idle_at=0.0))
    calls: list[UnitStatus] = []
    ex.add_listener(lambda: calls.append(ex.status))
    ex.request(replace(ON, speed=4))
    await ex.wait_idle()
    assert fake.keys() == [[Key.UP, Key.UP]]
    assert ex.status == UnitStatus(replace(ON, speed=2), idle_at=105.0)
    assert calls[-1] == ex.status
    assert ex.target.speed == 2


async def test_listeners_notified_and_unsubscribed() -> None:
    fake = Fake()
    ex = make(fake)
    calls: list[tuple[FanState, FanState]] = []
    remove = ex.add_listener(lambda: calls.append((ex.target, ex.status.state)))
    ex.request(ON)
    await ex.wait_idle()
    assert calls == [(ON, OFF), (ON, ON)]
    remove()
    ex.resync(OFF)
    assert len(calls) == 2


async def test_failing_listener_is_logged_and_sending_continues(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def broken() -> None:
        raise RuntimeError("boom")

    fake = Fake()
    ex = make(fake)
    ex.add_listener(broken)
    ex.request(ON)
    await ex.wait_idle()
    assert fake.keys() == [[Key.POWER]]
    assert "Listener failed" in caplog.text


async def test_planner_failure_is_logged_and_later_request_sends(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = Fake()
    ex = make(fake, max_timings=100)
    with caplog.at_level(logging.ERROR):
        ex.request(ON)
        await ex.wait_idle()
    assert "executor failed" in caplog.text
    assert fake.sent == []
    ex.max_timings = 288
    ex.request(ON)
    await ex.wait_idle()
    assert fake.keys() == [[Key.POWER]]


async def test_stop_cancels_pending_send() -> None:
    fake = Fake()
    ex = make(fake, ON, UnitStatus(ON, idle_at=110.0), throttle=0.0)
    ex.request(replace(ON, speed=2))
    await fake.settle()
    await ex.stop()
    await fake.advance(13.0)
    assert fake.sent == []


async def test_last_command_time_is_fixed_until_the_next_send() -> None:
    fake = Fake()
    ex = make(fake)
    ex.request(ON)
    await ex.wait_idle()
    await fake.advance(37.4)

    ex.resync(replace(ON, speed=3))

    assert ex.last_command_time == datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
