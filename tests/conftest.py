from __future__ import annotations

import os
import random
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

    def area_at(self, x: float, y: float) -> Area:
        return self.area

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


@pytest.fixture
def ctx(world: FakeWorld) -> Context:
    return Context(
        body=Body(x=960, y=1040),
        world=world,
        animator=Animator(CLIPS, initial="idle"),
        config=Config(),
        rng=random.Random(1234),
    )
