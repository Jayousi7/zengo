"""His bath: the dish's comings and goings, and bathing in it."""

import time
from dataclasses import replace

import pytest

from zengo.behavior.bath import SUMMER_SOONER, BathCycle
from zengo.behavior.food import Food
from zengo.behavior.machine import Brain


def _run(brain, seconds, dt=0.1):
    for _ in range(round(seconds / dt)):
        brain.tick(dt)


def test_a_dish_appears_after_a_while_near_him_and_fades_in(ctx):
    ctx.config = replace(ctx.config, bath_every=(10.0, 10.0))
    cycle = BathCycle()
    for _ in range(90):
        cycle.update(ctx, 0.1, occupied=False, free=True)
    assert cycle.dish is None
    for _ in range(15):
        cycle.update(ctx, 0.1, occupied=False, free=True)
    dish = cycle.dish
    assert dish is not None and 0 < dish.shown < 1
    assert dish.y == ctx.area().bottom
    assert 100 <= abs(dish.x - ctx.body.x) <= 190
    for _ in range(round(ctx.config.bath_fade_seconds * 10)):
        cycle.update(ctx, 0.1, occupied=False, free=True)
    assert cycle.phase == "out" and dish.ready


def test_the_dish_goes_after_a_few_minutes(ctx):
    cycle = BathCycle()
    cycle.fill(ctx)
    for _ in range(int((ctx.config.bath_stays[1] + 10) * 10)):
        cycle.update(ctx, 0.1, occupied=False, free=True)
    assert cycle.dish is None and cycle.phase == "waiting"


def test_it_stays_while_hes_in_it(ctx):
    cycle = BathCycle()
    cycle.fill(ctx)
    for _ in range(int((ctx.config.bath_stays[1] + 10) * 10)):
        cycle.update(ctx, 0.1, occupied=True, free=True)
    assert cycle.dish is not None and cycle.dish.ready


def test_no_dish_while_hes_caged_but_it_comes_once_hes_out(ctx):
    cycle = BathCycle()
    cycle._timer = 1.0
    for _ in range(50):
        cycle.update(ctx, 0.1, occupied=False, free=False)
    assert cycle.dish is None
    cycle.update(ctx, 0.1, occupied=False, free=True)
    assert cycle.dish is not None


def test_a_dish_out_when_hes_caged_goes(ctx):
    cycle = BathCycle()
    cycle.fill(ctx).shown = 1.0
    cycle.phase = "out"
    cycle._timer = 100.0
    cycle.update(ctx, 0.1, occupied=False, free=False)
    assert cycle.phase == "going"


def test_the_dish_keeps_off_his_seeds_and_the_screen_edge(ctx):
    ctx.body.x = 900
    ctx.food = Food(1100, ctx.area().bottom)
    dish = BathCycle().fill(ctx)
    assert dish.x < ctx.body.x  # the seeds are on the other side
    ctx.food, ctx.body.x = None, ctx.area().right - 40
    dish = BathCycle().fill(ctx)
    assert dish.x < ctx.body.x  # the room is that way


def _july() -> float:
    return time.mktime((2026, 7, 15, 12, 0, 0, 0, 0, -1))


def test_baths_come_sooner_in_summer(ctx):
    ctx.config = replace(ctx.config, bath_every=(100.0, 100.0))
    ctx.clock = _july
    assert BathCycle()._wait(ctx) == pytest.approx(100 * SUMMER_SOONER)
    ctx.seasons.enabled = False
    assert BathCycle()._wait(ctx) == 100


def test_the_bath_now_flag(make_pet):
    pet = make_pet(bath_now=True)
    assert pet._brain.ctx.bath.dish is not None
    pet._brain.tick(0.5)
    pet._render()
    assert pet._bath.isVisible()


# --- Bathing ---------------------------------------------------------------------

from zengo.behavior.states import (  # noqa: E402
    Bathe,
    Fly,
    Idle,
    Preen,
    Walk,
    choose_activity,
    go_to_bath,
    go_to_food,
)
from zengo.behavior.voice import Voice  # noqa: E402


