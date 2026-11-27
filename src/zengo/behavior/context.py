"""Everything a behaviour state may read or change."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from zengo.animation import Animator
from zengo.behavior.body import Body
from zengo.behavior.cage import Cage, EscapeProgress
from zengo.behavior.food import Food, Hunger
from zengo.behavior.petting import PettingSensor
from zengo.behavior.scenery import Scenery
from zengo.behavior.typing import TypingSensor
from zengo.config import Config
from zengo.sounds import whistle_for
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
    typing: TypingSensor = field(default_factory=TypingSensor)
    speech: Speech | None = None
    cage: Cage | None = None
    sounds: list[str] = field(default_factory=list)
    """Sounds he's made since the app last played them."""
    sound_on: bool = True
    """Your setting: whether his sounds play at all."""
    escape: EscapeProgress = field(default_factory=EscapeProgress)
    food: Food | None = None
    hunger: Hunger = field(default_factory=Hunger)

    def say(self, text: str, seconds: float, mood: str = "plain") -> None:
        self.speech = Speech(text, seconds, mood)

    def play(self, sound: str) -> None:
        """Make a sound (see :mod:`zengo.sounds`); the app plays it if sound is on."""
        self.sounds.append(sound)

    def whistle(self) -> None:
        """A whistle: one of his phrases in a cloud, and its tune."""
        phrase = self.rng.randrange(len(self.config.whistles))
        self.say(self.config.whistles[phrase], self.config.speech_seconds)
        self.play(whistle_for(phrase))

    def area(self) -> Area:
        # Probe slightly above the feet: the ground line is the area's exclusive bottom edge.
        return self.world.area_at(self.body.x, self.body.y - self.config.px(4))

    @property
    def margin(self) -> float:
        """Closest the anchor may get to a screen edge without the sprite leaving it."""
        return self.config.px(self.config.edge_margin)
