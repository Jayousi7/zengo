"""Catching Zengo in a cage, moving the cage about, and letting him out."""

import itertools
import math

import pytest

from zengo.behavior.cage import BELOW_FLOOR
from zengo.behavior.machine import Brain
from zengo.behavior.states import Caged, Dragged, Fly, Idle, OnBranch
from zengo.sprites.cage import CAGE, CAGE_WIDTH, CENTRE, FLOOR

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


def box_round_him(ctx, pad: float = 40):
    x, y = ctx.body.x, ctx.body.y
    return x - pad, y - 80, x + pad, y + 10


def catch(ctx, brain: Brain):
    assert brain.catch_in(*box_round_him(ctx))
    return ctx.cage


def carry(ctx, brain: Brain, to: tuple[float, float], seconds: float = 0.5):
    """Grab the cage by its middle and drag it to ``to``, then let go."""
    cage = ctx.cage
    start = (cage.x, cage.y - ctx.config.px(20))
    brain.cage_grab(*start)
    steps = round(seconds / DT)
    for i in range(1, steps + 1):
        brain.cage_drag(
            start[0] + (to[0] - start[0]) * i / steps, start[1] + (to[1] - start[1]) * i / steps
        )
        brain.tick(DT)
    brain.cage_release()


# --- Catching ----------------------------------------------------------------


def test_a_box_round_him_cages_him_where_he_stands_and_he_is_furious(ctx):
    brain = Brain(ctx, Idle())
    x = ctx.body.x
    cage = catch(ctx, brain)
    assert isinstance(brain.state, Caged)
    assert cage.mount == "ground" and cage.x == x
    assert cage.y == ctx.world.area.bottom - ctx.config.px(BELOW_FLOOR)
    brain.tick(DT)
    assert (ctx.body.x, ctx.body.y) == (cage.x, cage.y)  # on the tray
    assert ctx.speech is not None and ctx.speech.mood == "angry"
    assert ctx.animator.clip_name == "front_angry"


def test_a_box_that_misses_him_does_nothing_but_amuse_him(ctx):
    brain = Brain(ctx, Idle())
    x, y = ctx.body.x, ctx.body.y
    assert not brain.catch_in(x + 200, y - 100, x + 300, y)
    assert ctx.cage is None
    assert isinstance(brain.state, Idle)
    assert ctx.speech is not None and "missed" in ctx.speech.text


def test_caught_up_high_the_cage_drops_to_the_ground_and_he_says_ow(ctx):
    brain = Brain(ctx, Idle())
    ctx.scenery.grow(ctx)
    run(brain, ctx.config.branch_grow_seconds + 0.1)
    brain.transition(Fly.to_branch(ctx))
    run_until(brain, OnBranch, limit=20)
    cage = catch(ctx, brain)
    assert cage.mount == "falling"
    run(brain, 3)
    assert cage.mount == "ground"
    assert ctx.body.y == cage.y
    said = []
    for _ in range(3):
        if ctx.speech:
            said.append(ctx.speech.text)
        brain.tick(DT)
    assert "ow!" in said or ctx.speech.mood == "angry"


# --- Moving the cage ---------------------------------------------------------


def test_carried_to_the_top_it_hangs_from_a_chain_and_swings_to_rest(ctx):
    brain = Brain(ctx, Idle())
    cage = catch(ctx, brain)
    area = ctx.world.area
    carry(ctx, brain, to=(900, area.top + ctx.config.px(FLOOR) + 20))
    assert cage.mount == "chain"
    assert cage.pivot == (cage.x, area.top)
    run(brain, 0.5)
    assert cage.sway != 0  # swinging
    assert ctx.body.x == pytest.approx(cage.x + cage.sway)  # he swings with it
    run(brain, 15)
    assert abs(cage.sway) < 1  # and settles


def test_carried_to_a_side_edge_it_stands_on_a_shelf(ctx):
    brain = Brain(ctx, Idle())
    cage = catch(ctx, brain)
    area = ctx.world.area
    carry(ctx, brain, to=(area.left + ctx.config.px(CAGE_WIDTH / 2) + 10, 500))
    assert (cage.mount, cage.side) == ("shelf", -1)
    y = cage.y
    run(brain, 2)
    assert cage.y == y  # it stays put up there
    carry(ctx, brain, to=(area.right - ctx.config.px(CAGE_WIDTH / 2) - 10, 400))
    assert (cage.mount, cage.side) == ("shelf", 1)


def test_too_low_at_a_side_edge_for_a_shelf_it_goes_to_the_floor(ctx):
    """A shelf under a cage this near the floor would hang off the screen."""
    brain = Brain(ctx, Idle())
    cage = catch(ctx, brain)
    area, px = ctx.world.area, ctx.config.px
    low = area.bottom - px(BELOW_FLOOR) - 5
    for x in (area.left + px(CAGE_WIDTH / 2) + 10, area.right - px(CAGE_WIDTH / 2) - 10):
        carry(ctx, brain, to=(x, low))
        assert cage.mount == "falling"
        run(brain, 2)
        assert cage.mount == "ground"


