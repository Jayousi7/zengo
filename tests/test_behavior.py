import pytest

from zengo.behavior.body import Facing
from zengo.behavior.machine import Brain
from zengo.behavior.states import (
    STEPPING_FRAMES,
    Alert,
    CursorPerch,
    Dragged,
    Fall,
    Fly,
    Glide,
    Idle,
    Preen,
    Shake,
    Sleep,
    Walk,
    cursor_is_inviting,
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
    assert ctx.body.x == pytest.approx(start[0] + 200, abs=ctx.config.px(2))  # sways gently
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


def fly_and_record(brain: Brain, ctx, limit: float = 60.0):
    """Run a flight to its end; return the positions and the clips it showed, in order."""
    path, clips = [], []
    for _ in range(round(limit / DT)):
        brain.tick(DT)
        if not isinstance(brain.state, Fly):
            return path, clips
        path.append((ctx.body.x, ctx.body.y))
        if not clips or clips[-1] != ctx.animator.clip_name:
            clips.append(ctx.animator.clip_name)
    raise AssertionError("the flight never ended")


def test_hop_climbs_steeply_and_lands_shallow(ctx):
    brain = Brain(ctx, Fly())
    path, _ = fly_and_record(brain, ctx)
    (x0, y0), (x1, y1) = path[0], path[3]
    (xa, ya), (xb, yb) = path[-4], path[-1]
    climb = abs(y1 - y0) / max(abs(x1 - x0), 1e-6)
    landing = abs(yb - ya) / max(abs(xb - xa), 1e-6)
    assert climb > 3 * landing  # leaves steeply, arrives at a glide


def test_flight_clips_follow_the_path(ctx):
    brain = Brain(ctx, Fly())
    _, clips = fly_and_record(brain, ctx)
    assert clips[0] == "fly"  # flapping to climb
    assert "glide" in clips
    assert clips[-1] == "flare"  # wings flared to land


def test_tour_crosses_the_screen_high_up_and_lands_back_on_the_ground(ctx):
    area = ctx.world.area
    brain = Brain(ctx, Fly.tour(ctx))
    path, _ = fly_and_record(brain, ctx)
    xs, ys = [x for x, _ in path], [y for _, y in path]
    assert min(ys) < area.bottom - 0.3 * (area.bottom - area.top)  # well up the screen
    assert max(xs) - min(xs) > ctx.config.px(80)
    assert min(xs) >= area.left + ctx.margin - 1 and max(xs) <= area.right - ctx.margin + 1
    assert min(ys) >= area.top and max(ys) <= area.bottom
    assert isinstance(brain.state, Idle)
    assert ctx.body.y == area.bottom


def test_flight_turns_to_face_where_it_is_going(ctx):
    ctx.body.facing = Facing.LEFT
    brain = Brain(ctx, Fly([(ctx.body.x + 300, ctx.body.y - 200), (ctx.body.x + 600, ctx.body.y)]))
    run(brain, 0.5)
    assert ctx.body.facing is Facing.RIGHT


def rest_cursor(ctx, world, dx: float = 150, height: float = 200):
    """Leave the mouse resting above the ground near Zengo."""
    world.cursor_pos = (ctx.body.x + dx, ctx.world.area.bottom - height)
    world.idle = 5.0


def test_resting_cursor_invites_a_visit_but_a_moving_or_far_one_does_not(ctx, world):
    rest_cursor(ctx, world)
    assert cursor_is_inviting(ctx)
    world.idle = 0.5  # still moving
    assert not cursor_is_inviting(ctx)
    rest_cursor(ctx, world, dx=ctx.config.px(ctx.config.cursor_reach) + 50)
    assert not cursor_is_inviting(ctx)
    rest_cursor(ctx, world, height=10)  # down at ground level: he'd just walk
    assert not cursor_is_inviting(ctx)


def test_flies_up_and_perches_on_the_resting_cursor(ctx, world):
    rest_cursor(ctx, world)
    brain = Brain(ctx, Fly.to_cursor(ctx))
    run_until(brain, CursorPerch, limit=10)
    assert (ctx.body.x, ctx.body.y) == world.cursor_pos
    run(brain, 2)
    assert (ctx.body.x, ctx.body.y) == world.cursor_pos


def test_moving_the_cursor_startles_him_off_and_he_glides_down(ctx, world):
    rest_cursor(ctx, world)
    brain = Brain(ctx, Fly.to_cursor(ctx))
    run_until(brain, CursorPerch, limit=10)
    x, y = world.cursor_pos
    world.cursor_pos = (x + 40, y)
    brain.tick(DT)
    assert isinstance(brain.state, Fall)
    run_until(brain, Shake, limit=10)
    assert ctx.body.y == ctx.world.area.bottom


def test_left_alone_on_the_cursor_he_flies_back_down(ctx, world):
    rest_cursor(ctx, world)
    brain = Brain(ctx, Fly.to_cursor(ctx))
    run_until(brain, CursorPerch, limit=10)
    run_until(brain, Fly, limit=CursorPerch.stay[1] + 1)
    run_until(brain, Idle, limit=10)
    assert ctx.body.y == ctx.world.area.bottom


def test_cursor_moving_away_mid_flight_turns_it_into_a_glide_down(ctx, world):
    rest_cursor(ctx, world)
    brain = Brain(ctx, Fly.to_cursor(ctx))
    run(brain, 0.4)
    world.cursor_pos = (5000.0, 5000.0)
    brain.tick(DT)
    assert isinstance(brain.state, Glide)
    run_until(brain, Shake, limit=10)


def test_walking_moves_only_while_a_foot_is_lifted(ctx):
    """The frame on screen after a tick decides whether that tick moved the body."""
    brain = Brain(ctx, Walk(target=1500))
    for _ in range(60):
        before = ctx.body.x
        brain.tick(DT)
        moved = ctx.body.x != before
        assert moved == (ctx.animator.frame in STEPPING_FRAMES), ctx.animator.frame


def test_hanging_still_is_never_a_frozen_frame(ctx):
    brain = Brain(ctx)
    pick_up(ctx, brain, 0, -300)
    seen, xs = set(), []
    for _ in range(round(8 / DT)):
        brain.tick(DT)
        seen.add(ctx.animator.frame)
        xs.append(ctx.body.x)
    assert {"held", "held_blink", "held_kick_a", "held_look", "held_flick"} <= seen
    assert max(xs) - min(xs) >= ctx.config.px(1)  # a gentle sway


def test_turning_round_in_the_air_banks_through_a_front_view(ctx):
    x, y = ctx.body.x, ctx.body.y
    out_and_back = [(x + 300, y - 200), (x + 500, y - 260), (x + 250, y - 320), (x - 150, y)]
    brain = Brain(ctx, Fly(out_and_back))
    _, clips = fly_and_record(brain, ctx)
    assert clips[0] == "fly"
    assert "turn" in clips
    assert clips.index("turn") > 0 and clips[-1] == "flare"
    assert ctx.body.facing is Facing.LEFT  # came home the other way


def test_a_straight_flight_never_turns(ctx):
    brain = Brain(ctx, Fly())
    _, clips = fly_and_record(brain, ctx)
    assert "turn" not in clips
