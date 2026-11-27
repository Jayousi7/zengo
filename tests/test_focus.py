"""The focus timer: sessions, breaks, pausing, and the settings for it."""

import pytest

from zengo.behavior.focus import Focus, Plan
from zengo.settings import Settings

PLAN = Plan(focus=100, short_break=20, long_break=50, long_after=3)


def _focus(**kw):
    return Focus(plan=Plan(**{**PLAN.__dict__, **kw}))


def test_a_session_then_a_break_then_back_to_it():
    focus = _focus()
    focus.start(0)
    assert focus.focusing and focus.left(30) == 70
    assert focus.fraction_left(50) == pytest.approx(0.5)
    focus.update(99)
    assert focus.phase == "focus"
    focus.update(100)
    assert focus.on_break and not focus.long_break and focus.left(100) == 20
    focus.update(120)
    assert focus.phase == "waiting"
    assert focus.take_events() == ["focus", "break", "back"]
    focus.start(130)
    assert focus.focusing and focus.left(130) == 100


def test_automatically_the_next_session_starts_by_itself():
    focus = _focus(auto=True)
    focus.start(0)
    focus.update(100)
    focus.update(120)
    assert focus.focusing and focus.left(120) == 100
    assert focus.take_events() == ["focus", "break", "focus"]


def test_a_long_break_after_every_few_sessions():
    focus = _focus(auto=True)
    focus.start(0)
    breaks, t = [], 0.0
    for _ in range(4):
        t = focus.ends_at
        focus.update(t)  # focus over
        breaks.append(focus.long_break)
        focus.update(focus.ends_at)  # break over: the next begins
    assert breaks == [False, False, True, False]


def test_never_a_long_break_if_you_say_so():
    focus = _focus(auto=True, long_after=0)
    focus.start(0)
    for _ in range(6):
        focus.update(focus.ends_at)
        assert not focus.long_break
        focus.update(focus.ends_at)


def test_pausing_stops_the_clock():
    focus = _focus()
    focus.start(0)
    focus.pause(40)
    assert focus.paused and not focus.focusing
    focus.update(500)
    assert focus.phase == "focus" and focus.left(500) == 60
    focus.resume(500)
    assert focus.focusing and focus.left(530) == 30
    focus.update(560)
    assert focus.on_break


def test_stopping_ends_it():
    focus = _focus()
    focus.start(0)
    focus.update(100)
    focus.stop()
    assert focus.phase == "off" and not focus.running and focus.done == 0
    assert focus.take_events()[-1] == "stopped"


def test_a_session_keeps_the_lengths_it_started_with():
    focus = _focus()
    focus.start(0)
    focus.plan = Plan(focus=10)
    assert focus.left(0) == 100
    focus.update(100)
    focus.update(120)
    focus.start(120)
    assert focus.left(120) == 10


def test_after_being_closed_it_picks_up_quietly():
    focus = _focus(auto=True)
    focus.start(0)
    focus.take_events()
    focus.catch_up(110)  # focus ended while he was closed: on his break
    assert focus.on_break and focus.left(110) == 10
    focus.catch_up(5000)  # and the break too: he waits for you, auto or not
    assert focus.phase == "waiting"
    assert focus.take_events() == []


def test_the_focus_settings_and_their_ranges():
    plan = Settings(focus_minutes=50, short_break_minutes=10, next_session="auto").focus_plan()
    assert (plan.focus, plan.short_break, plan.auto) == (3000, 600, True)
    read = Settings.from_json(
        {"focus_minutes": 500, "short_break_minutes": 0, "long_break_minutes": 30,
         "long_after": 0, "next_session": "maybe", "reminder_minutes": 0}
    )  # fmt: skip
    assert read.focus_minutes == 25 and read.short_break_minutes == 5
    assert read.long_break_minutes == 30 and read.long_after == 0
    assert read.next_session == "ask" and read.reminder_minutes == 0
    assert Settings.from_json({"long_after": False, "reminder_minutes": 7}).long_after == 4
    assert Settings.from_json({"reminder_minutes": 7}).reminder_minutes == 50


# --- Remembered between runs -----------------------------------------------------

from zengo.behavior.memory import restore, snapshot  # noqa: E402


def _fresh(ctx):
    from zengo.behavior.context import Context

    return Context(ctx.body, ctx.world, ctx.animator, ctx.config, ctx.rng, clock=ctx.clock)


def test_a_session_under_way_survives_a_restart(ctx):
    now = ctx.clock()
    ctx.focus.plan = PLAN
    ctx.focus.start(now - 30)
    saved = snapshot(ctx)
    later = _fresh(ctx)
    restore(later, saved)
    assert later.focus.focusing and later.focus.left(now) == pytest.approx(70, abs=0.2)
    assert later.focus.session == PLAN
    assert later.focus.take_events() == []


def test_a_paused_session_stays_paused(ctx):
    now = ctx.clock()
    ctx.focus.plan = PLAN
    ctx.focus.start(now - 30)
    ctx.focus.pause(now)
    later = _fresh(ctx)
    restore(later, snapshot(ctx))
    assert later.focus.paused and later.focus.left(now + 9999) == pytest.approx(70)


def test_a_session_that_ended_while_he_was_closed(ctx):
    now = ctx.clock()
    ctx.focus.plan = PLAN
    ctx.focus.start(now - 110)  # focus ended 10 s ago: on the break
    later = _fresh(ctx)
    restore(later, snapshot(ctx))
    assert later.focus.on_break and later.focus.done == 1
    ctx.focus.start(now - 10_000)
    later = _fresh(ctx)
    restore(later, snapshot(ctx))
    assert later.focus.phase == "waiting"


def test_nothing_running_nothing_saved_and_rubbish_ignored(ctx):
    assert snapshot(ctx)["focus"] is None
    data = snapshot(ctx)
    for junk in ({"phase": "nap"}, {"phase": "focus"}, {"phase": "focus", "ends_at": "soon"}):
        later = _fresh(ctx)
        restore(later, {**data, "focus": junk})
        assert later.focus.phase == "off"
