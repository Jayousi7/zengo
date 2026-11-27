"""Remembering fullness, hunger and seeds between runs."""

import json

import pytest

from zengo.behavior.food import Food, Pile
from zengo.behavior.memory import restore, snapshot
from zengo.ui.state_file import StateFile


def test_fullness_hunger_and_seeds_survive_a_round_trip_through_the_file(ctx, tmp_path):
    ctx.hunger.fullness, ctx.hunger.hungry = 0.42, True
    ctx.hunger._check_in, ctx.hunger._ask_in = 12.0, 33.0
    ctx.food = Food(800, ctx.world.area.bottom, Pile(seeds=13, shown=13))
    file = StateFile(tmp_path / "zengo" / "state.json")
    file.save(snapshot(ctx))

    ctx.hunger.fullness, ctx.hunger.hungry, ctx.food = 1.0, False, None
    restore(ctx, file.load())
    assert ctx.hunger.fullness == pytest.approx(0.42)
    assert ctx.hunger.hungry
    assert ctx.hunger.check_in == pytest.approx(12.0)
    assert ctx.hunger._ask_in == pytest.approx(33.0)
    assert ctx.food is not None and ctx.food.pile.seeds == 13 and ctx.food.x == 800
    assert ctx.food.y == ctx.world.area.bottom


def test_no_seeds_out_means_none_after_a_restart(ctx, tmp_path):
    file = StateFile(tmp_path / "state.json")
    file.save(snapshot(ctx))
    ctx.food = Food(500, 1040, Pile(seeds=8))
    restore(ctx, file.load())
    assert ctx.food.pile.seeds == 8  # nothing remembered to replace it with...
    ctx.food = None
    restore(ctx, file.load())
    assert ctx.food is None


@pytest.mark.parametrize(
    "contents",
    [
        "",
        "not json {",
        "[]",
        json.dumps({"version": 99, "hunger": {"fullness": 0.1}}),
        json.dumps({"version": 1, "hunger": {"fullness": "lots", "hungry": "yes"}}),
        json.dumps({"version": 1, "food": {"x": "here", "seeds": 5}}),
    ],
)
def test_a_damaged_or_strange_file_is_shrugged_off(ctx, tmp_path, contents):
    path = tmp_path / "state.json"
    path.write_text(contents)
    before = (ctx.hunger.fullness, ctx.hunger.hungry, ctx.food)
    restore(ctx, StateFile(path).load())
    assert (ctx.hunger.fullness, ctx.hunger.hungry, ctx.food) == before


def test_a_missing_file_means_a_fresh_start(ctx, tmp_path):
    assert StateFile(tmp_path / "nowhere" / "state.json").load() is None


def test_out_of_range_values_are_brought_back_into_range(ctx):
    restore(ctx, {"version": 1, "hunger": {"fullness": 7.5}, "food": {"x": 1e9, "seeds": 999}})
    assert ctx.hunger.fullness == 1.0
    assert ctx.food.pile.seeds == 24
    area = ctx.world.area
    assert area.left < ctx.food.x < area.right  # back on his screen, within his reach


def test_saving_replaces_the_file_whole_and_leaves_no_temporary_files(ctx, tmp_path):
    file = StateFile(tmp_path / "state.json")
    for fullness in (0.9, 0.5, 0.1):
        ctx.hunger.fullness = fullness
        file.save(snapshot(ctx))
    assert json.loads(file.path.read_text())["hunger"]["fullness"] == 0.1
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]


def test_a_save_that_cannot_be_written_does_not_crash(ctx, tmp_path, capsys):
    blocker = tmp_path / "a_file"
    blocker.write_text("")
    file = StateFile(blocker / "state.json")  # its folder is a file: can't be made
    file.save(snapshot(ctx))
    file.save(snapshot(ctx))
    assert capsys.readouterr().err.count("can't save state") == 1  # said once


def test_the_app_remembers_across_a_restart(tmp_path):
    import random

    from zengo.app import Pet
    from zengo.config import Config
    from zengo.sprites.frames import build_frames

    file = StateFile(tmp_path / "state.json")
    first = Pet(Config(), build_frames(), random.Random(1), memory=file)
    first._brain.ctx.hunger.fullness = 0.3
    first._brain.feed()
    first._brain.feed()
    first.save()

    second = Pet(Config(), build_frames(), random.Random(2), memory=file)
    ctx = second._brain.ctx
    assert ctx.hunger.fullness == pytest.approx(0.3)
    assert second._brain.food_stacks == 2
