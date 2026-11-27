"""Your settings: kept in their own file, laid over the defaults, under the flags."""

from dataclasses import replace

from zengo.app import parse_args
from zengo.config import Config
from zengo.settings import Flags, Settings, build_config, migrated


def test_the_default_settings_change_nothing():
    assert build_config(Settings()) == Config()


def test_settings_are_laid_over_the_defaults():
    config = build_config(Settings(scale=4, branch="often", appetite="fast"))
    assert config.scale == 4
    assert config.branch_every == (300.0, 600.0)
    assert config.hunger_drain == Config.hunger_drain * 2
    assert build_config(Settings(appetite="slow")).hunger_drain == Config.hunger_drain / 2
    assert build_config(Settings(branch="rarely")).branch_every == (1200.0, 2400.0)


def test_flags_win_over_settings_and_quick_wins_over_appetite():
    settings = Settings(scale=4, appetite="slow")
    assert build_config(settings, Flags(scale=1)).scale == 1  # below the settings' range
    assert build_config(settings, Flags(fps=60)).fps == 60
    assert build_config(settings).scale == 4  # no flag: the setting stands
    assert build_config(settings, Flags(quick=True)).hunger_drain == 0.6


def test_flags_left_out_dont_override_anything():
    options = parse_args([])
    assert options.flags == Flags()
    assert parse_args(["--scale", "3", "--quick"]).flags == Flags(scale=3, quick=True)


def test_settings_round_trip_through_json():
    settings = Settings(scale=5, sound=False, volume=0.8, branch="rarely", appetite="fast")
    assert Settings.from_json(settings.to_json()) == settings


def test_a_damaged_file_reads_as_the_defaults():
    for data in (None, [], "scale=4", 3):
        assert Settings.from_json(data) == Settings()


def test_one_bad_value_falls_back_on_its_own():
    data = {**Settings(scale=4, appetite="fast").to_json(), "volume": "loud", "branch": "daily"}
    data["extra"] = "ignored"
    settings = Settings.from_json(data)
    assert (settings.scale, settings.appetite) == (4, "fast")  # kept
    assert (settings.volume, settings.branch) == (Settings.volume, Settings.branch)  # reset


def test_values_out_of_range_are_not_taken():
    assert Settings.from_json({"scale": 9}).scale == Settings.scale
    assert Settings.from_json({"scale": 1}).scale == Settings.scale
    assert Settings.from_json({"scale": 3.5}).scale == Settings.scale
    assert Settings.from_json({"scale": True}).scale == Settings.scale
    assert Settings.from_json({"volume": 7}).volume == 1.0  # clamped
    assert Settings.from_json({"volume": -1}).volume == 0.0
    assert Settings.from_json({"volume": float("nan")}).volume == Settings.volume
    assert Settings.from_json({"sound": "no"}).sound is True


def test_sound_moves_over_from_an_old_state_file_once():
    old_state = {"version": 1, "settings": {"sound": False}}
    assert migrated(None, old_state) == replace(Settings(), sound=False)
    assert migrated({"scale": 4}, old_state) == Settings(scale=4, sound=False)
    assert migrated({"sound": True}, old_state) is None  # the settings already say
    assert migrated(None, {"version": 1}) is None  # nothing to move
    assert migrated(None, None) is None


def test_turning_sound_off_in_the_menu_is_saved_in_the_settings(tmp_path):
    import random

    from zengo.app import Pet
    from zengo.sprites.frames import build_frames
    from zengo.ui.state_file import StateFile

    memory, file = StateFile(tmp_path / "state.json"), StateFile(tmp_path / "settings.json")
    pet = Pet(Config(), build_frames(), random.Random(1), memory=memory, settings_file=file)
    assert not file.path.exists()  # nothing written until something changes
    pet.change_settings(replace(pet.settings, sound=False))  # from the settings window
    assert pet._brain.ctx.sound_on is False
    assert Settings.from_json(file.load()).sound is False
    pet.save()
    assert "settings" not in memory.load()  # no longer kept with what he remembers
