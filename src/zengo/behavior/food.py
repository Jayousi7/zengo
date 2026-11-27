"""Food and hunger.

Seeds are put out a stack at a time, at most three stacks, in a pile on the
ground or in the dish on his cage's tray. He doesn't just eat whatever is put
down: he eats when he's hungry, and how likely that is follows how full he is,
which drains with time and activity (see :class:`Hunger`). A meal is up to one
stack. With nothing put out, he comes and asks for some.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from zengo.sprites.food import MAX_SEEDS, PILE_WIDTH, SEEDS_PER_STACK

if TYPE_CHECKING:
    from zengo.behavior.context import Context
    from zengo.config import Config

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
    """How full he is, and whether he's hungry.

    ``fullness`` runs from 1 (stuffed) to 0 (empty). It drains with time, faster
    the harder he's working (see ``State.effort``): flying burns far more than
    sitting, sleeping hardly anything. Every seed he eats tops it up.

    Getting hungry is still a matter of chance, but the chance follows the
    meter: every ``hunger_check_every`` seconds he may get hungry, never while
    he's well fed, more and more likely as he empties, certain at empty (see
    :func:`hunger_chance`). Hungry, he stays so until he's had a meal; with
    nothing to eat he asks for food, and asks again every ``nag_every`` seconds.
    """

    fullness: float = 0.8
    hungry: bool = False
    _check_in: float | None = None
    _ask_in: float = 0.0

    def update(self, ctx: Context, dt: float, effort: float = 1.0) -> None:
        cfg = ctx.config
        self.fullness = max(0.0, self.fullness - cfg.hunger_drain / 60 * effort * dt)
        if self.hungry:
            self._ask_in -= dt
            return
        if self._check_in is None:
            self._check_in = cfg.hunger_check_every
        self._check_in -= dt
        if self._check_in <= 0:
            self._check_in += cfg.hunger_check_every
            if ctx.rng.random() < hunger_chance(cfg, self.fullness):
                self.hungry, self._ask_in = True, 0.0

    @property
    def check_in(self) -> float:
        """Seconds to the next time he may get hungry."""
        return max(0.0, self._check_in or 0.0)

    @property
    def wants_to_ask(self) -> bool:
        return self.hungry and self._ask_in <= 0

    def asked(self, ctx: Context) -> None:
        self._ask_in = ctx.config.nag_every

    def ate_seed(self, ctx: Context) -> None:
        self.fullness = min(1.0, self.fullness + ctx.config.seed_fill)

    @property
    def full(self) -> bool:
        return self.fullness >= 0.999

    def fed(self) -> None:
        """The meal's over."""
        self.hungry = False


def hunger_chance(cfg: Config, fullness: float) -> float:
    """Odds he gets hungry at a check: none above ``peckish_below``, then rising
    ever faster as he empties, up to certain when he's empty."""
    if fullness >= cfg.peckish_below:
        return 0.0
    return min(1.0, ((cfg.peckish_below - fullness) / cfg.peckish_below) ** 2)