def _bath_out(ctx, x=1100.0):
    dish = BathCycle().fill(ctx)
    ctx.bath.dish, ctx.bath.phase = dish, "out"
    ctx.bath._timer = 1000.0
    dish.x, dish.shown = x, 1.0
    return dish


def test_he_walks_over_and_hops_in(ctx):
    dish = _bath_out(ctx)
    brain = Brain(ctx, initial=go_to_bath(ctx))
    assert isinstance(brain.state, Walk) and brain.state.holds_bath
    for _ in range(400):
        brain.tick(0.05)
        if isinstance(brain.state, Bathe):
            break
    assert isinstance(brain.state, Bathe)
    for _ in range(12):
        brain.tick(0.05)
    assert ctx.body.x == pytest.approx(dish.x)
    assert ctx.body.y == pytest.approx(ctx.area().bottom)


def test_a_whole_bath(ctx):
    dish = _bath_out(ctx, x=ctx.body.x)
    brain = Brain(ctx, initial=Bathe())
    drops = 0
    for _ in range(300):
        brain.tick(0.05)
        drops = max(drops, len(ctx.effects.particles))
        if not isinstance(brain.state, Bathe):
            break
    assert isinstance(brain.state, Preen)
    assert drops >= 10  # splashing, and shaking himself dry
    assert dish.used and not ctx.bath.usable
    assert ctx.damp > 0
    assert ctx.body.y == ctx.area().bottom
    assert abs(ctx.body.x - dish.x) > ctx.config.px(10)  # hopped out the far side
    assert ctx.speech is not None


def test_the_dish_waits_for_him_to_finish(ctx):
    _bath_out(ctx, x=ctx.body.x)
    ctx.bath._timer = 0.01
    brain = Brain(ctx, initial=Bathe())
    for _ in range(40):
        brain.tick(0.05)
    assert ctx.bath.phase == "out"


def test_if_the_dish_goes_he_lands_on_his_feet(ctx):
    _bath_out(ctx, x=ctx.body.x)
    brain = Brain(ctx, initial=Bathe())
    for _ in range(20):
        brain.tick(0.05)
    ctx.bath.dish = None
    brain.tick(0.05)
    assert not isinstance(brain.state, Bathe)
    assert ctx.body.y == ctx.area().bottom


def test_he_heads_for_a_new_bath(ctx):
    _bath_out(ctx)
    picks = [type(choose_activity(ctx)).__name__ for _ in range(60)]
    assert picks.count("Walk") > 20


def test_he_flies_to_a_far_bath(ctx):
    _bath_out(ctx, x=200)
    ctx.body.x = 1700
    flight = go_to_bath(ctx)
    assert isinstance(flight, Fly) and flight.holds_bath


# --- Damp ------------------------------------------------------------------------


def test_damp_he_never_flies_off(ctx):
    ctx.damp = 30.0
    ctx.world.idle = 5.0
    ctx.world.cursor_pos = (1000.0, 600.0)  # an inviting pointer
    ctx.scenery.grow(ctx).shown = 1.0
    for _ in range(200):
        assert not isinstance(choose_activity(ctx), Fly)


def test_damp_he_walks_to_far_seeds(ctx):
    from zengo.behavior.food import Food

    ctx.damp = 30.0
    ctx.food = Food(100, ctx.area().bottom)
    ctx.food.pile.add_stack()
    assert isinstance(go_to_food(ctx), Walk)


def test_damp_he_wont_hide_and_walks_when_called(ctx):
    brain = Brain(ctx)
    ctx.damp = 30.0
    ctx.body.x = 300
    assert not brain.can_hide()
    assert not brain.hide()
    assert ctx.speech is not None
    brain.summon()
    assert isinstance(brain.state, Walk)


def test_he_dries_off(ctx):
    brain = Brain(ctx, initial=Idle())
    ctx.damp = 1.0
    for _ in range(12):
        brain.tick(0.1)
    assert ctx.damp == 0
    assert brain.can_hide()


def test_an_old_phrases_file_still_has_something_for_after_a_bath():
    old = Voice(phrases={"random": ("hi",)})
    assert old.lines("bathed")
