"""Telling a stroke of the mouse over Zengo from just passing by.

Petting is the pointer moving gently back and forth over him: it changes
direction a few times, covers some ground, and isn't in a hurry. A pointer
resting on him, or a quick swipe across, isn't petting.
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
class PettingSensor:
    window: float = 1.5
    """Seconds of pointer history looked at."""
    min_reversals: int = 2
    """Changes of direction in that time: back, forth and back again."""
    min_travel: float = 20.0
    max_speed: float = 300.0
    """Art pixels moved in that time, at least, and art px/s, at most."""
    grace: float = 0.6
    """Seconds a pause between strokes still counts as being petted."""

    active: bool = False
    _time: float = 0.0
    _quiet_until: float = -math.inf
    _last_stroke: float = -math.inf
    _samples: deque[tuple[float, float, float, bool]] = field(default_factory=deque)

    def suppress(self, seconds: float = 1.0) -> None:
        """Ignore the pointer for a while: it's busy dragging him or his cage, which
        moves it back and forth over him just like a stroke would."""
        self._quiet_until = self._time + seconds
        self._samples.clear()
        self._last_stroke = -math.inf
        self.active = False

    def update(self, ctx: Context, dt: float) -> None:
        self._time += dt
        if self._time < self._quiet_until:
            return
        x, y = ctx.world.cursor()
        self._samples.append((self._time, x, y, _over_him(ctx, x, y)))
        while self._samples and self._samples[0][0] < self._time - self.window:
            self._samples.popleft()
        if self._stroking(ctx):
            self._last_stroke = self._time
        self.active = self._time - self._last_stroke <= self.grace

    def _stroking(self, ctx: Context) -> bool:
        samples = list(self._samples)
        if len(samples) < 6 or sum(over for *_, over in samples) < 0.8 * len(samples):
            return False
        cfg, travel, reversals = ctx.config, 0.0, 0
        last_dx = last_dy = 0.0
        for (_, x0, y0, _), (_, x1, y1, _) in itertools.pairwise(samples):
            dx, dy = x1 - x0, y1 - y0
            travel += math.hypot(dx, dy)
            if abs(dx) > 0.5:
                reversals += last_dx * dx < 0
                last_dx = dx
            if abs(dy) > 0.5:
                reversals += last_dy * dy < 0
                last_dy = dy
        span = samples[-1][0] - samples[0][0] or 1.0
        return (
            reversals >= self.min_reversals
            and travel >= cfg.px(self.min_travel)
            and travel / span <= cfg.px(self.max_speed)
        )


def _over_him(ctx: Context, x: float, y: float) -> bool:
    body, cfg = ctx.body, ctx.config
    return abs(x - body.x) <= cfg.px(14) and body.y - cfg.px(30) <= y <= body.y
