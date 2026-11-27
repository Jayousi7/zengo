"""The branch: its life cycle, flying to it, sitting on it and leaving it."""

from dataclasses import replace

import pytest

from zengo.behavior.body import Facing
from zengo.behavior.machine import Brain
from zengo.behavior.states import (
    Fall,
    Fly,
    FrontIdle,
    Idle,
    OnBranch,
    Shake,
    Walk,
    branch_is_inviting,
)
from zengo.sprites.branch import BRANCH, PERCH, TOP_ROW

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


def grow_branch(ctx, brain: Brain):
    branch = ctx.scenery.grow(ctx)
    run(brain, ctx.config.branch_grow_seconds + 0.1)
    assert branch.ready
    return branch


def clips_seen(brain: Brain, ctx, seconds: float) -> set[str]:
    seen = set()
    for _ in range(round(seconds / DT)):
        brain.tick(DT)
        seen.add(ctx.animator.clip_name)
    return seen


# --- Life cycle ------------------------------------------------------------


def test_a_branch_grows_from_a_screen_edge_after_a_while(ctx):
    brain = Brain(ctx, Idle())
    run(brain, 1)
    assert ctx.scenery.branch is None
    ctx.scenery._timer = 0.5  # skip the 10-20 minute wait
    run(brain, 1)
    branch = ctx.scenery.branch
    assert branch is not None and 0 < branch.shown < 1
    area = ctx.world.area
    assert branch.edge in (area.left, area.right)
    low, high = ctx.config.branch_height
    assert area.top + low * area.bottom <= branch.top <= area.top + high * area.bottom
    run(brain, ctx.config.branch_grow_seconds)
    assert branch.ready


def test_left_alone_the_branch_withdraws_and_another_comes_later(ctx):
    brain = Brain(ctx, Idle())
    grow_branch(ctx, brain)
    ctx.scenery._timer = 1.0
    run(brain, 1.2)
    assert ctx.scenery.phase == "retracting"
    run(brain, ctx.config.branch_grow_seconds + 0.1)
    assert ctx.scenery.branch is None
    assert ctx.config.branch_every[0] <= ctx.scenery._timer <= ctx.config.branch_every[1]


def test_the_branch_never_withdraws_while_he_sits_on_it(ctx):
    brain = Brain(ctx, Idle())
    grow_branch(ctx, brain)
    brain.transition(Fly.to_branch(ctx))
    run_until(brain, OnBranch, limit=20)
    ctx.scenery._timer = 0.1
    run(brain, 30)
    assert ctx.scenery.phase == "out"
    assert ctx.scenery.branch is not None


def test_branch_art_leaves_room_to_sit():
    lo, hi = PERCH
    assert set(BRANCH.rows[TOP_ROW][lo : hi + 1]) == {"O"}  # solid bark underfoot
    half_width = 8  # of the front view, either side of the anchor
    for row in BRANCH.rows[:TOP_ROW]:
        assert set(row[lo - half_width : hi + half_width + 1]) <= {"."}  # no leaves on him


# --- Using it --------------------------------------------------------------


def test_flies_to_the_branch_and_sits_facing_you(ctx):
    brain = Brain(ctx, Idle())
    branch = grow_branch(ctx, brain)
    assert branch_is_inviting(ctx)
    brain.transition(Fly.to_branch(ctx))
    run_until(brain, OnBranch, limit=20)
    lo, hi = branch.perch_span(ctx.config)
    assert ctx.body.y == branch.top
    assert lo <= ctx.body.x <= hi
    assert ctx.animator.frame.startswith("branch_")


def test_on_the_branch_he_preens_then_flies_off_into_the_screen(ctx):
    ctx.config = replace(ctx.config, branch_visit=(120.0, 120.0))
    brain = Brain(ctx, Idle())
    branch = grow_branch(ctx, brain)
    brain.transition(Fly.to_branch(ctx))
    run_until(brain, OnBranch, limit=20)
    seen = set()
    while isinstance(brain.state, OnBranch):
        brain.tick(DT)
        seen.add(ctx.animator.clip_name)
    assert {"branch_idle", "branch_preen"} <= seen
    assert isinstance(brain.state, Fly)
    assert ctx.body.facing is Facing(branch.inward)  # launching into the screen
    run_until(brain, Idle, limit=60)
    assert ctx.body.y == ctx.world.area.bottom