def test_let_go_anywhere_else_it_falls_to_the_ground_and_he_complains(ctx):
    brain = Brain(ctx, Idle())
    cage = catch(ctx, brain)
    run(brain, 15)  # let the tantrum pass
    carry(ctx, brain, to=(960, 400))
    assert cage.mount == "falling"
    complaints = set()
    for _ in range(round(3 / DT)):
        brain.tick(DT)
        if ctx.speech and ctx.speech.mood == "angry":
            complaints.add(ctx.speech.text)
    assert cage.mount == "ground"
    assert "ow!" in complaints


def test_he_rattles_about_angrily_while_the_cage_is_carried(ctx):
    brain = Brain(ctx, Idle())
    cage = catch(ctx, brain)
    run(brain, 15)
    brain.cage_grab(cage.x, cage.y - 30)
    for i in range(20):
        brain.cage_drag(cage.x + 5, cage.y - 30 - i)
        brain.tick(DT)
    assert ctx.animator.clip_name == "front_angry"


def test_he_cannot_be_grabbed_or_poked_through_the_bars(ctx):
    brain = Brain(ctx, Idle())
    catch(ctx, brain)
    brain.grab(ctx.body.x, ctx.body.y - 20)
    brain.click()
    brain.double_click()
    assert isinstance(brain.state, Caged)
    assert not isinstance(brain.state, Dragged)


def test_petting_through_the_bars_calms_him(ctx, world):
    brain = Brain(ctx, Idle())
    catch(ctx, brain)
    run(brain, 0.2)
    cx, cy = ctx.body.x, ctx.body.y - ctx.config.px(14)
    for i in range(round(2 / DT)):
        world.cursor_pos = (cx + ctx.config.px(8) * math.sin(2 * math.pi * i * DT / 0.8), cy)
        brain.tick(DT)
    assert ctx.animator.clip_name == "front_petted"


# --- Letting him out -------------------------------------------------------------


def test_let_out_he_flies_off_and_the_cage_goes(ctx):
    brain = Brain(ctx, Idle())
    catch(ctx, brain)
    run(brain, 1)
    brain.let_out()
    brain.tick(DT)
    assert isinstance(brain.state, Fly)
    assert ctx.cage is not None and ctx.cage.door_open
    run(brain, 2)
    assert ctx.cage is None
    run_until(brain, Idle, limit=10)
    assert ctx.body.y == ctx.world.area.bottom


def test_let_out_of_a_hanging_cage_he_flies_down(ctx):
    brain = Brain(ctx, Idle())
    catch(ctx, brain)
    carry(ctx, brain, to=(900, 140))
    run(brain, 2)
    brain.let_out()
    run_until(brain, Idle, limit=15)
    assert ctx.body.y == ctx.world.area.bottom


def test_cage_art_sits_him_on_the_tray():
    assert set(CAGE.rows[FLOOR]) == {"h"}  # brass lip all along the floor
    for row in CAGE.rows[FLOOR - 28 : FLOOR - 12]:  # his crest and face, front on
        assert row[CENTRE] == "."  # no bar or band across the middle of his face


def test_carried_about_his_complaints_come_one_at_a_time(ctx):
    brain = Brain(ctx, Idle())
    cage = catch(ctx, brain)
    brain.cage_grab(cage.x, cage.y - 30)
    started, last = [], None
    for i in range(round(20 / DT)):
        brain.cage_drag(cage.x + (i % 20), cage.y - 30)
        brain.tick(DT)
        if ctx.speech is not None and ctx.speech is not last:
            started.append(i * DT)
        last = ctx.speech
    gaps = [b - a for a, b in itertools.pairwise(started)]
    assert len(started) <= 20 / ctx.config.complaint_every[0] + 1
    assert min(gaps) >= ctx.config.complaint_every[0] - DT


def test_shelf_bracket_braces_up_from_the_wall():
    from zengo.sprites.cage import SHELF

    below_plank = [row for row in SHELF.rows[3:] if row.strip(".")]
    arm, brace = below_plank[0], below_plank[1:]
    assert arm.rstrip(".").endswith("M")  # an arm under the plank, out from the wall
    ends = [len(row.rstrip(".")) - 1 for row in brace]
    assert ends == sorted(ends, reverse=True)  # the brace drops towards the wall
    arm_end = len(arm.rstrip(".")) - 1
    assert arm_end - 1 <= ends[0] <= arm_end  # meets the end of the arm, diagonally
    assert ends[-1] <= 2  # and comes down to the wall


def test_carrying_the_cage_never_sets_off_his_petting(ctx, world):
    """A real drag wobbles the pointer back and forth over him, just like a stroke."""
    brain = Brain(ctx, Idle())
    cage = catch(ctx, brain)
    run(brain, 1)
    gx, gy = cage.x, cage.y - 30
    brain.cage_grab(gx, gy)
    clouds, last = [], None
    for i in range(round(10 / DT)):
        x, y = gx + 25 * math.sin(i / 8), gy - 200 * min(1, i / 60)
        world.cursor_pos = (x, y)
        brain.cage_drag(x, y)
        brain.tick(DT)
        if ctx.speech is not None and ctx.speech is not last:
            clouds.append(ctx.speech.text)
        last = ctx.speech
    assert "♥" not in clouds
    assert len(clouds) <= 10 / ctx.config.complaint_every[0] + 1


