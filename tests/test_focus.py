"""The focus timer: sessions, breaks, pausing, and the settings for it."""

import itertools

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


# --- How he behaves while you focus ---------------------------------------------------

from zengo.behavior.food import Food  # noqa: E402
from zengo.behavior.machine import Brain  # noqa: E402
from zengo.behavior.states import FocusRest, Idle, Walk  # noqa: E402


class Clock:
    def __init__(self, start: float) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def _brain(ctx, initial=None):
    clock = Clock(ctx.clock())
    ctx.clock = clock
    ctx.focus.plan = Plan(focus=600, short_break=60, long_break=120)
    return Brain(ctx, initial or Idle()), clock


def _run(brain, clock, seconds, dt=0.1):
    for _ in range(round(seconds / dt)):
        clock.now += dt
        brain.tick(dt)


def test_he_settles_by_the_screen_edge_and_dozes(ctx):
    brain, clock = _brain(ctx)
    ctx.focus.start(clock.now)
    _run(brain, clock, 0.1)
    going = brain.state
    assert getattr(going, "then", None) == "rest" or getattr(going, "onto", None) == "rest"
    _run(brain, clock, 120)
    assert isinstance(brain.state, FocusRest)
    area = ctx.area()
    assert min(ctx.body.x - area.left, area.right - ctx.body.x) < ctx.margin + ctx.config.px(20)


def test_typing_doesnt_stir_him_and_he_makes_no_sound(ctx):
    brain, clock = _brain(ctx, FocusRest())
    ctx.focus.start(clock.now)
    ctx.world.input_idle, ctx.world.idle = 0.0, 5.0  # typing away
    sounds = []
    for _ in range(3000):
        clock.now += 0.1
        brain.tick(0.1)
        sounds += ctx.sounds
        ctx.sounds.clear()
        ctx.world.input_idle = 0.0
    assert isinstance(brain.state, FocusRest)
    assert sounds == []


def test_he_doesnt_ask_for_food_till_the_break_and_isnt_put_out(ctx):
    brain, clock = _brain(ctx)
    ctx.focus.start(clock.now)
    ctx.hunger.hungry = True
    level = ctx.bond.level
    _run(brain, clock, 300)
    assert ctx.speech is None or "feed" not in ctx.speech.text
    assert ctx.bond.level >= level - 0.002
    assert brain._asks == 0


def test_seeds_you_put_out_he_still_eats(ctx):
    brain, clock = _brain(ctx)
    ctx.focus.start(clock.now)
    ctx.hunger.hungry = True
    ctx.food = Food(ctx.body.x + 60, ctx.area().bottom)
    ctx.food.pile.add_stack()
    _run(brain, clock, 30)
    assert ctx.food is None or ctx.food.pile.seeds < 8


def test_no_bath_and_no_toys_while_you_focus(ctx):
    from zengo.behavior.states import choose_activity

    brain, clock = _brain(ctx)
    ctx.toys.put_out(frozenset({"mirror"}))
    ctx.bath._timer = 1.0
    ctx.focus.start(clock.now)
    _run(brain, clock, 60)
    assert ctx.bath.dish is None
    picks = {type(choose_activity(ctx)).__name__ for _ in range(100)}
    assert picks <= {"Walk", "FocusRest", "Fly"}


def test_pausing_or_stopping_lets_him_up(ctx):
    brain, clock = _brain(ctx, FocusRest())
    ctx.focus.start(clock.now)
    _run(brain, clock, 1)
    ctx.focus.stop()
    _run(brain, clock, 0.2)
    assert not isinstance(brain.state, FocusRest)


# --- Break time and back to it ----------------------------------------------------------

from zengo.behavior.cage import Cage  # noqa: E402
from zengo.behavior.states import BreakCall, Caged, Stretch  # noqa: E402


def _to_break(ctx, initial=None):
    brain, clock = _brain(ctx, initial or FocusRest())
    ctx.focus.start(clock.now)
    _run(brain, clock, 1)
    ctx.focus.ends_at = clock.now + 0.05
    return brain, clock


