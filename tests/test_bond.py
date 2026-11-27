"""How close Zengo feels to you, and what it changes."""

import pytest

from zengo.behavior.machine import Brain
from zengo.behavior.memory import restore, snapshot
from zengo.behavior.states import Alert, Fly, Follow, Idle, Sulk, Walk, choose_activity

DT = 1 / 30


def run(brain, seconds):
    for _ in range(round(seconds / DT)):
        brain.tick(DT)


def far_pointer(world):
    world.cursor_pos = (5000.0, 5000.0)


# --- What raises and lowers it ------------------------------------------------


def test_he_starts_in_the_middle(ctx):
    assert ctx.bond.level == 0.5


def test_feeding_brings_him_closer_and_more_so_when_he_was_hungry(ctx, world):
    far_pointer(world)
    brain = Brain(ctx, Idle())
    brain.feed()
    assert ctx.bond.level == pytest.approx(0.5 + ctx.config.bond_fed)
    ctx.hunger.hungry = True
    before = ctx.bond.level
    brain.feed()
    assert ctx.bond.level == pytest.approx(before + ctx.config.bond_fed_hungry)


def test_catching_him_costs_and_letting_him_out_wins_some_back(ctx, world):
    far_pointer(world)
    brain = Brain(ctx, Idle())
    brain.catch_in(ctx.body.x - 40, ctx.body.y - 80, ctx.body.x + 40, ctx.body.y + 5)
    assert ctx.bond.level == pytest.approx(0.5 - ctx.config.bond_caught)
    run(brain, 60)  # a minute caged
    caged = ctx.bond.level
    assert caged == pytest.approx(0.5 - ctx.config.bond_caught - ctx.config.bond_caged, abs=1e-3)
    brain.let_out()
    assert ctx.bond.level == pytest.approx(caged + ctx.config.bond_let_out)
    brain.let_out()  # the door's already open: nothing more
    assert ctx.bond.level == pytest.approx(caged + ctx.config.bond_let_out)


def test_petting_helps_but_only_so_much_an_hour(ctx, world):
    far_pointer(world)
    ctx.bond.update(ctx, 0.0, caged=False, petted=False)
    for _ in range(round(60 / DT)):  # a solid minute of petting
        ctx.bond.update(ctx, DT, caged=False, petted=True)
    assert ctx.bond.level == pytest.approx(0.5 + ctx.config.bond_petting_per_hour, abs=0.01)


def test_your_pointer_nearby_is_company(ctx, world):
    world.cursor_pos = (ctx.body.x + 10, ctx.body.y - 20)
    for _ in range(round(60 / DT)):
        ctx.bond.update(ctx, DT, caged=False, petted=False)
    assert ctx.bond.level > 0.5


def test_dropping_him_from_high_up_hurts_his_feelings(ctx, world):
    far_pointer(world)
    brain = Brain(ctx, Idle())
    brain.grab(ctx.body.x, ctx.body.y)
    brain.drag(ctx.body.x, ctx.body.y - ctx.config.px(ctx.config.drop_height + 40))
    run(brain, 0.5)
    brain.release()
    assert ctx.bond.level == pytest.approx(0.5 - ctx.config.bond_dropped, abs=1e-3)


def test_a_short_drop_is_fine(ctx, world):
    far_pointer(world)
    brain = Brain(ctx, Idle())
    brain.grab(ctx.body.x, ctx.body.y)
    brain.drag(ctx.body.x, ctx.body.y - ctx.config.px(20))
    run(brain, 0.5)
    brain.release()
    assert ctx.bond.level == pytest.approx(0.5, abs=1e-3)


def test_left_alone_he_drifts_back_to_the_middle(ctx, world):
    far_pointer(world)
    ctx.bond.level = 0.9
    ctx.bond.update(ctx, 3600, caged=False, petted=False)
    assert ctx.bond.level == pytest.approx(0.9 - ctx.config.bond_drift)


def test_it_is_remembered(ctx):
    ctx.bond.level = 0.83
    data = snapshot(ctx)
    ctx.bond.level = 0.5
    restore(ctx, data)
    assert ctx.bond.level == 0.83


# --- What it changes ------------------------------------------------------------


def test_devoted_he_seeks_you_out_more(ctx, world):
    world.cursor_pos = (ctx.body.x + 400, ctx.body.y - 300)

    def follows(level):
        ctx.bond.level = level
        picks = [type(choose_activity(ctx)) for _ in range(400)]
        return picks.count(Follow)

    assert follows(0.9) > 1.5 * follows(0.5)
    assert follows(0.1) == 0


def test_grumpy_he_sulks_with_his_back_to_you(ctx, world):
    far_pointer(world)
    ctx.bond.level = 0.1
    picks = [type(choose_activity(ctx)) for _ in range(300)]
    assert Sulk in picks
    brain = Brain(ctx, Sulk())
    assert ctx.animator.frame.startswith("sulk")
    run(brain, 20)
    assert not isinstance(brain.state, Sulk)


def test_grumpy_he_walks_off_when_your_pointer_comes_near(ctx, world):
    ctx.bond.level = 0.1
    brain = Brain(ctx, Idle())
    world.cursor_pos = (ctx.body.x + 20, ctx.body.y - 20)
    run(brain, 1)
    assert isinstance(brain.state, Walk)
    assert brain.state.target < ctx.body.x  # away from the pointer


def test_grumpy_he_ignores_the_first_poke(ctx, world):
    far_pointer(world)
    ctx.bond.level = 0.1
    brain = Brain(ctx, Idle())
    brain.click()
    assert isinstance(brain.state, Idle) and ctx.speech.text == "hmph"
    brain.click()
    assert isinstance(brain.state, Alert)


def test_devoted_some_whistles_are_hearts(ctx):
    ctx.bond.level = 0.9
    said = set()
    for _ in range(80):
        ctx.whistle()
        said.add(ctx.speech.text)
    assert "♥" in said and len(said) > 1


# --- Welcome back -----------------------------------------------------------------


def come_back(brain, world, seconds_away=700):
    world.input_idle = seconds_away
    brain.tick(DT)
    world.input_idle = 0.1
    brain.tick(DT)


def test_devoted_he_greets_you_back(ctx, world):
    ctx.bond.level = 0.9
    world.cursor_pos = (ctx.body.x + 300, ctx.body.y - 100)
    brain = Brain(ctx, Idle())
    come_back(brain, world)
    assert ctx.speech.text == "you're back! ♪" and "trill" in ctx.sounds
    assert isinstance(brain.state, Fly | Follow)


def test_in_between_he_chirps_hello(ctx, world):
    far_pointer(world)
    brain = Brain(ctx, Idle())
    come_back(brain, world)
    assert ctx.speech.text == "oh, hi! ♪"


def test_grumpy_he_gives_you_one_look(ctx, world):
    far_pointer(world)
    ctx.bond.level = 0.1
    brain = Brain(ctx, Idle())
    come_back(brain, world)
    assert isinstance(brain.state, Alert)


def test_a_short_pause_is_not_being_away(ctx, world):
    far_pointer(world)
    brain = Brain(ctx, Idle())
    come_back(brain, world, seconds_away=60)
    assert ctx.speech is None or ctx.speech.text != "oh, hi! ♪"
