"""The chasing game."""

from dataclasses import replace

from zengo.behavior.chase import WiggleSensor
from zengo.behavior.machine import Brain
from zengo.behavior.states import (
    Bathe,
    BreakCall,
    Chase,
    Crouch,
    Idle,
    Pant,
    Sleep,
)


def _wiggle(ctx, brain, x=None, y=None, seconds=1.0, dt=1 / 30):
    """The pointer darting back and forth by him, fast."""
    x = ctx.body.x + 40 if x is None else x
    y = ctx.area().bottom - 30 if y is None else y
    for i in range(round(seconds / dt)):
        ctx.world.cursor_pos = (x + (25 if i % 3 == 0 else -25), y)
        ctx.world.idle = 0.0
        brain.tick(dt)


def _still(ctx, brain, seconds, dt=1 / 30):
    for _ in range(round(seconds / dt)):
        ctx.world.idle += dt
        brain.tick(dt)


def test_a_quick_wiggle_near_him_starts_a_game(ctx):
    brain = Brain(ctx, Idle())
    _wiggle(ctx, brain)
    assert isinstance(brain.state, Crouch | Chase)


def test_a_slow_stroke_or_a_far_wiggle_doesnt(ctx):
    brain = Brain(ctx, Idle())
    for i in range(60):  # gentle petting speed, over him
        ctx.world.cursor_pos = (ctx.body.x + (4 if i % 6 < 3 else -4), ctx.body.y - 20)
        brain.tick(1 / 30)
    assert not isinstance(brain.state, Crouch | Chase)
    brain = Brain(ctx, Idle())
    _wiggle(ctx, brain, x=ctx.body.x + 900)
    assert not isinstance(brain.state, Crouch | Chase)


def test_not_while_hes_busy_but_a_game_wakes_him(ctx):
    brain = Brain(ctx, Bathe())
    _wiggle(ctx, brain, seconds=0.5)
    assert not isinstance(brain.state, Crouch | Chase)
    brain = Brain(ctx, Sleep())
    _wiggle(ctx, brain)
    assert isinstance(brain.state, Crouch | Chase)


def test_he_hops_after_it_and_pounces_when_it_stops(ctx):
    brain = Brain(ctx, Chase())
    ground = ctx.area().bottom
    target = ctx.body.x + 200
    ctx.world.cursor_pos, ctx.world.idle = (target, ground - 10), 0.0
    heights = []
    for _ in range(90):
        ctx.world.idle = 0.0  # still moving
        brain.tick(1 / 30)
        heights.append(ctx.body.y)
    assert min(heights) < ground  # hops
    assert ctx.body.x > target - 200 + 40
    caught = False
    for _ in range(300):
        ctx.world.idle += 1 / 30
        brain.tick(1 / 30)
        caught |= ctx.speech is not None and ctx.speech.mood == "love"
    assert caught
    assert "trill" in ctx.sounds


def test_up_out_of_reach_he_flies_after_it_unless_damp(ctx):
    ground = ctx.area().bottom
    ctx.world.cursor_pos = (ctx.body.x + 40, ground - 300)
    brain = Brain(ctx, Chase())
    highest = ground
    for _ in range(40):
        ctx.world.idle = 0.0
        brain.tick(1 / 30)
        highest = min(highest, ctx.body.y)
    assert highest < ground - ctx.config.px(20)
    ctx.body.y, ctx.damp = ground, 30.0
    brain = Brain(ctx, Chase())
    highest = ground
    for _ in range(60):
        ctx.world.idle = 0.0
        brain.tick(1 / 30)
        highest = min(highest, ctx.body.y)
    assert highest >= ground - ctx.config.px(6)  # only hops


def test_leave_the_pointer_resting_and_he_gives_up(ctx):
    brain = Brain(ctx, Chase())
    ctx.world.cursor_pos = (ctx.body.x + 600, 300.0)
    _still(ctx, brain, ctx.config.chase_rest + 2)
    assert not isinstance(brain.state, Chase)
    assert ctx.body.y == ctx.area().bottom


def test_after_a_minute_hes_tired_and_pants(ctx):
    ctx.config = replace(ctx.config, chase_seconds=5.0)
    level = ctx.bond.level
    brain = Brain(ctx, Chase())
    seen_pant = False
    for i in range(400):
        ctx.world.cursor_pos = (ctx.body.x + (300 if (i // 60) % 2 else -300), 900.0)
        ctx.world.idle = 0.0
        brain.tick(1 / 30)
        seen_pant |= isinstance(brain.state, Pant)
    assert seen_pant
    assert ctx.bond.level > level


def test_invited_he_waits_for_the_pointer_to_move(ctx):
    brain = Brain(ctx, Crouch(invite=True))
    _still(ctx, brain, 2)
    assert isinstance(brain.state, Crouch)
    ctx.world.idle = 0.0
    brain.tick(1 / 30)
    assert isinstance(brain.state, Chase)
    brain = Brain(ctx, Crouch(invite=True))
    _still(ctx, brain, 7)
    assert isinstance(brain.state, Idle)


def test_the_sensor_needs_speed_and_turns():
    sensor = WiggleSensor()
    assert sensor.min_speed > 300  # faster than any stroke
    assert BreakCall.clip
