"""Everything a behaviour state may read or change."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from zengo.animation import Animator
from zengo.behavior.bath import BathCycle
from zengo.behavior.body import Body
from zengo.behavior.bond import Bond
from zengo.behavior.cage import Cage, EscapeProgress
from zengo.behavior.effects import Effects
from zengo.behavior.focus import Focus
from zengo.behavior.food import Food, Hunger
from zengo.behavior.moult import Moult
from zengo.behavior.petting import PettingSensor
from zengo.behavior.scenery import Scenery
from zengo.behavior.seasons import Seasons
from zengo.behavior.toys import Toys
from zengo.behavior.typing import TypingSensor
from zengo.behavior.vocabulary import Vocabulary, garble, lessons_needed
from zengo.behavior.voice import Voice
from zengo.behavior.weather import Weather
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
    bond: Bond = field(default_factory=Bond)
    voice: Voice = field(default_factory=Voice)
    """What he says at each moment, and which of his sounds you've replaced."""
    vocabulary: Vocabulary = field(default_factory=Vocabulary)
    """Words you've taught him, learned or still being learned."""
    clock: Callable[[], float] = time.time
    """Wall-clock time, for lessons an hour apart across restarts."""
    talking: bool = False
    """He's just said one of your words: the app shows his beak working."""
    seasons: Seasons = field(default_factory=Seasons)
    bath: BathCycle = field(default_factory=BathCycle)
    moult: Moult = field(default_factory=Moult)
    toys: Toys = field(default_factory=Toys)
    focus: Focus = field(default_factory=Focus)
    weather: Weather = field(default_factory=Weather)
    effects: Effects = field(default_factory=Effects)
    """Droplets, snowflakes and leaves in the air."""
    damp: float = 0.0
    """Seconds until he's dry after a bath."""

    def season(self) -> str | None:
        """The time of year as he shows it, or ``None`` with seasons turned off."""
        return self.seasons.now(self.clock())

    def say(self, text: str, seconds: float, mood: str = "plain") -> None:
        self.speech = Speech(text, seconds, mood)

    def words_needed(self) -> int:
        """Lessons he needs to learn a word, as close as he feels to you now."""
        return lessons_needed(self.bond.level, self.config.bond_close)

    def phrase(self, moment: str) -> str:
        """Something to say at ``moment`` (see :data:`zengo.behavior.voice.MOMENTS`):
        one of the moment's phrases, or as often as not a word you've taught him for
        it. Now and then he practises a word he's still learning, garbled."""
        needed = self.words_needed()
        taught = self.vocabulary.learned(moment, needed)
        if taught and self.rng.random() < 0.5:
            word = self.rng.choice(taught)
            word.uses += 1
            self.talking = True
            return word.text
        learning = self.vocabulary.learning(needed)
        if moment == "random" and learning and self.rng.random() < 0.3:
            word = self.rng.choice(learning)
            self.talking = True
            return garble(word.text, word.lessons / needed, self.rng)
        return self.rng.choice(self.voice.lines(moment))

    @property
    def hushed(self) -> bool:
        """You're focusing: he keeps quiet."""
        return self.focus.focusing

    def play(self, sound: str) -> None:
        """Make a sound (see :mod:`zengo.sounds`); the app plays it if sound is on.
        Not a peep while you're focusing."""
        if not self.hushed:
            self.sounds.append(sound)

    def whistle(self) -> None:
        """A whistle: one of his phrases in a cloud, and its tune."""
        whistles = self.voice.lines("whistle")
        phrase = self.rng.randrange(len(whistles))
        if self.bond.close(self.config) and self.rng.random() < 0.25:
            self.say("♥", self.config.speech_seconds, mood="love")  # devoted
        else:
            self.say(whistles[phrase], self.config.speech_seconds)
        self.play(whistle_for(phrase))

    def area(self) -> Area:
        # Probe slightly above the feet: the ground line is the area's exclusive bottom edge.
        return self.world.area_at(self.body.x, self.body.y - self.config.px(4))

    @property
    def margin(self) -> float:
        """Closest the anchor may get to a screen edge without the sprite leaving it."""
        return self.config.px(self.config.edge_margin)
