"""The needs read-out shown in his menu."""

import pytest

from zengo.behavior.machine import Brain
from zengo.behavior.states import Idle
from zengo.ui.status_panel import StatusPanel, clock, rows


def test_well_fed_he_is_not_peckish(ctx):
    ctx.hunger.fullness = 0.9
    status = Brain(ctx, Idle()).status()
    assert status.hunger_chance == 0
    assert [r.title for r in rows(status)] == ["Fullness", "Hunger", "Seeds"]
    assert "not peckish" in rows(status)[1].value


def test_the_emptier_he_is_the_higher_his_odds_shown(ctx):
    brain = Brain(ctx, Idle())
    ctx.hunger.fullness = 0.5
    half = brain.status().hunger_chance
    ctx.hunger.fullness = 0.2
    low = brain.status().hunger_chance
    assert 0 < half < low
    assert f"{low:.0%}" in rows(brain.status())[1].value


def test_hungry_shows_as_hungry(ctx):
    ctx.hunger.hungry = True
    assert rows(Brain(ctx, Idle()).status())[1].value == "hungry now!"


def test_caged_it_shows_his_dish_and_escape_odds_and_countdown(ctx):
    brain = Brain(ctx, Idle())
    brain.catch_in(ctx.body.x - 40, ctx.body.y - 80, ctx.body.x + 40, ctx.body.y + 5)
    brain.feed()
    status = brain.status()
    assert status.caged and not status.escape_started
    assert status.escape_try_in == pytest.approx(ctx.config.escape_after, abs=1)
    assert status.escape_chance == pytest.approx(0.15 - 0.03)  # fed once in there
    escape = rows(status)[-1]
    assert escape.title == "Escape" and "first try in 5:00" in escape.value
    assert rows(status)[2].title == "Dish" and rows(status)[2].value == "1/3 stacks"


def test_the_panel_draws_and_refreshes(ctx):
    brain = Brain(ctx, Idle())
    panel = StatusPanel(brain.status)
    panel.resize(panel.sizeHint())
    assert not panel.grab().isNull()
    assert panel.sizeHint().height() > 3 * StatusPanel.ROW_HEIGHT


def test_clock():
    assert clock(0) == "0:00" and clock(65.4) == "1:05" and clock(-3) == "0:00"
