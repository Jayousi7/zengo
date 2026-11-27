"""Food and hunger.

Seeds are put out a stack at a time, at most three stacks, in a pile on the
ground or in the dish on his cage's tray. He doesn't just eat whatever is put
down: every few minutes he may get hungry, and then he eats one stack. With
nothing put out, he comes and asks for some.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from zengo.sprites.food import MAX_SEEDS, PILE_WIDTH, SEEDS_PER_STACK

if TYPE_CHECKING:
    from zengo.behavior.context import Context

PECK_REACH = 16
"""Art px from his anchor to the tip of his beak when he pecks at the ground."""

STAND_OFF = PECK_REACH + PILE_WIDTH / 2 - 3
"""Art px from the middle of a pile to where he stands to eat from it: his beak
then lands just inside its near edge."""

SECONDS_PER_SEED = 1.04
"""One seed: peck it up, crack it, swallow (the length of the eating clips)."""

POUR_RATE = 16.0
"""Seeds a second appearing on the pile as a stack is poured on."""


@dataclass
class Pile:
    seeds: int = 0
    shown: float = 0.0
    """Seeds drawn. It catches up with ``seeds`` as a stack pours on, so you can
    see the pile fill; eating takes them off one at a time anyway."""

    @property
    def stacks(self) -> int:
        """Stacks' worth in the pile, counting a part-eaten one."""
        return -(-self.seeds // SEEDS_PER_STACK)

    @property
    def full(self) -> bool:
        return self.seeds > MAX_SEEDS - SEEDS_PER_STACK

    def add_stack(self) -> bool:
        """Pour on another stack. False if the pile is already full."""
        if self.full:
            return False
        self.seeds = min(MAX_SEEDS, self.seeds + SEEDS_PER_STACK)
        return True

    def take_seed(self) -> bool:
        if self.seeds <= 0:
            return False
        self.seeds -= 1
        self.shown = min(self.shown, self.seeds)
        return True

    def update(self, dt: float) -> None:
        if self.shown < self.seeds:
            self.shown = min(self.seeds, self.shown + POUR_RATE * dt)
        else:
            self.shown = self.seeds


@dataclass
class Food:
    """The seed pile on the ground."""

    x: float
    """Screen x of the middle of the pile."""
    y: float
    """Screen y of the ground it rests on."""
    pile: Pile = field(default_factory=Pile)


@dataclass
class Hunger:
    """Every ``hunger_every`` seconds, a ``hunger_chance`` he gets hungry. Hungry, he
    stays hungry until he's eaten a stack; with nothing to eat he asks for food,
    and asks again every ``nag_every`` seconds until fed."""

    hungry: bool = False
    _roll_in: float | None = None
    _ask_in: float = 0.0

    def update(self, ctx: Context, dt: float) -> None:
        cfg = ctx.config
        if self._roll_in is None:
            self._roll_in = cfg.hunger_every
        if self.hungry:
            self._ask_in -= dt
            return
        self._roll_in -= dt
        if self._roll_in <= 0:
            self._roll_in += cfg.hunger_every
            if ctx.rng.random() < cfg.hunger_chance:
                self.hungry, self._ask_in = True, 0.0

    @property
    def wants_to_ask(self) -> bool:
        return self.hungry and self._ask_in <= 0

    def asked(self, ctx: Context) -> None:
        self._ask_in = ctx.config.nag_every

    def fed(self) -> None:
        self.hungry = False
