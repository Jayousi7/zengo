"""The seasons on him: snow, leaves, puffing up, song, panting."""

import time

from zengo.behavior.machine import Brain
from zengo.behavior.states import Idle, OnBranch, Puffed, Whistle, choose_activity


def _in(month, hour=12):
    return lambda: time.mktime((2026, month, 15, hour, 0, 0, 0, 0, -1))


def _branch(ctx):
    branch = ctx.scenery.grow(ctx)
    branch.shown = 1.0
    ctx.scenery.phase = "out"
    ctx.scenery._timer = 1000.0
    return branch


def _kinds(ctx):
    return {p.kind for p in ctx.effects.particles}


def _on_branch(ctx):
    branch = _branch(ctx)
    lo, hi = branch.perch_span(ctx.config)
    ctx.body.x, ctx.body.y = (lo + hi) / 2, branch.top
    return Brain(ctx, initial=OnBranch())


def test_snow_drifts_past_the_branch_in_winter(ctx):
    ctx.clock = _in(1)
    brain = _on_branch(ctx)
    for _ in range(100):
        brain.tick(0.1)
    assert "snow" in _kinds(ctx)
    assert all(p.y < ctx.area().bottom for p in ctx.effects.particles)


def test_no_snow_on_the_ground_or_in_summer_or_with_seasons_off(ctx):
    ctx.clock = _in(1)
    brain = Brain(ctx)
    for _ in range(100):
        brain.tick(0.1)
    assert "snow" not in _kinds(ctx)
    ctx.clock = _in(7)
    brain = _on_branch(ctx)
    for _ in range(100):
        brain.tick(0.1)
    assert "snow" not in _kinds(ctx)


def test_leaves_fall_from_the_branch_in_autumn(ctx):
    ctx.clock = _in(10)
    _branch(ctx)
    brain = Brain(ctx)
    for _ in range(200):
        brain.tick(0.1)
    assert "leaf" in _kinds(ctx)
    ctx.effects.clear()
    ctx.seasons.enabled = False
    for _ in range(200):
        brain.tick(0.1)
    assert "leaf" not in _kinds(ctx)


def _picks(ctx, n=400):
    return [type(choose_activity(ctx)) for _ in range(n)]


def test_he_puffs_up_in_winter_only(ctx):
    ctx.clock = _in(1)
    assert Puffed in _picks(ctx)
    ctx.clock = _in(7)
    assert Puffed not in _picks(ctx)


def test_he_sings_more_in_spring(ctx):
    ctx.clock = _in(4)
    assert Whistle in _picks(ctx)
    ctx.clock = _in(10)
    assert Whistle not in _picks(ctx)


def test_he_pants_on_a_summer_afternoon(ctx):
    ctx.clock = _in(7)
    ctx.world.hour = 15
    Idle().enter(ctx)
    assert ctx.animator.clip_name == "pant"
    ctx.world.hour = 9
    Idle().enter(ctx)
    assert ctx.animator.clip_name == "idle"
    ctx.clock, ctx.world.hour = _in(1), 15
    Idle().enter(ctx)
    assert ctx.animator.clip_name == "idle"


def test_puffed_up_he_settles_back_after_a_while(ctx):
    brain = Brain(ctx, initial=Puffed())
    assert ctx.animator.clip_name == "puffed"
    for _ in range(150):
        brain.tick(0.1)
    assert not isinstance(brain.state, Puffed)


def test_spring_brings_more_chirps(ctx):
    def chirps(month):
        ctx.clock = _in(month)
        ctx.rng.seed(7)
        brain = Brain(ctx, initial=Idle())
        count = 0
        for _ in range(3000):
            brain.tick(0.1)
            count += sum(s.startswith("chirp") for s in ctx.sounds)
            ctx.sounds.clear()
            if not isinstance(brain.state, Idle):
                brain.transition(Idle())
        return count

    assert chirps(4) > chirps(10)
