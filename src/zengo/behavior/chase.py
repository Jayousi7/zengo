"""The chasing game: wiggle the pointer quickly near him and he's after it.

A wiggle is the pointer darting back and forth (several changes of direction
within a second), fast: much faster than a stroke (see ``petting.py``), so the
two can't be taken for each other. It has to be near him, on his screen.

Pure Python: no Qt.
"""

from __future__ import annotations

import itertools
import math
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zengo.behavior.context import Context


@dataclass
class WiggleSensor:
    window: float = 1.0
    """Seconds of pointer history looked at."""
    min_reversals: int = 4
    min_speed: float = 400.0
    """Art px/s, at least: well above the fastest stroke petting allows."""
    reach: float = 160.0
    """Art px from him (sideways) the pointer may be, and above the ground."""

    active: bool = False
    _time: float = 0.0
    _samples: deque[tuple[float, float, float]] = field(default_factory=deque)

    def update(self, ctx: Context, dt: float) -> None:
        self._time += dt
        x, y = ctx.world.cursor()
        self._samples.append((self._time, x, y))
        while self._samples and self._samples[0][0] < self._time - self.window:
            self._samples.popleft()
        self.active = self._near(ctx, x, y) and self._wiggling(ctx)
        if self.active:
            self._samples.clear()  # one wiggle, one start

    def _near(self, ctx: Context, x: float, y: float) -> bool:
        cfg, area = ctx.config, ctx.area()
        return (
            ctx.world.area_at(x, y) == area
            and abs(x - ctx.body.x) <= cfg.px(self.reach)
            and area.bottom - cfg.px(self.reach) <= y <= area.bottom
        )

    def _wiggling(self, ctx: Context) -> bool:
        samples = list(self._samples)
        if len(samples) < 6:
            return False
        travel, reversals, last = 0.0, 0, 0.0
        for (_, x0, y0), (_, x1, y1) in itertools.pairwise(samples):
            dx = x1 - x0
            travel += math.hypot(dx, y1 - y0)
            if abs(dx) > 1.0:
                reversals += last * dx < 0
                last = dx
        span = samples[-1][0] - samples[0][0] or 1.0
        return reversals >= self.min_reversals and travel / span >= ctx.config.px(self.min_speed)