def test_at_the_break_he_stretches_comes_to_you_and_calls(ctx):
    ctx.world.cursor_pos = (ctx.body.x + 300, 500.0)
    brain, clock = _to_break(ctx)
    level = ctx.bond.level
    _run(brain, clock, 0.2)
    assert isinstance(brain.state, Stretch)
    assert ctx.bond.level > level  # a session done together
    called = False
    for _ in range(400):
        clock.now += 0.05
        brain.tick(0.05)
        called |= isinstance(brain.state, BreakCall)
        if called:
            break
    assert called
    assert abs(ctx.body.x - ctx.world.cursor_pos[0]) < ctx.config.px(20)
    assert "break" in ctx.sounds
    assert ctx.speech is not None


def test_caged_he_calls_from_the_cage(ctx):
    ctx.cage = Cage(x=ctx.body.x, y=ctx.body.y)
    ctx.cage.mount = "ground"
    brain, clock = _to_break(ctx, Caged(just_caught=False))
    _run(brain, clock, 0.3)
    assert isinstance(brain.state, Caged)
    assert "break" in ctx.sounds


def test_hidden_he_stays_hidden(ctx):
    from zengo.behavior.states import Away

    brain, clock = _to_break(ctx, Away())
    _run(brain, clock, 2)
    assert brain.away and "break" not in ctx.sounds


def test_he_suggests_something_about_one_break_in_three_never_twice_running(ctx):
    suggested, kinds = [], set()
    for i in range(60):
        ctx.bath.dish, ctx.bath.phase = None, "waiting"
        ctx.rng.seed(i)
        call = BreakCall()
        call.enter(ctx)
        suggested.append(bool(call.suggestion))
        if call.suggestion:
            kinds.add("chase" if call.game else "bath")
            assert call.game or ctx.bath.dish is not None
    assert kinds == {"bath", "chase"}
    assert 10 <= sum(suggested) <= 30
    assert not any(a and b for a, b in itertools.pairwise(suggested))


def test_damp_he_walks_to_you(ctx):
    from zengo.behavior.states import go_to_you

    ctx.damp = 30.0
    ctx.world.cursor_pos = (ctx.body.x + 800, 500.0)
    going = go_to_you(ctx)
    assert isinstance(going, Walk) and going.then == "break"


def test_pointer_on_another_screen_he_calls_from_where_he_is(ctx):
    from zengo.behavior.states import go_to_you
    from zengo.world import Area

    ctx.world.area_at = lambda x, y: (
        Area(0, 0, 1920, 1040) if x < 1920 else Area(1920, 0, 3840, 1040)
    )
    ctx.world.cursor_pos = (2500.0, 500.0)
    assert isinstance(go_to_you(ctx), BreakCall)


def test_after_the_break_he_asks_back_to_it_and_a_button_waits(make_pet):
    pet = make_pet()
    ctx = pet._brain.ctx
    clock = Clock(ctx.clock())
    ctx.clock = clock
    pet.change_settings(Settings(focus_minutes=5, short_break_minutes=1))
    pet.start_focus()
    assert ctx.focus.focusing and ctx.focus.session.focus == 300
    clock.now += 301
    pet._brain.tick(0.1)
    assert ctx.focus.on_break
    clock.now += 61
    pet._brain.tick(0.1)
    pet._render()
    assert ctx.focus.phase == "waiting"
    assert ctx.speech is not None
    assert pet._start_button.isVisible()
    pet._start_button.clicked.emit()
    assert ctx.focus.focusing
    pet._render()
    assert not pet._start_button.isVisible()
    pet.pause_focus()
    assert ctx.focus.paused
    pet.pause_focus()
    assert ctx.focus.focusing
    pet.stop_focus()
    assert ctx.focus.phase == "off"


def test_waiting_he_asks_again_now_and_then_without_a_sound(ctx):
    brain, clock = _brain(ctx)
    ctx.focus.start(clock.now)
    ctx.focus.update(clock.now + 600)
    ctx.focus.update(clock.now + 660)
    ctx.speech = None
    asks = 0
    for _ in range(round(200 / 0.1)):
        clock.now += 0.1
        had = ctx.speech
        brain.tick(0.1)
        if ctx.speech is not None and ctx.speech is not had and "?" in ctx.speech.text:
            asks += 1
        brain.ctx.sounds.clear()
    assert asks >= 2


def test_sessions_and_games_cant_be_farmed_for_his_bond(ctx):
    start = ctx.bond.level
    for _ in range(40):
        ctx.bond.played(ctx.config, ctx.config.bond_focus)
        ctx.bond.played(ctx.config, ctx.config.bond_chase)
    assert ctx.bond.level - start <= ctx.config.bond_toy_per_hour + 1e-9
