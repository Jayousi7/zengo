"""The settings window, and settings changed while he runs."""

import random

import pytest

from zengo.behavior.food import Hunger
from zengo.settings import Flags, Settings, build_config
from zengo.sprites.frames import build_frames


@pytest.fixture
def pet(tmp_path):
    from zengo.app import Pet
    from zengo.ui.state_file import StateFile

    def make(flags=None, settings=None):
        flags, settings = flags or Flags(), settings or Settings()
        pet = Pet(
            build_config(settings, flags),
            build_frames(),
            random.Random(1),
            memory=StateFile(tmp_path / "state.json"),
            settings=settings,
            settings_file=StateFile(tmp_path / "settings.json"),
            flags=flags,
        )
        pet.start()
        made.append(pet)
        return pet

    made = []
    yield make
    for p in made:
        p._timer.stop()
        for window in (p._window, p._cage, p._mount, p._branch, p._bubble, p._food, p._dish):
            window.close()
        if p._settings_window is not None:
            p._settings_window.close()


def test_the_window_shows_the_settings_and_reports_changes():
    from zengo.ui.settings_window import SettingsWindow

    window = SettingsWindow(Settings(scale=3, appetite="slow"))
    general = window.general
    assert general.size.currentData() == 3 and general.appetite.currentData() == "slow"
    changes = []
    window.changed.connect(changes.append)
    general.branch.setCurrentIndex(general.branch.findData("often"))
    general.sound.setChecked(False)
    assert changes == [
        Settings(scale=3, appetite="slow", branch="often"),
        Settings(scale=3, appetite="slow", branch="often", sound=False),
    ]
    assert not general.volume.isEnabled()  # no volume with the sound off
    window.show_settings(Settings())  # shown, not changed
    assert len(changes) == 2
    window.close()


def test_size_is_locked_when_set_on_the_command_line():
    from zengo.ui.settings_window import SettingsWindow

    window = SettingsWindow(Settings(), scale_locked=True)
    assert not window.general.size.isEnabled()
    window.close()


def test_changing_size_redraws_him_at_once(pet):
    pet = pet()
    pet.open_settings()
    general = pet._settings_window.general
    general.size.setCurrentIndex(general.size.findData(4))
    assert pet._config.scale == 4 and pet._brain.ctx.config.scale == 4
    assert pet._sheet.get("perch", pet._brain.ctx.body.facing).pixmap.width() > 200
    assert pet._cage._config.scale == 4  # the other windows too
    assert Settings.from_json(pet._settings_file.load()).scale == 4  # and it's kept


def test_a_caged_bird_stays_hung_when_he_grows(pet):
    pet = pet()
    brain, ctx = pet._brain, pet._brain.ctx
    assert brain.catch_in(ctx.body.x - 40, ctx.body.y - 80, ctx.body.x + 40, ctx.body.y + 10)
    cage = ctx.cage
    brain.cage_grab(cage.x, cage.y)
    brain.cage_drag(900, ctx.world.area_at(900, 300).top + 40)
    brain.cage_release()
    assert cage.mount == "chain"
    pet.change_settings(Settings(scale=4))
    assert cage.mount == "chain" and cage.top(ctx) >= cage.pivot[1]


def test_appetite_changes_with_flags_kept(pet):
    pet = pet(flags=Flags(quick=True))
    pet.change_settings(Settings(appetite="slow", branch="often"))
    config = pet._brain.ctx.config
    assert config.hunger_drain == 0.6  # --quick still wins
    assert config.escape_after == 5.0
    assert config.branch_every == (300.0, 600.0)


def test_dragging_the_volume_applies_it_but_keeps_it_only_when_let_go(pet):
    pet = pet()
    pet.change_settings(Settings(volume=0.8), keep=False)
    assert pet.settings.volume == 0.8
    assert pet._settings_file.load() is None
    pet.change_settings(Settings(volume=0.8))
    assert Settings.from_json(pet._settings_file.load()).volume == 0.8


