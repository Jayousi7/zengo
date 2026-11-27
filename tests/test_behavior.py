import pytest

from zengo.behavior.body import Facing
from zengo.behavior.machine import Brain
from zengo.behavior.states import (
    STEPPING_FRAMES,
    Alert,
    Dragged,
    Fall,
    Fly,
    Glide,
    Idle,
    Preen,
    Shake,
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


def pick_up(ctx, brain: Brain, dx: float, dy: float, settle: float = 3.0):
    """Grab Zengo by the back, move the mouse by (dx, dy) and hold still."""
    grab_x, grab_y = ctx.body.x, ctx.body.y - 30
    brain.grab(grab_x, grab_y)
    brain.drag(grab_x + dx, grab_y + dy)
    run(brain, settle)
    return ctx.body.x - dx, ctx.body.y - dy  # where the body was picked up from, plus sag


def test_held_pet_lags_behind_the_mouse_then_hangs_below_it(ctx):
    brain = Brain(ctx)
    start = (ctx.body.x, ctx.body.y)
    brain.grab(start[0], start[1] - 30)
    assert isinstance(brain.state, Dragged)
    brain.drag(start[0] + 200, start[1] - 30 - 400)

    brain.tick(DT)
    assert 0 < ctx.body.x - start[0] < 200  # on his way, not teleported

    run(brain, 3)
    assert ctx.body.x == pytest.approx(start[0] + 200, abs=1)
    sag = ctx.body.y - (start[1] - 400)
    assert 0 < sag < ctx.config.px(6)  # hangs a little below the grab point


def test_moving_him_fast_makes_him_flap_holding_still_calms_him(ctx):
    brain = Brain(ctx)
    brain.grab(ctx.body.x, ctx.body.y - 30)
    brain.drag(ctx.body.x + 300, ctx.body.y - 330)
    run(brain, 0.2)
    assert ctx.animator.clip_name == "flutter"
    run(brain, 3)
    assert ctx.animator.clip_name == "held"


def test_drop_from_height_glides_down_and_shakes_it_off(ctx):
    brain = Brain(ctx)
    pick_up(ctx, brain, 0, -400)
    brain.release()
    assert isinstance(brain.state, Fall)
    run_until(brain, Glide, limit=2)
    run_until(brain, Shake, limit=10)
    assert ctx.body.y == ctx.world.area.bottom
    run_until(brain, Idle, limit=3)


def test_low_drop_flutters_straight_down_without_gliding(ctx):
    brain = Brain(ctx)
    pick_up(ctx, brain, 0, -ctx.config.px(12))
    x = ctx.body.x
    brain.release()
    for _ in range(round(3 / DT)):
        brain.tick(DT)
        assert not isinstance(brain.state, Glide)
        if isinstance(brain.state, Shake):
            break
    assert ctx.body.y == ctx.world.area.bottom
    assert ctx.body.x == pytest.approx(x, abs=1)


def fling(ctx, brain: Brain, cursor: tuple[float, float], dx: float, seconds: float = 0.1):
    """Sweep the mouse sideways by ``dx`` over ``seconds``, then let go."""
    steps = round(seconds / DT)
    x, y = cursor
    for i in range(1, steps + 1):
        brain.drag(x + dx * i / steps, y)
        brain.tick(DT)
    brain.release()


def test_throw_carries_him_onwards(ctx):
    brain = Brain(ctx)
    pick_up(ctx, brain, -300, -300)
    release_x = ctx.body.x
    fling(ctx, brain, cursor=(ctx.body.x, ctx.body.y - 30), dx=150)
    assert isinstance(brain.state, Fall)
    assert ctx.body.vx > 0
    run_until(brain, Shake, limit=10)
    assert ctx.body.x > release_x + 150
    assert ctx.body.x <= ctx.world.area.right - ctx.margin


def test_wild_fling_is_capped_and_stays_on_screen(ctx):
    brain = Brain(ctx)
    pick_up(ctx, brain, -600, -300)
    fling(ctx, brain, cursor=(ctx.body.x, ctx.body.y - 30), dx=-3000)
    speed_limit = ctx.config.px(ctx.config.max_throw_speed)
    brain.tick(DT)
    assert abs(ctx.body.vx) <= speed_limit
    run_until(brain, Shake, limit=10)
    assert ctx.world.area.left + ctx.margin <= ctx.body.x


def test_clicks_are_ignored_while_held_or_airborne(ctx):
    brain = Brain(ctx)
    brain.grab(ctx.body.x, ctx.body.y)
    brain.click()
    assert isinstance(brain.state, Dragged)

    brain = Brain(ctx, Fly())
    run(brain, 0.3)
    brain.click()
    assert isinstance(brain.state, Fly)


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
