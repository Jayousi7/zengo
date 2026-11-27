"""Bobbing his head along while you type."""

from zengo.behavior.machine import Brain
from zengo.behavior.states import Bob, Fly, FrontIdle, Idle, OnBranch

DT = 1 / 30


def typing(world, brain, seconds: float) -> None:
    """Keys going down every so often, the pointer resting."""
    world.idle = 5.0  # the pointer hasn't moved
    for i in range(round(seconds / DT)):
        world.input_idle = (i % 6) * DT  # a key every 0.2 s
        brain.tick(DT)


def stop_typing(world, brain, seconds: float) -> None:
    for _ in range(round(seconds / DT)):
        world.input_idle = (world.input_idle or 0) + DT
        brain.tick(DT)


def test_sitting_about_he_bobs_along_while_you_type(ctx, world):
    brain = Brain(ctx, Idle())
    typing(world, brain, 1)
    assert isinstance(brain.state, Bob)
    frames = set()
    for i in range(30):
        world.input_idle = (i % 6) * DT
        brain.tick(DT)
        frames.add(ctx.animator.frame)
    assert frames == {"perch", "bob"}  # nodding


def test_he_stops_soon_after_you_do(ctx, world):
    brain = Brain(ctx, Idle())
    typing(world, brain, 1)
    stop_typing(world, brain, 0.5)
    assert isinstance(brain.state, Bob)  # a short pause between words
    stop_typing(world, brain, 1)
    assert not isinstance(brain.state, Bob)


def test_moving_the_mouse_is_not_typing(ctx, world):
    brain = Brain(ctx, Idle())
    world.idle = 0.0  # the pointer is moving: that's the input
    for _ in range(60):
        world.input_idle = 0.0
        brain.tick(DT)
    assert not isinstance(brain.state, Bob)


def test_no_word_from_the_system_means_no_bobbing(ctx, world):
    brain = Brain(ctx, Idle())
    world.idle = 5.0
    world.input_idle = None
    for _ in range(60):
        brain.tick(DT)
    assert not isinstance(brain.state, Bob)


def test_facing_you_he_bobs_facing_you(ctx, world):
    brain = Brain(ctx, FrontIdle())
    typing(world, brain, 1)
    assert isinstance(brain.state, Bob) and ctx.animator.clip_name == "front_bob"


def test_busy_he_does_not_stop_to_bob(ctx, world):
    brain = Brain(ctx, Fly.tour(ctx))
    typing(world, brain, 1)
    assert isinstance(brain.state, Fly)


def test_he_bobs_on_the_branch_and_in_the_cage(ctx, world):
    brain = Brain(ctx, Idle())
    ctx.scenery.grow(ctx)
    for _ in range(45):
        brain.tick(DT)
    brain.transition(Fly.to_branch(ctx))
    while not isinstance(brain.state, OnBranch):
        brain.tick(DT)
    typing(world, brain, 1)
    assert ctx.animator.clip_name == "branch_bob"

    brain = Brain(ctx, Idle())
    ctx.scenery.branch = None
    ctx.body.y = ctx.world.area.bottom
    brain.catch_in(ctx.body.x - 40, ctx.body.y - 80, ctx.body.x + 40, ctx.body.y + 5)
    for _ in range(round(15 / DT)):  # let the tantrum pass
        brain.tick(DT)
    typing(world, brain, 1)
    assert ctx.animator.clip_name == "front_bob"
