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
    brain = Brain(ctx)
    _run(brain, 9)
    assert ctx.bath.dish is None
    _run(brain, 1.5)
    dish = ctx.bath.dish
    assert dish is not None and 0 < dish.shown < 1
    assert dish.y == ctx.area().bottom
    assert 100 <= abs(dish.x - ctx.body.x) <= 190
    _run(brain, ctx.config.bath_fade_seconds)
    assert ctx.bath.phase == "out" and dish.ready


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
