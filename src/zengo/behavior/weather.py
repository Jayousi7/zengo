"""What the season brings round him: snow past the branch in winter, leaves
falling from it in autumn. (His scarf, his songs and his panting are in his
looks and states.) All of it only with seasons turned on.

Pure Python: no Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from zengo.sprites.branch import BRANCH_WIDTH

if TYPE_CHECKING:
    from zengo.behavior.context import Context

SNOW_EVERY = (1.2, 3.5)
"""Seconds between snowflakes drifting past while he's on the branch in winter."""
LEAF_EVERY = (6.0, 15.0)
"""Seconds between leaves falling from the branch in autumn."""


@dataclass
class Weather:
    _snow_in: float = 0.0
    _leaf_in: float = 0.0

    def update(self, ctx: Context, dt: float, *, on_branch: bool) -> None:
        season = ctx.season()
        cfg, area, rng = ctx.config, ctx.area(), ctx.rng
        ground = area.bottom - cfg.px(1)
        if season == "winter" and on_branch:
            self._snow_in -= dt
            if self._snow_in <= 0:
                self._snow_in = rng.uniform(*SNOW_EVERY)
                x = ctx.body.x + cfg.px(rng.uniform(-110, 110))
                y = ctx.body.y - cfg.px(rng.uniform(60, 120))
                drift = cfg.px(rng.uniform(-4, 4))
                ctx.effects.falling("snow", x, max(area.top, y), ground, rng, drift)
        branch = ctx.scenery.branch
        if season == "autumn" and branch is not None and branch.ready:
            self._leaf_in -= dt
            if self._leaf_in <= 0:
                self._leaf_in = rng.uniform(*LEAF_EVERY)
                x = branch.x_at(rng.uniform(4, BRANCH_WIDTH - 6), cfg)
                y = branch.top + cfg.px(rng.uniform(-6, 6))
                ctx.effects.falling("leaf", x, y, ground, rng, cfg.px(rng.uniform(-3, 3)))