@pytest.mark.parametrize(
    "to", [(-500, -500), (5000, -500), (5000, 5000), (-500, 5000), (960, -900)]
)
def test_the_cage_stops_at_the_screen_edges_and_corners(ctx, to):
    brain = Brain(ctx, Idle())
    cage = catch(ctx, brain)
    brain.cage_grab(cage.x, cage.y - 30)
    brain.cage_drag(*to)
    brain.tick(DT)
    area, px = ctx.world.area, ctx.config.px
    assert area.left <= cage.x - px(CAGE_WIDTH / 2) and cage.x + px(CAGE_WIDTH / 2) <= area.right
    assert area.top <= cage.top(ctx) and cage.y + px(BELOW_FLOOR) <= area.bottom


# --- Escaping ------------------------------------------------------------------


def test_escape_odds_start_at_15_percent_after_5_minutes_and_rise_1_percent_a_minute(ctx):
    from zengo.behavior.cage import escape_chance

    cfg = ctx.config
    assert escape_chance(cfg, 4 * 60, 0) == 0
    assert escape_chance(cfg, 5 * 60, 0) == pytest.approx(0.15)
    assert escape_chance(cfg, 6 * 60, 0) == pytest.approx(0.16)
    assert escape_chance(cfg, 10 * 60 + 30, 0) == pytest.approx(0.20)
    assert escape_chance(cfg, 10 * 60, 2) == pytest.approx(0.14)  # fed twice: 3% off each
    assert escape_chance(cfg, 5 * 60, 10) == 0  # never below nothing


def test_he_tries_once_a_minute_from_five_minutes(ctx):
    from dataclasses import replace

    ctx.config = replace(ctx.config, escape_chance=0.0, escape_chance_rise=0.0)
    brain = Brain(ctx, Idle())
    catch(ctx, brain)
    tries = []
    escape = ctx.escape
    original = escape.tries_to_escape

    def counting(c):
        result = original(c)
        if escape.next_try is not None and (not tries or tries[-1] != escape.next_try):
            tries.append(escape.next_try)
        return result

    escape.tries_to_escape = counting
    run(brain, 8 * 60)
    assert isinstance(brain.state, Caged)  # 0%: he never gets out
    attempts = [t - ctx.config.escape_every for t in tries]
    assert attempts[0] == pytest.approx(5 * 60, abs=0.1)
    assert {round(b - a) for a, b in itertools.pairwise(attempts)} == {60}


def test_with_quick_timers_he_works_the_latch_and_escapes_within_seconds(ctx):
    from zengo.config import quick

    ctx.config = quick(ctx.config)
    brain = Brain(ctx, Idle())
    catch(ctx, brain)
    run(brain, ctx.config.escape_after + 0.5)
    assert ctx.animator.clip_name == "front_pick"  # working the latch...
    run_until(brain, Fly, limit=4)
    assert ctx.cage.escaped and ctx.speech.text.startswith("freedom")
    run_until(brain, Idle, limit=15)
    run(brain, 2)
    assert ctx.cage is None  # the empty cage goes


def test_no_escaping_while_the_cage_is_carried(ctx):
    from zengo.config import quick

    ctx.config = quick(ctx.config)
    brain = Brain(ctx, Idle())
    cage = catch(ctx, brain)
    brain.cage_grab(cage.x, cage.y - 30)
    for i in range(round(15 / DT)):
        brain.cage_drag(cage.x + i % 3, cage.y - 30)
        brain.tick(DT)
    assert isinstance(brain.state, Caged) and not cage.door_open


def test_letting_him_out_keeps_his_escape_progress_and_catching_him_again_carries_on(ctx):
    brain = Brain(ctx, Idle())
    catch(ctx, brain)
    brain.feed()
    run(brain, 3 * 60)
    brain.let_out()
    run_until(brain, Idle, limit=15)
    run(brain, 2)
    assert ctx.cage is None
    assert ctx.escape.caged_for == pytest.approx(3 * 60, abs=1)  # kept
    assert ctx.escape.feedings == 1
    run(brain, 60)
    assert ctx.escape.caged_for == pytest.approx(3 * 60, abs=1)  # paused while free
    catch(ctx, brain)
    run(brain, 60)
    assert ctx.escape.caged_for == pytest.approx(4 * 60, abs=1)  # carries on


def test_only_escaping_starts_his_progress_over(ctx):
    from zengo.config import quick

    ctx.config = quick(ctx.config)
    brain = Brain(ctx, Idle())
    catch(ctx, brain)
    brain.feed()
    run_until(brain, Fly, limit=15)
    assert ctx.cage.escaped
    assert (ctx.escape.caged_for, ctx.escape.feedings, ctx.escape.next_try) == (0, 0, None)