def test_sleepy_on_the_branch_he_naps_there(ctx, world):
    brain = Brain(ctx, Idle())
    grow_branch(ctx, brain)
    brain.transition(Fly.to_branch(ctx))
    run_until(brain, OnBranch, limit=20)
    world.hour = 2
    assert "branch_sleep" in clips_seen(brain, ctx, 60)
    assert isinstance(brain.state, OnBranch)


def test_a_poke_on_the_branch_startles_him_but_he_stays(ctx):
    brain = Brain(ctx, Idle())
    grow_branch(ctx, brain)
    brain.transition(Fly.to_branch(ctx))
    run_until(brain, OnBranch, limit=20)
    brain.click()
    brain.tick(DT)
    assert ctx.animator.clip_name == "branch_alert"
    assert isinstance(brain.state, OnBranch)


def test_dropped_onto_the_branch_he_grabs_it(ctx):
    brain = Brain(ctx, Idle())
    branch = grow_branch(ctx, brain)
    lo, hi = branch.perch_span(ctx.config)
    ctx.body.x, ctx.body.y = (lo + hi) / 2, branch.top - ctx.config.px(30)
    brain.transition(Fall())
    run_until(brain, OnBranch, limit=3)
    assert ctx.body.y == branch.top
    assert ctx.animator.clip_name == "branch_fluff"  # settles his feathers first


def test_dropped_beside_the_branch_he_misses_it(ctx):
    brain = Brain(ctx, Idle())
    branch = grow_branch(ctx, brain)
    lo, hi = branch.perch_span(ctx.config)
    far = hi + ctx.config.px(60) if branch.inward > 0 else lo - ctx.config.px(60)
    ctx.body.x, ctx.body.y = far, branch.top - ctx.config.px(30)
    brain.transition(Fall())
    run_until(brain, Shake, limit=10)
    assert ctx.body.y == ctx.world.area.bottom


def test_if_the_branch_goes_while_he_flies_to_it_he_glides_down(ctx):
    brain = Brain(ctx, Idle())
    grow_branch(ctx, brain)
    brain.transition(Fly.to_branch(ctx))
    run(brain, 0.5)
    ctx.scenery.branch = None
    run_until(brain, Shake, limit=10)


def test_a_waiting_branch_draws_him_over(ctx):
    brain = Brain(ctx, Idle())
    grow_branch(ctx, brain)
    for _ in range(round(120 / DT)):
        brain.tick(DT)
        if isinstance(brain.state, Fly) and brain.state.onto == "branch":
            return
    pytest.fail("never flew to the branch")


# --- Front view on the ground ----------------------------------------------


def test_he_sometimes_sits_facing_you_on_the_ground(ctx):
    brain = Brain(ctx, FrontIdle())
    brain.tick(DT)
    assert ctx.animator.frame.startswith("front_")
    run_until(brain, Walk | Idle | Fly | FrontIdle | OnBranch, limit=12)


def test_turning_round_on_the_ground_shows_his_front_for_a_moment(ctx):
    ctx.body.facing = Facing.RIGHT
    brain = Brain(ctx, Idle())
    brain.transition(Walk(target=ctx.body.x - 200))
    brain.tick(DT)
    assert ctx.body.facing is Facing.LEFT
    assert ctx.animator.frame == "front_perch"
    run(brain, 0.3)
    assert ctx.animator.frame != "front_perch"


def test_no_branch_grows_while_he_is_caged_but_it_comes_as_soon_as_he_is_out(ctx):
    brain = Brain(ctx, Idle())
    brain.catch_in(ctx.body.x - 40, ctx.body.y - 80, ctx.body.x + 40, ctx.body.y + 5)
    run(brain, 1)
    ctx.scenery._timer = 2.0  # due in two seconds
    run(brain, 10)
    assert ctx.scenery.branch is None  # held back while he's caged
    assert ctx.scenery._timer < 0  # but the wait wasn't reset
    brain.let_out()
    run(brain, 0.2)
    assert ctx.scenery.branch is not None  # out he comes, and there it grows
