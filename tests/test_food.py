"""Feeding Zengo sunflower seeds."""

import pytest

from zengo.behavior.food import PECK_REACH
from zengo.behavior.machine import Brain
from zengo.behavior.states import (
    Caged,
    Eat,
    Fall,
    Fly,
    Idle,
    OnBranch,
    Shake,
    Sleep,
    Walk,
)
from zengo.sprites.food import MAX_SEEDS

DT = 1 / 30


def run(brain: Brain, seconds: float) -> None:
    for _ in range(round(seconds / DT)):
        brain.tick(DT)


def run_until(brain: Brain, kind: type, limit: float = 60.0) -> None:
    for _ in range(round(limit / DT)):
        brain.tick(DT)
        if isinstance(brain.state, kind):
            return
    raise AssertionError(f"never reached {kind.__name__}; stuck in {brain.state!r}")


def test_seeds_go_down_in_front_of_him_and_he_is_delighted(ctx):
    brain = Brain(ctx, Idle())
    brain.feed()
    food = ctx.food
    assert food is not None and food.seeds == MAX_SEEDS
    assert food.y == ctx.world.area.bottom
    assert food.x > ctx.body.x  # he faces right: in front of him
    assert ctx.speech.mood == "love"


def test_he_walks_over_and_pecks_them_up_one_by_one(ctx):
    brain = Brain(ctx, Idle())
    brain.feed()
    brain.tick(DT)
    assert isinstance(brain.state, Walk)
    run_until(brain, Eat, limit=10)
    food = ctx.food
    assert ctx.body.x == pytest.approx(food.x - ctx.config.px(PECK_REACH), abs=1)  # beak on it
    assert ctx.animator.clip_name == "eat"
    seeds = []
    while ctx.food is not None:
        brain.tick(DT)
        if ctx.food is not None:
            seeds.append(ctx.food.seeds)
    assert seeds == sorted(seeds, reverse=True) and len(set(seeds)) == MAX_SEEDS
    assert isinstance(brain.state, Shake)  # pleased with himself
    assert ctx.speech.text.startswith("yum")
    run_until(brain, Idle, limit=3)


def test_from_the_branch_he_flies_down_for_seeds(ctx):
    brain = Brain(ctx, Idle())
    ctx.scenery.grow(ctx)
    run(brain, ctx.config.branch_grow_seconds + 0.1)
    brain.transition(Fly.to_branch(ctx))
    run_until(brain, OnBranch, limit=20)
    brain.feed()
    brain.tick(DT)
    assert isinstance(brain.state, Fly) and brain.state.onto == "food"
    run_until(brain, Eat, limit=20)
    assert ctx.body.y == ctx.world.area.bottom


def test_held_he_eats_once_he_has_landed(ctx):
    brain = Brain(ctx, Idle())
    brain.grab(ctx.body.x, ctx.body.y - 30)
    brain.drag(ctx.body.x, ctx.body.y - 300)
    run(brain, 1)
    brain.feed()
    run(brain, 0.5)
    assert ctx.food is not None and ctx.food.seeds == MAX_SEEDS  # can't reach them yet
    brain.release()
    assert isinstance(brain.state, Fall)
    run_until(brain, Eat, limit=15)


def test_seeds_wake_him(ctx, world):
    world.hour = 2
    brain = Brain(ctx, Sleep())
    brain.feed()
    brain.tick(DT)
    assert not isinstance(brain.state, Sleep)


def test_more_seeds_top_up_the_pile(ctx):
    brain = Brain(ctx, Idle())
    brain.feed()
    run_until(brain, Eat, limit=10)
    run(brain, 3)
    assert ctx.food.seeds < MAX_SEEDS
    brain.feed()
    assert ctx.food.seeds == MAX_SEEDS


def test_caged_his_seeds_go_on_the_tray_and_calm_him(ctx):
    brain = Brain(ctx, Idle())
    brain.catch_in(ctx.body.x - 40, ctx.body.y - 80, ctx.body.x + 40, ctx.body.y + 5)
    run(brain, 0.5)
    brain.feed()
    food, cage = ctx.food, ctx.cage
    assert food.in_cage and (food.x, food.y) == (cage.x, cage.y)
    brain.tick(DT)
    assert ctx.animator.clip_name == "front_eat"
    assert isinstance(brain.state, Caged)
    run(brain, MAX_SEEDS * 1.1)
    assert ctx.food is None
    assert ctx.speech.text.startswith("yum")


def test_seeds_on_the_tray_travel_with_the_cage(ctx):
    brain = Brain(ctx, Idle())
    brain.catch_in(ctx.body.x - 40, ctx.body.y - 80, ctx.body.x + 40, ctx.body.y + 5)
    brain.feed()
    cage = ctx.cage
    brain.cage_grab(cage.x, cage.y - 30)
    brain.cage_drag(cage.x + 200, cage.y - 230)
    brain.tick(DT)
    assert (ctx.food.x, ctx.food.y) == (cage.shown_x, cage.y)


def test_seeds_near_the_screen_edge_are_still_within_his_reach(ctx):
    ctx.body.x = ctx.world.area.right - ctx.margin
    brain = Brain(ctx, Idle())
    brain.feed()
    run_until(brain, Eat, limit=10)
    assert ctx.body.x >= ctx.world.area.left + ctx.margin
    assert ctx.body.x <= ctx.world.area.right - ctx.margin
