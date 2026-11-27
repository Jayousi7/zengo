"""Everything a behaviour state may read or change."""

from __future__ import annotations

import random
from dataclasses import dataclass

from zengo.animation import Animator
from zengo.behavior.body import Body
from zengo.config import Config
from zengo.world import Area, World


@dataclass
class Context:
    body: Body
    world: World
    animator: Animator
    config: Config
    rng: random.Random

    def area(self) -> Area:
        # Probe slightly above the feet: the ground line is the area's exclusive bottom edge.
        return self.world.area_at(self.body.x, self.body.y - self.config.px(4))

    @property
    def margin(self) -> float:
        """Closest the anchor may get to a screen edge without the sprite leaving it."""
        return self.config.px(self.config.edge_margin)
