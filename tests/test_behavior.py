import pytest

from zengo.behavior.body import Facing
from zengo.behavior.machine import Brain
from zengo.behavior.states import (
    STEPPING_FRAMES,
    Alert,
    Dragged,
    Fall,
    Fly,
    Idle,
    Preen,
    Sleep,
    Walk,
    flight_profile,
)
from zengo.world import Area

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


def test_idle_eventually_does_something_else(ctx):
    brain = Brain(ctx)
    run_until(brain, Walk | Preen | Fly | Sleep)


def test_walk_reaches_target_and_returns_to_idle(ctx):
    brain = Brain(ctx, Walk(target=1100))
    assert ctx.body.facing is Facing.RIGHT
    run_until(brain, Idle)
    assert ctx.body.x == 1100
    assert ctx.body.y == ctx.world.area.bottom


def test_walk_target_is_kept_on_screen(ctx):
    brain = Brain(ctx, Walk(target=-500))
    run_until(brain, Idle)
    assert ctx.body.x == ctx.margin


def test_idle_watches_nearby_cursor(ctx, world):
    brain = Brain(ctx)
    world.cursor_pos = (ctx.body.x - 50, ctx.body.y - 50)
    brain.tick(DT)
    assert ctx.body.facing is Facing.LEFT


def test_fly_lands_on_ground_elsewhere(ctx):
    start = ctx.body.x
    brain = Brain(ctx, Fly())
    run(brain, 0.3)
    assert ctx.body.y < ctx.world.area.bottom  # airborne mid-flight
    run_until(brain, Idle)
    assert ctx.body.y == ctx.world.area.bottom
    assert abs(ctx.body.x - start) >= ctx.config.px(60)


def test_click_startles_then_settles(ctx):
    brain = Brain(ctx, Sleep())
    brain.click()
    assert isinstance(brain.state, Alert)
    run_until(brain, Idle, limit=5)


def test_drag_moves_body_then_drop_falls_to_ground(ctx):
    brain = Brain(ctx)
    grab_x, grab_y = ctx.body.x, ctx.body.y - 30
    brain.grab(grab_x, grab_y)
    assert isinstance(brain.state, Dragged)

    brain.drag(grab_x + 200, grab_y - 400)
    brain.tick(DT)
    assert (ctx.body.x, ctx.body.y) == (grab_x + 200, ctx.world.area.bottom - 400)

    brain.release()
    assert isinstance(brain.state, Fall)
    run_until(brain, Alert, limit=10)
    assert ctx.body.y == ctx.world.area.bottom


def test_clicks_are_ignored_while_held(ctx):
    brain = Brain(ctx)
    brain.grab(ctx.body.x, ctx.body.y)
    brain.click()
    assert isinstance(brain.state, Dragged)


def test_sleepy_after_user_inactivity(ctx, world):
    world.idle = ctx.config.sleep_after
    brain = Brain(ctx)
    run_until(brain, Sleep, limit=120)


def test_sleep_ends_when_user_returns_by_day(ctx, world):
    world.idle = 999
    brain = Brain(ctx, Sleep())
    run(brain, 5)
    assert isinstance(brain.state, Sleep)
    world.idle = 0
    brain.tick(DT)
    assert isinstance(brain.state, Idle)


def test_night_nap_ignores_user_activity(ctx, world):
    world.hour = 2
    brain = Brain(ctx, Sleep())
    run(brain, 30)
    assert isinstance(brain.state, Sleep)


def test_grounded_pet_follows_ground_when_desktop_changes(ctx, world):
    brain = Brain(ctx)
    world.area = Area(0, 0, 800, 600)  # resolution drop / panel moved
    brain.tick(DT)
    assert ctx.body.y == 600
    assert ctx.body.x == 800 - ctx.margin


def test_flight_profile_starts_and_ends_on_the_ground():
    assert flight_profile(0.0) == (0.0, 0.0)
    progress, height = flight_profile(1.0)
    assert progress == pytest.approx(1.0) and height == pytest.approx(0.0, abs=1e-9)


def test_flight_climbs_fast_and_lands_shallow():
    heights = [flight_profile(i / 100)[1] for i in range(101)]
    assert max(heights) == pytest.approx(1.0)
    assert heights.index(max(heights)) < 50  # peak in the first half: powered climb
    climb = heights[5] - heights[0]
    landing = heights[95] - heights[100]
    assert climb > 3 * landing  # leaves steeply, arrives at a glide


def test_flight_clip_follows_phase(ctx):
    brain = Brain(ctx, Fly())
    seen = []
    for _ in range(400):
        brain.tick(DT)
        if not isinstance(brain.state, Fly):
            break
        if not seen or seen[-1] != ctx.animator.clip_name:
            seen.append(ctx.animator.clip_name)
    assert seen == ["fly", "glide", "flare"]


def test_walking_moves_only_while_a_foot_is_lifted(ctx):
    """The frame on screen after a tick decides whether that tick moved the body."""
    brain = Brain(ctx, Walk(target=1500))
    for _ in range(60):
        before = ctx.body.x
        brain.tick(DT)
        moved = ctx.body.x != before
        assert moved == (ctx.animator.frame in STEPPING_FRAMES), ctx.animator.frame