def test_reset_forgets_him_but_keeps_your_settings(pet):
    pet = pet()
    pet.change_settings(Settings(appetite="fast"))
    ctx = pet._brain.ctx
    ctx.bond.level, ctx.hunger.fullness = 0.95, 0.2
    ctx.escape.caged_for = 500.0
    pet._brain.feed()
    assert pet._brain.catch_in(ctx.body.x - 40, ctx.body.y - 80, ctx.body.x + 40, ctx.body.y + 10)
    pet.reset()
    assert ctx.bond.level == 0.5 and ctx.hunger.fullness == Hunger().fullness
    assert ctx.cage is None and ctx.food is None
    assert ctx.escape.caged_for == 0.0
    assert not pet._brain.caged
    saved = pet._memory.load()
    assert saved["bond"] == 0.5 and saved["cage"] is None
    assert pet.settings.appetite == "fast"


def test_a_volume_dragged_with_the_slider_is_kept_when_let_go(pet):
    pet = pet()
    pet.open_settings()
    volume = pet._settings_window.general.volume
    volume.setSliderDown(True)
    volume.setValue(80)
    assert pet.settings.volume == 0.8  # heard at once
    assert pet._settings_file.load() is None  # not saved mid-drag
    volume.setSliderDown(False)  # let go
    assert Settings.from_json(pet._settings_file.load()).volume == 0.8


# --- The Life tab ------------------------------------------------------------------


def test_the_life_tab_puts_toys_out_and_away(make_pet):
    pet = make_pet()
    pet.open_settings()
    life = pet._settings_window.life
    life.toys["mirror"].setChecked(True)
    assert pet.settings.toys == ("mirror",)
    pet._brain.tick(0.1)
    assert pet._brain.ctx.toys.mirror is not None
    life.toys["bell"].setChecked(True)
    life.toys["mirror"].setChecked(False)
    assert pet.settings.toys == ("bell",)
    assert Settings.from_json(pet._settings_file.load()).toys == ("bell",)


def test_the_life_tab_sets_baths_and_seasons(make_pet):
    pet = make_pet()
    pet.open_settings()
    life = pet._settings_window.life
    life.baths.setCurrentIndex(life.baths.findData("often"))
    assert pet._config.bath_every == (900.0, 1800.0)
    life.hemisphere.setCurrentIndex(life.hemisphere.findData("south"))
    assert pet._brain.ctx.seasons.hemisphere == "south"
    life.seasons.setChecked(False)
    assert pet._brain.ctx.season() is None
    assert not life.hemisphere.isEnabled()


def test_the_hemisphere_choice_says_what_the_time_zone_gave(make_pet):
    from zengo.ui.settings_window import SettingsWindow

    window = SettingsWindow(Settings(), hemisphere_found="south")
    assert "southern" in window.life.hemisphere.itemText(0)
    window.close()


# --- The Focus tab -------------------------------------------------------------------


def test_the_focus_tab_sets_the_lengths_and_runs_the_timer(make_pet):
    pet = make_pet()
    pet.open_settings("Focus")
    window = pet._settings_window
    assert window.tabs.tabText(window.tabs.currentIndex()) == "Focus"
    tab = window.focus
    tab.focus.setValue(40)
    tab.next_session.setCurrentIndex(tab.next_session.findData("auto"))
    assert pet.settings.focus_minutes == 40 and pet.settings.next_session == "auto"
    tab.start_button.click()
    ctx = pet._brain.ctx
    assert ctx.focus.focusing and ctx.focus.session.focus == 40 * 60
    pet._render()
    assert "40:00 left of focus" in tab.state.text()
    assert not tab.start_button.isEnabled() and tab.pause_button.isEnabled()
    tab.pause_button.click()
    pet._render()
    assert ctx.focus.paused and tab.pause_button.text() == "Resume"
    tab.stop_button.click()
    assert ctx.focus.phase == "off"
    tab._reset()
    assert pet.settings.focus_minutes == 25 and pet.settings.short_break_minutes == 5


def test_the_needs_strip_shows_the_time_left(make_pet):
    from zengo.ui.status_panel import rows

    pet = make_pet()
    assert not any(row.title == "Focus" for row in rows(pet._brain.status()))
    pet.start_focus()
    focus_rows = [row for row in rows(pet._brain.status()) if row.title == "Focus"]
    assert focus_rows and focus_rows[0].headline == "25:00"
