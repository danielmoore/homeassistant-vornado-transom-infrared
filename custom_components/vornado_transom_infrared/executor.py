import asyncio
import logging
from collections.abc import Awaitable, Callable, Coroutine
from datetime import datetime
from typing import Any

from infrared_protocols.commands import Command

from .payloads import plan_payloads
from .planner import plan
from .state import FanState, UnitStatus

_LOGGER = logging.getLogger(__name__)

# Z2M transfers take about 1-3 s.
TRANSFER_LAG = 3.0
# Back-to-back payloads play ~2.2 s apart.
PAYLOAD_SPACING = 3.0


class Executor:
    """Sends the presses that move the unit from its assumed state to the target.

    Requests coalesce: one background task waits for the throttle interval and
    the planner's send time, then plans against the latest target.
    """

    def __init__(
        self,
        *,
        send: Callable[[Command], Awaitable[None]],
        clock: Callable[[], float],
        utcnow: Callable[[], datetime],
        sleep: Callable[[float], Awaitable[None]],
        create_task: Callable[[Coroutine[Any, Any, None]], asyncio.Task[None]],
        frames_per_press: int,
        max_timings: int,
        throttle_interval: float,
        target: FanState,
        status: UnitStatus,
    ) -> None:
        self.send = send
        self.clock = clock
        self.utcnow = utcnow
        self.sleep = sleep
        self.create_task = create_task
        self.frames_per_press = frames_per_press
        self.max_timings = max_timings
        self.throttle_interval = throttle_interval
        self.target = target
        self.status = status
        self.last_command_at: float | None = None
        self.last_command_time: datetime | None = None
        self._listeners: list[Callable[[], None]] = []
        self._task: asyncio.Task[None] | None = None
        self._resyncs = 0
        self._changed = asyncio.Event()

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def remove() -> None:
            self._listeners.remove(listener)

        return remove

    def request(self, target: FanState) -> None:
        """Set a new target and send what it needs in the background."""
        self.target = target
        self._changed.set()
        self._notify()
        if self._task is None or self._task.done():
            self._task = self.create_task(self._run())

    def resync(self, state: FanState) -> None:
        """Set target and assumed state to state without sending."""
        self._resyncs += 1
        self.target = state
        self.status = UnitStatus(state, self.status.idle_at)
        self._changed.set()
        self._notify()

    async def wait_idle(self) -> None:
        if self._task is not None:
            await self._task

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

    def _notify(self) -> None:
        for listener in list(self._listeners):
            try:
                listener()
            except Exception:
                _LOGGER.exception("Listener failed")

    async def _run(self) -> None:
        try:
            await self._send_until_settled()
        except Exception:
            _LOGGER.exception("Fan command executor failed")

    async def _wait(self, seconds: float) -> None:
        """Sleep, ending early when a request or resync arrives."""
        waits = {
            asyncio.ensure_future(self.sleep(seconds)),
            asyncio.ensure_future(self._changed.wait()),
        }
        try:
            await asyncio.wait(waits, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for wait in waits:
                wait.cancel()
            await asyncio.gather(*waits, return_exceptions=True)

    async def _send_until_settled(self) -> None:
        while True:
            self._changed.clear()
            now = self.clock()
            planned = plan(self.target, self.status, now, transfer_lag=TRANSFER_LAG)
            if planned is None:
                return
            ready_at = planned.send_at
            if self.last_command_at is not None:
                ready_at = max(ready_at, self.last_command_at + self.throttle_interval)
            if ready_at > now:
                await self._wait(ready_at - now)
                continue

            payloads = plan_payloads(
                planned.presses, self.frames_per_press, self.max_timings
            )
            resyncs = self._resyncs
            self.last_command_at = now
            self.last_command_time = self.utcnow()
            sent = 0
            try:
                for payload in payloads:
                    if resyncs != self._resyncs:
                        break
                    sent += 1
                    await self.send(payload)
            except Exception:
                _LOGGER.exception(
                    "Sending to the fan failed; assuming the planned state anyway"
                )
            finally:
                if sent:
                    idle_at = now + (sent - 1) * PAYLOAD_SPACING + planned.awake_for
                    state = (
                        self.status.state if resyncs != self._resyncs else planned.state
                    )
                    self.status = UnitStatus(state, idle_at)
                    self._notify()
