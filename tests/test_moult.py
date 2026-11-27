"""Moulting: feathers drifting down, lying about, and clicked away."""

import time
from dataclasses import replace

from zengo.behavior.machine import Brain
from zengo.behavior.moult import MAX_FEATHERS, Moult
from zengo.behavior.states import OnBranch, Preen, choose_activity


def _run(moult, ctx, seconds, dt=0.1, **kw):
    kw.setdefault("free", True)
    for _ in range(round(seconds / dt)):
        moult.update(ctx, dt, **kw)


def test_a_feather_drifts_down_swaying_and_stays_where_it_lands(ctx):
    moult = Moult()
    feather = moult.drop(ctx)
    start_x, xs, tilts = feather.x, [], set()
    while not feather.landed:
        _run(moult, ctx, 0.1)
        xs.append(feather.x)
        tilts.add(feather.tilt)
    assert feather.y == feather.ground == ctx.area().bottom - ctx.config.px(1)
    assert max(xs) - min(xs) > 6
    assert tilts == {-1, 0, 1}
    _run(moult, ctx, 600)
    assert moult.feathers == [feather]
    assert feather.tilt == 0
    assert abs(feather.x - start_x) < ctx.config.px(40)


def test_one_falls_every_so_often(ctx):
    ctx.config = replace(ctx.config, moult_every=(100.0, 100.0))
    ctx.seasons.enabled = False
    moult = Moult()
    moult._day, moult._moulting_day = time.localtime(ctx.clock())[:3], False
    _run(moult, ctx, 99)
    assert moult.feathers == []
    _run(moult, ctx, 2)
    assert len(moult.feathers) == 1


def test_none_fall_while_hes_caged_or_away(ctx):
    moult = Moult()
    moult._timer = 1.0
    _run(moult, ctx, 10, free=False)
    assert moult.feathers == []


def test_at_most_three_lie_about_the_oldest_fading(ctx):
    moult = Moult()
    first = moult.drop(ctx)
    for _ in range(MAX_FEATHERS):
        moult.drop(ctx)
    assert first.fading is not None
    _run(moult, ctx, 2)
    assert first not in moult.feathers
    assert len(moult.feathers) == MAX_FEATHERS


def test_a_click_clears_one_away(ctx):
    brain = Brain(ctx)
    ctx.moult.drop(ctx)
    brain.pick_feather(0)
    brain.pick_feather(5)  # nothing there: no harm
    for _ in range(10):
        brain.tick(0.1)
    assert ctx.moult.feathers == []


def _in(month):
    return lambda: time.mktime((2026, month, 15, 12, 0, 0, 0, 0, -1))


def test_moulting_seasons_and_days_bring_more(ctx):
    ctx.config = replace(ctx.config, moult_every=(100.0, 100.0))
    ctx.clock = _in(7)  # summer
    moult = Moult()
    moult._day, moult._moulting_day = time.localtime(ctx.clock())[:3], False
    assert moult._wait(ctx) == 100
    ctx.clock = _in(4)  # spring
    moult._day = time.localtime(ctx.clock())[:3]
    assert moult._wait(ctx) == 60
    moult._moulting_day = True
    assert moult._wait(ctx) == 30


def test_a_moulting_day_is_settled_once_a_day(ctx):
    moult = Moult()
    days = {moult.moulting_day(ctx) for _ in range(50)}
    assert len(days) == 1


def test_he_preens_more_on_a_moulting_day(ctx):
    def preens():
        return sum(isinstance(choose_activity(ctx), Preen) for _ in range(400))

    ctx.moult._day, ctx.moult._moulting_day = time.localtime(ctx.clock())[:3], False
    usual = preens()
    ctx.moult._moulting_day = True
    assert preens() > usual * 1.6


def test_on_the_branch_in_autumn_a_leaf_falls_instead_sometimes(ctx):
    ctx.clock = _in(10)
    ctx.config = replace(ctx.config, moult_every=(1.0, 1.0))
    moult = Moult()
    _run(moult, ctx, 30, on_branch=True)
    leaves = [p for p in ctx.effects.particles if p.kind == "leaf"]
    assert leaves and moult.feathers


def test_feathers_have_their_windows(make_pet):
    pet = make_pet()
    ctx = pet._brain.ctx
    ctx.moult.drop(ctx)
    pet._render()
    shown = [w for w in pet._feathers if w.isVisible()]
    assert len(shown) == 1
    shown[0].clicked.emit()
    assert ctx.moult.feathers[0].fading is not None
    layers = pet._layers()
    assert layers.index(shown[0]) < layers.index(pet._window)
    assert not isinstance(pet._brain.state, OnBranch)
