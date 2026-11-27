"""Things in Zengo's surroundings that come and go: for now, the branch.

Every so often a branch grows out from the left or right edge of the screen
he's on. It stays a few minutes, never retracts while he's sitting on it or
flying to it, lingers a little after he leaves, then withdraws. All of this is
plain timing; the Qt side only draws where the branch is and how far it is out.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from zengo.sprites.branch import BRANCH_WIDTH, PERCH

if TYPE_CHECKING:
    from zengo.behavior.context import Context
    from zengo.config import Config


@dataclass
class Branch:
    side: int
    """-1 when it grows from the left edge of the screen, +1 from the right."""
    edge: float
    """Screen x of that edge."""
    top: float
    """Screen y of its upper surface along the perch, where his feet rest."""
    shown: float = 0.0
    """How far it has grown out, 0 to 1."""

    @property
    def ready(self) -> bool:
        """Fully out, so he can land on it."""
        return self.shown >= 1.0

    @property
    def inward(self) -> int:
        """Direction from the edge into the screen: the way the branch points."""
        return -self.side

    def x_at(self, column: float, config: Config) -> float:
        """Screen x of an art column counted from the screen edge."""
        return self.edge + self.inward * config.px(column)

    def perch_span(self, config: Config) -> tuple[float, float]:
        """Screen x range he can sit in."""
        a, b = (self.x_at(column, config) for column in PERCH)
        return min(a, b), max(a, b)

    def length(self, config: Config) -> float:
        return config.px(BRANCH_WIDTH)


class Scenery:
    """The branch's life cycle: waiting, growing, out, retracting, then waiting again."""

    def __init__(self) -> None:
        self.branch: Branch | None = None
        self.phase = "waiting"
        self._timer: float | None = None

    def update(self, ctx: Context, dt: float, *, occupied: bool) -> None:
        """Advance the branch by ``dt``. ``occupied``: Zengo is on it or flying to it."""
        cfg = ctx.config
        if self._timer is None:
            self._timer = ctx.rng.uniform(*cfg.branch_every)

        if self.phase == "waiting":
            self._timer -= dt
            if self._timer <= 0:
                self.grow(ctx)
        elif self.phase == "growing":
            assert self.branch is not None
            self.branch.shown = min(1.0, self.branch.shown + dt / cfg.branch_grow_seconds)
            if self.branch.ready:
                self.phase, self._timer = "out", ctx.rng.uniform(*cfg.branch_stays)
        elif self.phase == "out":
            if occupied:
                self._timer = max(self._timer, ctx.rng.uniform(*cfg.branch_linger))
            else:
                self._timer -= dt
                if self._timer <= 0:
                    self.phase = "retracting"
        elif self.phase == "retracting":
            assert self.branch is not None
            if occupied:  # he got there just in time: let it grow back out
                self.phase = "growing"
                return
            self.branch.shown -= dt / cfg.branch_grow_seconds
            if self.branch.shown <= 0:
                self.branch, self.phase = None, "waiting"
                self._timer = ctx.rng.uniform(*cfg.branch_every)

    def grow(self, ctx: Context) -> Branch:
        """Start a branch growing out now, on a random edge of Zengo's screen."""
        cfg, area = ctx.config, ctx.area()
        side = ctx.rng.choice((-1, 1))
        edge = area.left if side < 0 else area.right
        low, high = cfg.branch_height
        top = area.top + ctx.rng.uniform(low, high) * (area.bottom - area.top)
        self.branch = Branch(side=side, edge=edge, top=top)
        self.phase = "growing"
        return self.branch
