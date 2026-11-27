"""Perching on top of your windows."""

import pytest

from zengo.behavior.machine import Brain
from zengo.behavior.states import Fall, Fly, Idle, OnWindow, Shake
from zengo.world import Ledge, Window, visible_ledges

DT = 1 / 30


def run(brain, seconds):
    for _ in range(round(seconds / DT)):
        brain.tick(DT)


def run_until(brain, kind, limit=30.0):
    for _ in range(round(limit / DT)):
        brain.tick(DT)
        if isinstance(brain.state, kind):
            return
    raise AssertionError(f"never reached {kind.__name__}; stuck in {brain.state!r}")


# --- Which parts of window tops are in view -----------------------------------


def test_a_lone_window_offers_its_whole_top():
    assert visible_ledges([Window(1, 100, 200, 700, 600)]) == [Ledge(1, 100, 700, 200, 100)]


def test_a_window_in_front_hides_the_part_of_the_top_it_lies_across():
    front = Window(2, 300, 150, 500, 400)  # straddles the lower window's top edge
    back = Window(1, 100, 200, 700, 600)
    ledges = visible_ledges([front, back])
    assert Ledge(2, 300, 500, 150, 300) in ledges
    assert [(le.left, le.right) for le in ledges if le.window == 1] == [(100, 300), (500, 700)]


def test_a_window_in_front_below_the_top_edge_hides_nothing_of_it():
    front = Window(2, 300, 250, 500, 400)  # lower down, clear of the top edge
    back = Window(1, 100, 200, 700, 600)
    ledges = [le for le in visible_ledges([front, back]) if le.window == 1]
    assert [(le.left, le.right) for le in ledges] == [(100, 700)]


def test_scraps_too_narrow_to_stand_on_are_dropped():
    front = Window(2, 105, 150, 695, 400)
    back = Window(1, 100, 200, 700, 600)
    assert [le.window for le in visible_ledges([front, back], min_width=20)] == [2]


# --- Perching -----------------------------------------------------------------


def window_top(world, *, left=600.0, right=1200.0, y=500.0, window=7):
    world.windows_on_top = [Ledge(window, left, right, y, left)]


def perch(ctx, world, brain):
    window_top(world)
    brain.transition(Fly.to_window(ctx))
    run_until(brain, OnWindow, limit=15)


def test_he_flies_up_and_sits_on_a_window_top(ctx, world):
    brain = Brain(ctx, Idle())
    perch(ctx, world, brain)
    assert ctx.body.y == 500
    assert 600 <= ctx.body.x <= 1200
    assert ctx.animator.frame in (
        "ledge_perch",
        "ledge_blink",
        "ledge_shake_a",
        "ledge_shake_mid",
        "ledge_shake_b",
    )


def test_he_rides_along_when_the_window_moves(ctx, world):
    brain = Brain(ctx, Idle())
    perch(ctx, world, brain)
    x = ctx.body.x
    window_top(world, left=700, right=1300, y=420)  # dragged right and up
    brain.tick(DT)
    assert isinstance(brain.state, OnWindow)
    assert (ctx.body.x, ctx.body.y) == (pytest.approx(x + 100), 420)


def test_between_window_list_reads_he_rides_on_a_fresh_read_and_keeps_his_balance(ctx, world):
    brain = Brain(ctx, Idle())
    perch(ctx, world, brain)
    run(brain, 1)
    x = ctx.body.x
    world.live_windows[7] = Window(7, 650, 480, 1250, 900)  # being dragged; the list is stale
    brain.tick(DT)
    assert isinstance(brain.state, OnWindow)
    assert (ctx.body.x, ctx.body.y) == (pytest.approx(x + 50), 480)
    assert ctx.animator.frame == "ledge_grip"
    run(brain, 0.5)  # the window has stopped
    assert ctx.animator.frame != "ledge_grip"


def test_a_ride_wakes_him(ctx, world):
    brain = Brain(ctx, Idle())
    perch(ctx, world, brain)
    brain.state._do(ctx, "sleep")
    world.live_windows[7] = Window(7, 650, 480, 1250, 900)
    brain.tick(DT)
    assert brain.state.doing == "alert"


def test_losing_his_window_startles_him(ctx, world):
    brain = Brain(ctx, Idle())
    perch(ctx, world, brain)
    world.windows_on_top = []
    brain.tick(DT)
    assert isinstance(brain.state, Fall)
    assert ctx.animator.frame.startswith("startle_")
    assert "chirp_b" in ctx.sounds


@pytest.mark.parametrize(
    "change",
    [
        lambda world: setattr(world, "windows_on_top", []),  # closed, minimized, maximized
        lambda world: setattr(
            world, "windows_on_top", [Ledge(7, 600, 610, 500, 600)]
        ),  # covered where he sits
    ],
)
def test_he_flutters_off_when_his_window_goes(ctx, world, change):
    brain = Brain(ctx, Idle())
    perch(ctx, world, brain)
    ctx.body.x = 900
    brain.tick(DT)
    change(world)
    brain.tick(DT)
    assert isinstance(brain.state, Fall)
    run_until(brain, Shake, limit=10)
    assert ctx.body.y == ctx.world.area.bottom


def test_if_the_window_goes_while_he_flies_to_it_he_glides_down(ctx, world):
    brain = Brain(ctx, Idle())
    window_top(world)
    brain.transition(Fly.to_window(ctx))
    run(brain, 0.5)
    world.windows_on_top = []
    run_until(brain, Shake, limit=10)


def test_tops_too_high_too_low_or_too_narrow_are_not_for_perching(ctx, world):
    from zengo.behavior.states import perchable_ledges

    world.windows_on_top = [
        Ledge(1, 100, 900, 20, 100),  # no room above it for him
        Ledge(2, 100, 900, 1030, 100),  # down by the ground
        Ledge(3, 100, 130, 500, 100),  # a sliver
        Ledge(4, 100, 900, 500, 100),
    ]
    assert [le.window for le in perchable_ledges(ctx)] == [4]


def test_up_there_he_still_does_what_he_does(ctx, world):
    brain = Brain(ctx, Idle())
    perch(ctx, world, brain)
    brain.double_click()
    brain.tick(DT)
    assert ctx.animator.clip_name == "ledge_whistle" and isinstance(brain.state, OnWindow)


def test_after_a_while_he_flies_off(ctx, world):
    brain = Brain(ctx, Idle())
    perch(ctx, world, brain)
    run_until(brain, Fly, limit=ctx.config.window_visit[1] + 15)
    run_until(brain, Idle, limit=30)
    assert ctx.body.y == ctx.world.area.bottom


def test_a_window_top_draws_him_over(ctx, world):
    window_top(world)
    brain = Brain(ctx, Idle())
    for _ in range(round(120 / DT)):
        brain.tick(DT)
        if isinstance(brain.state, Fly) and brain.state.onto == "window":
            return
    pytest.fail("never flew to the window")
