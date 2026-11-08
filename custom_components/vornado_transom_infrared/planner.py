from collections.abc import Sequence
from dataclasses import dataclass, replace

from .codes import Key
from .state import FanState, UnitStatus

IDLE_TIMEOUT = 5.0
SETPOINT_WINDOW = 5.0


@dataclass(frozen=True)
class Plan:
    """Presses to send and the assumed unit state afterwards.

    awake_for is how long after the last press the unit stays awake. The
    planner can't know when the last press plays, so the caller sets idle_at.
    """

    presses: Sequence[Sequence[Key]]
    send_at: float
    awake_for: float
    state: FanState


def _steps(delta: int) -> list[tuple[Key, ...]]:
    return [(Key.UP,)] * delta if delta > 0 else [(Key.DOWN,)] * -delta


def _wake(presses: list[tuple[Key, ...]]) -> list[tuple[Key, ...]]:
    # No key is harmless on an awake unit, so the wake press duplicates the
    # first real press: an idle unit absorbs it, an awake one sees it twice.
    return [(presses[0][0],), *presses]


def plan(
    target: FanState, assumed: UnitStatus, now: float, *, transfer_lag: float
) -> Plan | None:
    """Plan the press groups moving the unit toward the target.

    Returns None if nothing on the unit changes.

    Order within one send: power, direction, speed, then Auto and setpoint, so
    the speed presses aren't swallowed by the setpoint window that Auto opens.
    A send to a unit assumed on waits until idle_at plus transfer_lag, because
    a still-awake unit would count the wake press as a real one. A send that
    opens or extends the setpoint window leaves the unit awake for the window
    plus the idle timeout. Only the double Auto is a multi-press group, since
    its presses must share a payload. The wake press is its own group: split
    payloads arrive inside the unit's idle timeout.
    """
    unit = assumed.state
    if not target.power:
        if not unit.power:
            return None
        send_at = max(now, assumed.idle_at + transfer_lag)
        return Plan(
            tuple(_wake([(Key.POWER,)])), send_at, 0.0, replace(unit, power=False)
        )

    presses: list[tuple[Key, ...]] = []
    state = replace(unit, power=True)
    if not unit.power:
        presses.append((Key.POWER,))
    if target.direction != unit.direction:
        presses.append((Key.DIRECT_EXHAUST,))
        state = replace(state, direction=target.direction)

    presses += _steps(target.speed - unit.speed)
    state = replace(state, speed=target.speed)

    awake_for = IDLE_TIMEOUT
    if target.auto and (not unit.auto or target.setpoint != unit.setpoint):
        presses += [(Key.AUTO,), *_steps(target.setpoint - unit.setpoint)]
        state = replace(state, auto=True, setpoint=target.setpoint)
        awake_for = SETPOINT_WINDOW + IDLE_TIMEOUT
    elif not target.auto and unit.auto:
        presses.append((Key.AUTO, Key.AUTO))
        state = replace(state, auto=False)

    if not presses:
        return None
    send_at = now
    if unit.power:
        presses = _wake(presses)
        send_at = max(now, assumed.idle_at + transfer_lag)
    return Plan(tuple(presses), send_at, awake_for, state)
