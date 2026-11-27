from __future__ import annotations

import random
from dataclasses import dataclass, field

import pytest

from zengo.animation import Animator
from zengo.behavior.body import Body
from zengo.behavior.context import Context
from zengo.config import Config
from zengo.sprites.clips import CLIPS
from zengo.world import Area


@dataclass
class FakeWorld:
    """A single 1920x1040 screen (taskbar excluded) with a controllable cursor and clock."""

    area: Area = field(default_factory=lambda: Area(0, 0, 1920, 1040))
    cursor_pos: tuple[float, float] = (5000.0, 5000.0)  # off-screen: out of watch range
    idle: float = 0.0
    hour: int = 12

    def area_at(self, x: float, y: float) -> Area:
        return self.area

    def cursor(self) -> tuple[float, float]:
        return self.cursor_pos

    def user_idle_seconds(self) -> float:
        return self.idle

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
