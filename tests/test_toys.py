"""His toys: where they go, playing with them, and what it does for the bond."""

from dataclasses import replace

import pytest

from zengo.behavior.cage import Cage
from zengo.behavior.machine import Brain
from zengo.behavior.states import (
    Caged,
    Fly,
    Idle,
    OnBranch,
    PlayMirror,
    Walk,
    choose_activity,
    go_to_mirror,
)
from zengo.behavior.toys import Bell
from zengo.settings import Settings
from zengo.sounds import sound


def _out(ctx, *toys):
    ctx.toys.put_out(frozenset(toys))


def _branch(ctx):
    branch = ctx.scenery.grow(ctx)
    branch.shown = 1.0
    ctx.scenery.phase = "out"
    ctx.scenery._timer = 1000.0
    return branch


def _caged(ctx):
    ctx.cage = Cage(x=ctx.body.x, y=ctx.body.y)
    ctx.cage.mount = "ground"
    return Brain(ctx, initial=Caged(just_caught=False))


def test_nothing_shows_until_you_put_toys_out(ctx):
    brain = Brain(ctx)
    _branch(ctx)
    brain.tick(0.1)
    assert ctx.toys.bell is None and ctx.toys.mirror is None


def test_the_bell_hangs_under_the_branch_tip_only_while_its_out(ctx):
    brain = Brain(ctx)
    _out(ctx, "bell")
    brain.tick(0.1)
    assert ctx.toys.bell is None  # no branch
    branch = _branch(ctx)
    brain.tick(0.1)
    bell = ctx.toys.bell
    lo, hi = branch.perch_span(ctx.config)
    assert bell is not None and bell.where == "branch"
    assert bell.y > branch.top
    assert min(abs(bell.x - lo), abs(bell.x - hi)) < ctx.config.px(10)  # by the perch's end


def test_in_the_cage_the_bell_hangs_from_the_roof_and_the_mirror_on_the_bars(ctx):
    _out(ctx, "bell", "mirror")
    brain = _caged(ctx)
    brain.tick(0.1)
    bell, mirror = ctx.toys.bell, ctx.toys.mirror
    assert bell.where == "cage" and mirror.where == "cage"
    assert bell.y < ctx.cage.y and mirror.y < ctx.cage.y
    assert bell.x > ctx.cage.x > mirror.x


def test_the_mirror_stands_near_him_and_stays_put(ctx):
    brain = Brain(ctx)
    _out(ctx, "mirror")
    brain.tick(0.1)
    mirror = ctx.toys.mirror
    assert mirror.where == "ground" and mirror.y == ctx.area().bottom
    assert ctx.config.px(55) <= abs(mirror.x - ctx.body.x) <= ctx.config.px(105)
    x = mirror.x
    ctx.body.x += 300
    brain.tick(0.1)
    assert ctx.toys.mirror.x == x


def test_a_struck_bell_swings_then_settles():
    bell = Bell()
    bell.strike(1)
    swings = set()
    for _ in range(60):
        bell.update(1 / 30)
        swings.add(bell.swing)
    assert swings == {-1, 0, 1}
    for _ in range(300):
        bell.update(1 / 30)
    assert bell.swing == 0


def test_he_goes_to_chat_to_his_mirror(ctx):
    _out(ctx, "mirror")
    brain = Brain(ctx)
    brain.tick(0.1)
    picks = [choose_activity(ctx) for _ in range(200)]
    assert any(isinstance(p, Walk) and p.then == "mirror" for p in picks)
    brain.transition(go_to_mirror(ctx))
    for _ in range(300):
        brain.tick(0.05)
        if isinstance(brain.state, PlayMirror):
            break
    assert isinstance(brain.state, PlayMirror)
    assert (ctx.toys.mirror.x - ctx.body.x) * int(ctx.body.facing) > 0  # facing it
    brain.tick(0.05)
    assert ctx.toys.mirror.reflecting
    level = ctx.bond.level
    for _ in range(200):
        brain.tick(0.05)
        if not isinstance(brain.state, PlayMirror):
            break
    assert isinstance(brain.state, Idle)
    assert ctx.speech is not None or ctx.sounds
    assert ctx.bond.level > level
    assert not ctx.toys.ready()  # had his fun for now
    brain.tick(0.05)
    assert not ctx.toys.mirror.reflecting


def test_no_more_games_till_hes_rested(ctx):
    _out(ctx, "mirror")
    Brain(ctx).tick(0.1)
    ctx.toys.rest = 100.0
    picks = [choose_activity(ctx) for _ in range(200)]
    assert not any(isinstance(p, Walk) and p.then == "mirror" for p in picks)


def test_far_off_he_flies_to_the_mirror(ctx):
    _out(ctx, "mirror")
    Brain(ctx).tick(0.1)
    ctx.body.x = ctx.toys.mirror.x + 900
    assert isinstance(go_to_mirror(ctx), Fly)


def test_on_the_branch_he_lands_by_his_bell_and_rings_it(ctx):
    _out(ctx, "bell")
    _branch(ctx)
    brain = Brain(ctx)
    brain.tick(0.1)
    lands = [Fly.to_branch(ctx).waypoints[-1][0] for _ in range(20)]
    assert sum(abs(x - ctx.toys.bell.x) < ctx.config.px(16) for x in lands) >= 10
    ctx.body.x, ctx.body.y = ctx.toys.bell.x, ctx.scenery.branch.top
    brain.transition(OnBranch())
    rang = 0
    for _ in range(2000):
        brain.tick(0.05)
        rang += ctx.sounds.count("ting")
        ctx.sounds.clear()
        if rang >= 2:
            break
    assert rang >= 2


def test_in_the_cage_he_rings_and_chats(ctx):
    ctx.config = replace(ctx.config, toy_every=(1.0, 1.0))
    _out(ctx, "bell", "mirror")
    brain = _caged(ctx)
    did = set()
    for _ in range(4000):
        brain.tick(0.05)
        did.add(brain.state.doing)
        if {"ring", "chat"} <= did:
            break
    assert {"ring", "chat"} <= did


def test_the_bond_from_toys_is_capped_each_hour(ctx):
    start = ctx.bond.level
    for _ in range(50):
        ctx.bond.played(ctx.config)
    assert ctx.bond.level - start <= ctx.config.bond_toy_per_hour + 1e-9


def test_the_bell_has_a_soft_ting():
    ting = sound("ting")
    assert 0.5 < len(ting) / 22050 < 1.0
    assert max(abs(s) for s in ting[-200:]) < 0.05  # dies away


@pytest.mark.parametrize(
    ("given", "kept"),
    [(["mirror", "bell"], ("bell", "mirror")), (["ball", "bell"], ("bell",)), ("bell", ())],
)
def test_the_toys_setting_reads_forgivingly(given, kept):
    assert Settings.from_json({"toys": given}).toys == kept
    assert Settings.from_json(Settings(toys=kept).to_json()).toys == kept


def test_toys_put_out_from_settings_show_up(make_pet):
    pet = make_pet()
    pet.change_settings(replace(pet.settings, toys=("mirror",)))
    pet._brain.tick(0.1)
    pet._render()
    assert pet._mirror.isVisible() and not pet._bell.isVisible()
    pet.change_settings(replace(pet.settings, toys=()))
    pet._brain.tick(0.1)
    pet._render()
    assert not pet._mirror.isVisible()
    layers = pet._layers()
    assert layers.index(pet._branch) < layers.index(pet._bell) < layers.index(pet._cage)
