"""Double-click whistles and petting."""

import math

from zengo.behavior.machine import Brain
from zengo.behavior.states import (
    Fly,
    Idle,
    OnBranch,
    Petted,
    Shake,
    Sleep,
    Whistle,
)

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


def stroke(ctx, world, brain: Brain, seconds: float, *, reach: float = 8, period: float = 0.8):
    """Move the pointer gently back and forth over his back, ``reach`` art px each way.

    Returns everything said while stroking.
    """
    said = []
    cx, cy = ctx.body.x, ctx.body.y - ctx.config.px(14)
    for i in range(round(seconds / DT)):
        offset = ctx.config.px(reach) * math.sin(2 * math.pi * i * DT / period)
        world.cursor_pos = (cx + offset, cy)
        brain.tick(DT)
        if ctx.speech is not None:
            said.append(ctx.speech.text)
    return said


# --- Whistling ---------------------------------------------------------------


def test_double_click_gets_a_whistle_in_a_cloud(ctx):
    brain = Brain(ctx, Idle())
    brain.double_click()
    assert isinstance(brain.state, Whistle)
    assert ctx.speech is not None and ctx.speech.text in ctx.config.whistles
    brain.tick(DT)
    assert ctx.animator.clip_name == "whistle"
    run_until(brain, Idle, limit=5)
    run(brain, ctx.config.speech_seconds)
    assert ctx.speech is None  # the cloud has gone


def test_no_whistle_in_mid_air(ctx):
    brain = Brain(ctx, Fly())
    run(brain, 0.3)
    brain.double_click()
    assert isinstance(brain.state, Fly)
    assert ctx.speech is None


def test_he_whistles_on_the_branch_too(ctx):
    brain = Brain(ctx, Idle())
    ctx.scenery.grow(ctx)
    run(brain, ctx.config.branch_grow_seconds + 0.1)
    brain.transition(Fly.to_branch(ctx))
    run_until(brain, OnBranch, limit=20)
    brain.double_click()
    brain.tick(DT)
    assert ctx.animator.clip_name == "branch_whistle"
    assert ctx.speech is not None
    assert isinstance(brain.state, OnBranch)


# --- Petting -----------------------------------------------------------------


def test_gentle_strokes_over_him_are_petting(ctx, world):
    brain = Brain(ctx, Idle())
    said = stroke(ctx, world, brain, 2.0)
    assert isinstance(brain.state, Petted)
    assert ctx.animator.clip_name == "petted"
    assert "♥" in said


def test_when_the_petting_stops_he_shakes_happily(ctx, world):
    brain = Brain(ctx, Idle())
    stroke(ctx, world, brain, 2.0)
    run_until(brain, Shake, limit=4)  # the pointer rests: he's done
    run_until(brain, Idle, limit=3)


def test_petting_carries_on_while_the_strokes_do(ctx, world):
    brain = Brain(ctx, Idle())
    stroke(ctx, world, brain, 6.0)
    assert isinstance(brain.state, Petted)


def test_a_quick_swipe_across_him_is_not_petting(ctx, world):
    brain = Brain(ctx, Idle())
    y = ctx.body.y - ctx.config.px(14)
    for sweep in range(3):  # across and back, quickly, and a pause between
        start, end = ctx.body.x - 150, ctx.body.x + 150
        if sweep % 2:
            start, end = end, start
        for i in range(6):
            world.cursor_pos = (start + (end - start) * i / 5, y)
            brain.tick(DT)
        run(brain, 0.5)
    assert not isinstance(brain.state, Petted)


def test_a_pointer_resting_on_him_is_not_petting(ctx, world):
    brain = Brain(ctx, Idle())
    world.cursor_pos = (ctx.body.x, ctx.body.y - ctx.config.px(14))
    run(brain, 3)
    assert not isinstance(brain.state, Petted)


def test_strokes_somewhere_else_are_not_petting(ctx, world):
    brain = Brain(ctx, Idle())
    far = ctx.config.px(60)
    cx, cy = ctx.body.x + far, ctx.body.y - ctx.config.px(14)
    for i in range(round(2 / DT)):
        world.cursor_pos = (cx + ctx.config.px(8) * math.sin(2 * math.pi * i * DT / 0.8), cy)
        brain.tick(DT)
    assert not isinstance(brain.state, Petted)


def test_petting_wakes_him_gently(ctx, world):
    world.hour = 2
    brain = Brain(ctx, Sleep())
    stroke(ctx, world, brain, 2.0)
    assert isinstance(brain.state, Petted)


def test_petting_on_the_branch(ctx, world):
    brain = Brain(ctx, Idle())
    ctx.scenery.grow(ctx)
    run(brain, ctx.config.branch_grow_seconds + 0.1)
    brain.transition(Fly.to_branch(ctx))
    run_until(brain, OnBranch, limit=20)
    stroke(ctx, world, brain, 2.0)
    assert ctx.animator.clip_name == "branch_petted"
    assert isinstance(brain.state, OnBranch)
