"""Everything a behaviour state may read or change."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from zengo.animation import Animator
from zengo.behavior.body import Body
from zengo.behavior.cage import Cage
from zengo.behavior.food import Food, Hunger
from zengo.behavior.petting import PettingSensor
from zengo.behavior.scenery import Scenery
from zengo.config import Config
from zengo.world import Area, World


@dataclass
class Speech:
    """Words in a cloud above his head: a whistle, a heart, a complaint."""

    text: str
    remaining: float
    mood: str = "plain"
    """``"plain"``, ``"love"`` or ``"angry"``: how the cloud is coloured."""


@dataclass
class Context:
    body: Body
    world: World
    animator: Animator
    config: Config
    rng: random.Random
    scenery: Scenery = field(default_factory=Scenery)
    petting: PettingSensor = field(default_factory=PettingSensor)
    speech: Speech | None = None
    cage: Cage | None = None
    food: Food | None = None
    hunger: Hunger = field(default_factory=Hunger)

    def say(self, text: str, seconds: float, mood: str = "plain") -> None:
        self.speech = Speech(text, seconds, mood)

    def area(self) -> Area:
        # Probe slightly above the feet: the ground line is the area's exclusive bottom edge.
        return self.world.area_at(self.body.x, self.body.y - self.config.px(4))

    @property
    def margin(self) -> float:
        """Closest the anchor may get to a screen edge without the sprite leaving it."""
        return self.config.px(self.config.edge_margin)
