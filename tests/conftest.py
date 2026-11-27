from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass, field

import pytest

from zengo.animation import Animator
from zengo.behavior.body import Body
from zengo.behavior.context import Context
from zengo.config import Config
from zengo.sprites.clips import CLIPS
from zengo.world import Area, Ledge, Window


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    """One full Qt application for the whole run, created before any test needs one.

    Widget tests need a QApplication; if a test made a plain QGuiApplication first,
    widgets would crash. The behaviour tests never touch Qt; it costs them nothing.
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # no display needed
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@dataclass
class FakeWorld:
    """A single 1920x1040 screen (taskbar excluded) with a controllable cursor and clock."""

    area: Area = field(default_factory=lambda: Area(0, 0, 1920, 1040))
    cursor_pos: tuple[float, float] = (5000.0, 5000.0)  # off-screen: out of watch range
    idle: float = 0.0
    hour: int = 12
    input_idle: float | None = None
    windows_on_top: list[Ledge] = field(default_factory=list)
    """Visible window tops to perch on."""
    live_windows: dict[int, Window] = field(default_factory=dict)
    """Where windows are this instant, when that's newer than ``windows_on_top``."""
    """Seconds since any input; None: the system won't say."""

    screens: list[Area] | None = None
    """Several screens, when a test wants them; otherwise just ``area``."""

    def areas(self) -> list[Area]:
        return list(self.screens) if self.screens else [self.area]

    def area_at(self, x: float, y: float) -> Area:
        if not self.screens:
            return self.area
        from zengo.world import nearest

        return nearest(self.screens, x, y)

    def cursor(self) -> tuple[float, float]:
        return self.cursor_pos

    def user_idle_seconds(self) -> float:
        return self.idle

    def ledges(self) -> list[Ledge]:
        return self.windows_on_top

    def window_frame(self, window: int) -> Window | None:
        return self.live_windows.get(window)

    def input_idle_seconds(self) -> float | None:
        return self.input_idle

    def local_hour(self) -> int:
        return self.hour


@pytest.fixture
def world() -> FakeWorld:
    return FakeWorld()


FIXED_DATE = tuple(int(n) for n in os.environ.get("ZENGO_TEST_DATE", "2026-11-15").split("-"))
"""The date the tests run on, whatever today is: seasons change what he does.
(Set ``ZENGO_TEST_DATE=2027-01-15`` to run them all in another season.)"""


def fixed_clock() -> float:
    year, month, day = FIXED_DATE
    return time.mktime((year, month, day, 12, 0, 0, 0, 0, -1))


@pytest.fixture
def ctx(world: FakeWorld) -> Context:
    return Context(
        body=Body(x=960, y=1040),
        world=world,
        animator=Animator(CLIPS, initial="idle"),
        config=Config(),
        rng=random.Random(1234),
        clock=fixed_clock,
    )


@pytest.fixture
def make_pet(tmp_path):
    """Makes a started Pet with its files in a temporary folder; closed afterwards."""
    from zengo.app import Pet
    from zengo.settings import Flags, Settings, build_config
    from zengo.sprites.frames import build_frames
    from zengo.ui.state_file import StateFile

    made = []

    def make(flags=None, settings=None, **extra):
        flags, settings = flags or Flags(), settings or Settings()
        pet = Pet(
            build_config(settings, flags),
            build_frames(),
            random.Random(1),
            memory=StateFile(tmp_path / "state.json"),
            settings=settings,
            settings_file=StateFile(tmp_path / "settings.json"),
            flags=flags,
            **extra,
        )
        pet._brain.ctx.clock = fixed_clock
        pet.start()
        made.append(pet)
        return pet

    yield make
    for pet in made:
        pet._timer.stop()
        for window in (pet._window, *pet._scaled_windows()):
            window.close()
        if pet._settings_window is not None:
            pet._settings_window.close()
