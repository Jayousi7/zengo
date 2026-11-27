"""Break reminders, when you're not using the focus timer."""

from zengo.behavior.cage import Cage
from zengo.behavior.machine import Brain
from zengo.behavior.reminders import A_BREAK, ASK_AGAIN
from zengo.behavior.states import Caged, Nudge


def _at_it(ctx, brain, seconds, dt=1.0):
    nudged = 0
    for _ in range(round(seconds / dt)):
        ctx.world.input_idle = 2.0  # at the computer
        ctx.hunger.fullness, ctx.hunger.hungry = 1.0, False  # (not off asking for food)
        brain.tick(dt)
        nudged += isinstance(brain.state, Nudge) and brain.state.elapsed < dt
    return nudged


def test_after_a_long_stretch_he_comes_to_suggest_a_break(ctx):
    ctx.reminders.minutes = 50
    ctx.world.cursor_pos = (ctx.body.x + 100, 700.0)
    brain = Brain(ctx)
    _at_it(ctx, brain, 49 * 60)
    assert ctx.reminders.nudges == 0
    saw = False
    for _ in range(600):
        ctx.world.input_idle = 2.0
        ctx.hunger.fullness, ctx.hunger.hungry = 1.0, False
        brain.tick(0.2)
        if isinstance(brain.state, Nudge):
            saw = True
            break
    assert saw
    assert ctx.speech is not None and "?" in ctx.speech.text


def test_he_comes_down_from_a_perch_to_suggest_it(ctx):
    from zengo.behavior.states import OnBranch

    branch = ctx.scenery.grow(ctx)
    branch.shown, ctx.scenery.phase, ctx.scenery._timer = 1.0, "out", 1e9
    lo, hi = branch.perch_span(ctx.config)
    ctx.body.x, ctx.body.y = (lo + hi) / 2, branch.top
    ctx.reminders.minutes, ctx.reminders.at_it = 30, 30 * 60 - 1
    brain = Brain(ctx, OnBranch())
    for _ in range(300):
        ctx.world.input_idle = 2.0
        brain.tick(0.1)
        if isinstance(brain.state, Nudge):
            break
    assert isinstance(brain.state, Nudge)


def test_once_more_after_ten_minutes_then_he_lets_it_go(ctx):
    ctx.reminders.minutes = 30
    brain = Brain(ctx)
    _at_it(ctx, brain, 30 * 60 + 5)
    assert ctx.reminders.nudges == 1
    _at_it(ctx, brain, ASK_AGAIN)
    assert ctx.reminders.nudges == 2
    _at_it(ctx, brain, 3 * 3600)
    assert ctx.reminders.nudges == 2


def test_a_real_break_starts_the_count_again(ctx):
    ctx.reminders.minutes = 30
    brain = Brain(ctx)
    _at_it(ctx, brain, 25 * 60)
    ctx.world.input_idle = A_BREAK + 1
    brain.tick(1.0)
    assert ctx.reminders.at_it == 0
    _at_it(ctx, brain, 25 * 60)
    assert ctx.reminders.nudges == 0


def test_never_during_focus_or_when_off(ctx):
    ctx.reminders.minutes = 30
    brain = Brain(ctx)
    ctx.focus.start(ctx.clock())
    _at_it(ctx, brain, 40 * 60)
    assert ctx.reminders.nudges == 0
    ctx.focus.stop()
    ctx.reminders.minutes = 0
    _at_it(ctx, brain, 40 * 60)
    assert ctx.reminders.nudges == 0


def test_without_the_systems_word_the_pointer_counts(ctx):
    ctx.reminders.minutes = 30
    brain = Brain(ctx)
    for _ in range(31 * 60):
        ctx.world.input_idle, ctx.world.idle = None, 1.0
        brain.tick(1.0)
    assert ctx.reminders.nudges == 1


def test_caged_he_suggests_it_from_there(ctx):
    from dataclasses import replace

    ctx.config = replace(ctx.config, escape_after=1e9)  # he stays put
    ctx.reminders.minutes = 30
    ctx.cage = Cage(x=ctx.body.x, y=ctx.body.y)
    ctx.cage.mount = "ground"
    brain = Brain(ctx, Caged(just_caught=False))
    _at_it(ctx, brain, 30 * 60 + 2)
    assert isinstance(brain.state, Caged)
    assert ctx.reminders.nudges == 1


def test_the_setting_reaches_him(make_pet):
    from dataclasses import replace

    pet = make_pet()
    pet.change_settings(replace(pet.settings, reminder_minutes=90))
    assert pet._brain.ctx.reminders.minutes == 90
