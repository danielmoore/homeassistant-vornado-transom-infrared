import pytest

from custom_components.vornado_transom_infrared.codes import Key
from custom_components.vornado_transom_infrared.planner import plan
from custom_components.vornado_transom_infrared.state import (
    Direction,
    FanState,
    UnitStatus,
)

LAG = 2.0


def on(**kw) -> FanState:
    return FanState(power=True, **kw)


def run(target, unit, now=100.0, idle_at=0.0):
    return plan(target, UnitStatus(unit, idle_at), now, transfer_lag=LAG)


def test_invalid_state_raises():
    with pytest.raises(ValueError):
        FanState(speed=5)
    with pytest.raises(ValueError):
        FanState(speed=0)
    with pytest.raises(ValueError):
        FanState(setpoint=59)
    with pytest.raises(ValueError):
        FanState(setpoint=91)


def test_nothing_to_do():
    assert run(on(speed=2), on(speed=2)) is None
    assert run(FanState(power=False, speed=3), FanState(power=False)) is None


def test_power_on_from_off_has_no_wake():
    p = run(on(), FanState())
    assert p.presses == ((Key.POWER,),)
    assert p.state.power


def test_power_off_wakes_first():
    p = run(FanState(), on())
    assert p.presses == ((Key.POWER,), (Key.POWER,))
    assert not p.state.power


def test_power_off_ignores_other_targets():
    p = run(FanState(speed=4, auto=True), on(speed=2))
    assert p.presses == ((Key.POWER,), (Key.POWER,))
    assert p.state.speed == 2


def test_changes_while_off_send_nothing():
    target = FanState(power=False, speed=4, direction=Direction.EXHAUST, auto=True)
    assert run(target, FanState(power=False)) is None


def test_power_on_applies_stored_targets():
    target = on(speed=3, direction=Direction.EXHAUST, auto=True, setpoint=62)
    p = run(target, FanState(setpoint=60))
    assert p.presses == (
        (Key.POWER,),
        (Key.DIRECT_EXHAUST,),
        (Key.UP,),
        (Key.UP,),
        (Key.AUTO,),
        (Key.UP,),
        (Key.UP,),
    )
    assert p.state == target


def test_power_on_with_auto_off_ignores_setpoint():
    p = run(on(setpoint=75), FanState(setpoint=60))
    assert p.presses == ((Key.POWER,),)
    assert p.state.setpoint == 60


def test_speed_up_wakes_with_duplicate():
    p = run(on(speed=3), on(speed=1))
    assert p.presses == ((Key.UP,), (Key.UP,), (Key.UP,))
    assert p.state.speed == 3


def test_speed_down():
    p = run(on(speed=1), on(speed=4))
    assert p.presses == ((Key.DOWN,), (Key.DOWN,), (Key.DOWN,), (Key.DOWN,))


def test_direction_toggle():
    p = run(on(direction=Direction.EXHAUST), on())
    assert p.presses == ((Key.DIRECT_EXHAUST,), (Key.DIRECT_EXHAUST,))
    assert p.state.direction is Direction.EXHAUST


def test_auto_on_then_setpoint_steps():
    p = run(on(auto=True, setpoint=63), on(setpoint=60))
    assert p.presses == ((Key.AUTO,), (Key.AUTO,), (Key.UP,), (Key.UP,), (Key.UP,))
    assert p.state.auto


def test_auto_on_setpoint_down():
    p = run(on(auto=True, setpoint=60), on(setpoint=62))
    assert p.presses == ((Key.AUTO,), (Key.AUTO,), (Key.DOWN,), (Key.DOWN,))


def test_auto_on_same_setpoint_is_only_auto():
    p = run(on(auto=True, setpoint=70), on(setpoint=70))
    assert p.presses == ((Key.AUTO,), (Key.AUTO,))


def test_auto_off_is_double_auto():
    p = run(on(setpoint=70), on(auto=True, setpoint=70))
    assert p.presses == ((Key.AUTO,), (Key.AUTO, Key.AUTO))
    assert not p.state.auto


def test_setpoint_ignored_with_auto_off():
    assert run(on(setpoint=80), on(setpoint=70)) is None


def test_setpoint_change_with_auto_on_reopens_window():
    p = run(on(auto=True, setpoint=71), on(auto=True, setpoint=70), now=10.0)
    assert p.presses == ((Key.AUTO,), (Key.AUTO,), (Key.UP,))
    assert p.state.setpoint == 71


def test_waits_until_idle_plus_lag_speed():
    assert run(on(speed=2), on(), now=100.0, idle_at=103.0).send_at == 105.0


def test_waits_until_idle_plus_lag_direction():
    assert (
        run(on(direction=Direction.EXHAUST), on(), now=100.0, idle_at=103.0).send_at
        == 105.0
    )


def test_waits_until_idle_plus_lag_power_off():
    assert run(FanState(), on(), now=100.0, idle_at=103.0).send_at == 105.0


def test_waits_until_idle_plus_lag_setpoint():
    assert (
        run(
            on(auto=True, setpoint=61),
            on(auto=True, setpoint=60),
            now=100.0,
            idle_at=103.0,
        ).send_at
        == 105.0
    )


def test_waits_until_idle_plus_lag_auto_on():
    assert run(on(auto=True), on(), now=100.0, idle_at=103.0).send_at == 105.0


def test_waits_until_idle_plus_lag_auto_off():
    assert run(on(), on(auto=True), now=100.0, idle_at=103.0).send_at == 105.0


def test_no_wait_once_idle():
    assert run(on(speed=2), on(), now=100.0, idle_at=90.0).send_at == 100.0


def test_no_wait_for_power_on_from_off():
    assert run(on(speed=2), FanState(), now=100.0, idle_at=103.0).send_at == 100.0


def test_awake_for():
    assert run(on(speed=2), on()).awake_for == 5.0
    assert run(on(direction=Direction.EXHAUST), on()).awake_for == 5.0
    assert run(on(), on(auto=True)).awake_for == 5.0
    assert run(on(auto=True), on()).awake_for == 10.0
    assert run(on(auto=True, setpoint=70), on(auto=True)).awake_for == 10.0
    assert run(on(speed=2, auto=True), FanState()).awake_for == 10.0
    assert run(FanState(), on()).awake_for == 0.0
    assert run(on(), FanState()).awake_for == 5.0


def test_auto_off_with_setpoint_change_keeps_assumed_setpoint():
    p = run(on(setpoint=75), on(auto=True, setpoint=70))
    assert p.presses == ((Key.AUTO,), (Key.AUTO, Key.AUTO))
    assert p.state == on(setpoint=70)


def test_power_on_with_remembered_auto_and_new_setpoint():
    p = run(on(auto=True, setpoint=72), FanState(auto=True, setpoint=70))
    assert p.presses == ((Key.POWER,), (Key.AUTO,), (Key.UP,), (Key.UP,))
    assert p.state == on(auto=True, setpoint=72)


def test_multi_change_order():
    target = on(speed=2, direction=Direction.EXHAUST, auto=True, setpoint=61)
    unit = on(speed=1, auto=True, setpoint=60)
    p = run(target, unit)
    assert p.presses == (
        (Key.DIRECT_EXHAUST,),
        (Key.DIRECT_EXHAUST,),
        (Key.UP,),
        (Key.AUTO,),
        (Key.UP,),
    )
    assert p.state == target


def test_auto_off_after_speed():
    p = run(on(speed=2), on(auto=True))
    assert p.presses == ((Key.UP,), (Key.UP,), (Key.AUTO, Key.AUTO))
