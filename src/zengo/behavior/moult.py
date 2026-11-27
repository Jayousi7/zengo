"""Moulting: now and then a feather comes loose and drifts down.

Every hour or two (more often in spring and autumn) a small feather falls from
him, swaying side to side, and stays where it lands until you click it away.
At most :data:`MAX_FEATHERS` lie about: when another falls, the oldest fades.
Some days are moulting days (likelier in spring and autumn): feathers come
twice as often and he preens more. Sitting on the branch in autumn, what
drops is sometimes a leaf instead.

Pure Python: no Qt.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zengo.behavior.context import Context

MAX_FEATHERS = 3
FALL_SPEED = 9.0
"""Art px/s a feather settles at."""
SWAY = 7.0
"""Art px it swings either side as it falls."""
FADE_SECONDS = 0.8
MOULT_SEASONS = ("spring", "autumn")
MOULTING_DAY_ODDS = {True: 0.5, False: 0.15}
"""Chance a day is a moulting day, in a moulting season or not."""


@dataclass
class Feather:
    x: float
    y: float
    """Screen position of its middle."""
    ground: float
    white: bool = False
    """A white one from his face, or a fawn one from his back."""
    phase: float = 0.0
    age: float = 0.0
    landed: bool = False
    fading: float | None = None
    """Seconds since it started fading: clicked away, or pushed out by a new one."""

    @property
    def alpha(self) -> float:
        return 1.0 if self.fading is None else max(0.0, 1.0 - self.fading / FADE_SECONDS)

    @property
    def tilt(self) -> int:
        """Which way it's tipped as it sways down: -1, 0 or 1 (0 once landed)."""
        if self.landed:
            return 0
        swing = math.cos(self.age * 1.8 + self.phase)
        return -1 if swing < -0.4 else 1 if swing > 0.4 else 0


@dataclass
class Moult:
    feathers: list[Feather] = field(default_factory=list)
    _timer: float | None = None
    _day: tuple[int, int, int] | None = None
    _moulting_day: bool = False

    def moulting_day(self, ctx: Context) -> bool:
        """Today is a moulting day: settled once a day, by the date."""
        today = time.localtime(ctx.clock())[:3]
        if today != self._day:
            self._day = today
            in_season = ctx.season() in MOULT_SEASONS
            self._moulting_day = ctx.rng.random() < MOULTING_DAY_ODDS[in_season]
        return self._moulting_day

    def _wait(self, ctx: Context) -> float:
        wait = ctx.rng.uniform(*ctx.config.moult_every)
        if ctx.season() in MOULT_SEASONS:
            wait *= 0.6
        return wait / 2 if self.moulting_day(ctx) else wait

    def update(self, ctx: Context, dt: float, *, free: bool, on_branch: bool = False) -> None:
        """Advance by ``dt``. ``free``: neither caged nor away, so one may fall."""
        if self._timer is None:
            self._timer = self._wait(ctx)
        self._timer -= dt
        if self._timer <= 0 and free:
            self._timer = self._wait(ctx)
            if on_branch and ctx.season() == "autumn" and ctx.rng.random() < 0.5:
                self._leaf(ctx)
            else:
                self.drop(ctx)
        scale = ctx.config.scale
        for feather in self.feathers:
            feather.age += dt
            if feather.fading is not None:
                feather.fading += dt
            elif not feather.landed:
                sway = SWAY * scale * math.cos(feather.age * 1.8 + feather.phase) * 1.8
                feather.x += sway * dt
                feather.y += FALL_SPEED * scale * dt
                if feather.y >= feather.ground:
                    feather.y, feather.landed = feather.ground, True
        self.feathers = [f for f in self.feathers if f.alpha > 0]

    def drop(self, ctx: Context) -> Feather:
        """A feather comes loose from his back now, and starts to fall."""
        cfg, body, area = ctx.config, ctx.body, ctx.area()
        behind = -int(body.facing) * cfg.px(ctx.rng.uniform(4, 14))
        feather = Feather(
            area.clamp_x(body.x + behind, cfg.px(6)),
            body.y - cfg.px(16),
            area.bottom - cfg.px(1),
            white=ctx.rng.random() < 0.3,
            phase=ctx.rng.uniform(0, math.tau),
        )
        lying = [f for f in self.feathers if f.fading is None]
        if len(lying) >= MAX_FEATHERS:
            lying[0].fading = 0.0  # the oldest makes way
        self.feathers.append(feather)
        return feather

    def _leaf(self, ctx: Context) -> None:
        """A leaf from the branch he's on, falling from under his feet."""
        cfg = ctx.config
        y = ctx.body.y + cfg.px(2)
        ctx.effects.falling("leaf", ctx.body.x, y, ctx.area().bottom - cfg.px(1), ctx.rng)

    def pick_up(self, index: int) -> None:
        """You clicked a feather: it fades away."""
        if 0 <= index < len(self.feathers) and self.feathers[index].fading is None:
            self.feathers[index].fading = 0.0
