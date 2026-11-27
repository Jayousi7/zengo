"""The needs read-out shown in his menu."""

import pytest

from zengo.behavior.machine import Brain
from zengo.behavior.states import Idle
from zengo.ui.status_panel import StatusPanel, clock, rows


def by_title(status):
    return {row.title: row for row in rows(status)}


def test_one_bar_each_for_bond_hunger_seeds_and_escape(ctx):
    status = Brain(ctx, Idle()).status()
    assert [row.title for row in rows(status)] == ["Bond ♥", "Fullness", "Seeds", "Escape"]


def test_the_bond_bar_shows_how_close_he_feels(ctx):
    brain = Brain(ctx, Idle())
    ctx.bond.level = 0.85
    row = by_title(brain.status())["Bond ♥"]
    assert row.share == pytest.approx(0.85) and row.value == "85% · devoted"
    ctx.bond.level = 0.2
    assert by_title(brain.status())["Bond ♥"].value == "20% · grumpy"


def test_the_hunger_bar_is_his_fullness_with_his_odds_beside_it(ctx):
    brain = Brain(ctx, Idle())
    ctx.hunger.fullness = 0.9
    row = by_title(brain.status())["Fullness"]
    assert row.share == pytest.approx(0.9) and row.value == "90% · not peckish"
    ctx.hunger.fullness = 0.2
    status = brain.status()
    row = by_title(status)["Fullness"]
    assert 0 < status.hunger_chance < 1
    assert row.value.startswith("20% · ") and f"{status.hunger_chance:.0%} hungry in" in row.value
    ctx.hunger.hungry = True
    assert by_title(brain.status())["Fullness"].value == "20% · hungry now!"


def test_the_emptier_he_is_the_higher_his_odds(ctx):
    brain = Brain(ctx, Idle())
    ctx.hunger.fullness = 0.5
    half = brain.status().hunger_chance
    ctx.hunger.fullness = 0.2
    assert 0 < half < brain.status().hunger_chance


def test_the_escape_bar_fills_towards_his_first_try_then_shows_his_odds(ctx):
    brain = Brain(ctx, Idle())
    row = by_title(brain.status())["Escape"]
    assert row.share == 0 and "5:00 to go (paused)" in row.value  # never caged yet
    ctx.escape.caged_for = 2 * 60
    assert by_title(brain.status())["Escape"].share == pytest.approx(0.4)
    ctx.escape.caged_for = 6 * 60 + 10
    ctx.escape.next_try = 7 * 60
    status = brain.status()
    row = by_title(status)["Escape"]
    assert status.escape_started and row.share == pytest.approx(status.escape_chance)
    assert row.value == f"{status.escape_chance:.0%} at next try (paused)"


def test_caged_it_shows_his_dish_and_the_countdown_running(ctx):
    brain = Brain(ctx, Idle())
    brain.catch_in(ctx.body.x - 40, ctx.body.y - 80, ctx.body.x + 40, ctx.body.y + 5)
    brain.feed()
    rows_ = by_title(brain.status())
    assert rows_["Dish"].value == "1/3 stacks"
    assert "5:00 to go" in rows_["Escape"].value and "paused" not in rows_["Escape"].value


def test_the_panel_draws(ctx):
    panel = StatusPanel(Brain(ctx, Idle()).status)
    panel.resize(panel.sizeHint())
    assert not panel.grab().isNull()


def test_clock():
    assert clock(0) == "0:00" and clock(65.4) == "1:05" and clock(-3) == "0:00"
