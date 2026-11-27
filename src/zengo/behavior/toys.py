"""His toys: a bell and a mirror, put out (or away) from his settings.

- **The bell** hangs from the branch, near its tip, while the branch is out, or
  from the roof of his cage while he's in it. He pecks it: it swings and rings.
- **The mirror** stands on the ground, a little way from where he was when you
  put it out, or hangs on the bars inside his cage while he's in it. He goes
  and chats to his reflection: bobbing, whistling, crest up.

Playing counts as activity (he gets hungrier), and since you gave him the
toys, it brings him a little closer to you; at most so much an hour, so
putting a toy out and away again gains nothing.

Pure Python: no Qt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from zengo.sprites.branch import TOP_ROW
from zengo.sprites.cage import FLOOR
from zengo.sprites.toys import BELL_HANG_COLUMN, BRANCH_UNDERSIDE, CAGE_BELL, CAGE_MIRROR

if TYPE_CHECKING:
    from zengo.behavior.context import Context

TOYS: dict[str, str] = {"bell": "a bell to ring", "mirror": "a mirror to chat to"}

SWING_STIFFNESS = 30.0
SWING_DAMPING = 1.6
"""How the bell swings once struck (1/s², 1/s): a few quick swings, then still."""
STRIKE = 1.6
"""Swing speed (radians a second) a peck gives it."""


@dataclass
class Bell:
    x: float = 0.0
    y: float = 0.0
    """Screen position it hangs from."""
    where: str = "branch"
    """``"branch"`` or ``"cage"``."""
    angle: float = 0.0
    speed: float = 0.0

    def strike(self, direction: int) -> None:
        """Pecked from one side: it swings away from the beak."""
        self.speed += direction * STRIKE

    def update(self, dt: float) -> None:
        self.speed += (-SWING_STIFFNESS * self.angle - SWING_DAMPING * self.speed) * dt
        self.angle += self.speed * dt

    @property
    def swing(self) -> int:
        """Which picture to show: swung left (-1), hanging (0) or swung right (1)."""
        return -1 if self.angle < -0.12 else 1 if self.angle > 0.12 else 0


@dataclass
class Mirror:
    x: float = 0.0
    y: float = 0.0
    """Screen position of its middle, at the bottom (its foot, or its hook's end)."""
    where: str = "ground"
    """``"ground"`` (standing) or ``"cage"`` (hanging on the bars)."""
    reflecting: bool = False
    """He's in front of it: his reflection shows."""


@dataclass
class Toys:
    out: frozenset[str] = frozenset()
    """The toys you've put out: names from :data:`TOYS`."""
    bell: Bell | None = None
    """Where the bell is now, if it's out and has somewhere to hang."""
    mirror: Mirror | None = None
    _ground_x: float | None = None
    """Where the mirror stands on the ground, once put there."""
    _swing: Bell = field(default_factory=Bell)
    rest: float = 0.0
    """Seconds before he'll play again."""

    def ready(self) -> bool:
        return self.rest <= 0

    def played(self, ctx: Context) -> None:
        """A game's over: he's had his fun (and grown a little fonder of you)."""
        self.rest = ctx.rng.uniform(*ctx.config.toy_every)
        ctx.bond.played(ctx.config)

    def put_out(self, out: frozenset[str]) -> None:
        if "mirror" not in out:
            self._ground_x = None  # put back out, it goes near him again
        self.out = out

    def update(
        self, ctx: Context, dt: float, *, caged: bool, away: bool, at_mirror: bool = False
    ) -> None:
        """Hang and stand the toys where they go now, and swing the bell.
        ``at_mirror``: he's in front of the mirror, so his reflection shows."""
        cfg, cage, branch = ctx.config, ctx.cage, ctx.scenery.branch
        in_cage = caged and cage is not None
        self.rest = max(0.0, self.rest - dt)
        self._swing.update(dt)
        self.bell = None
        if "bell" in self.out:
            if in_cage:
                assert cage is not None
                self._swing.x = cage.shown_x + cfg.px(CAGE_BELL[0])
                self._swing.y = cage.y - cfg.px(FLOOR - CAGE_BELL[1])
                self._swing.where = "cage"
                self.bell = self._swing
            elif branch is not None and branch.ready and not away:
                self._swing.x = branch.x_at(BELL_HANG_COLUMN, cfg)
                self._swing.y = branch.top + cfg.px(BRANCH_UNDERSIDE - TOP_ROW)
                self._swing.where = "branch"
                self.bell = self._swing
        reflecting = at_mirror
        self.mirror = None
        if "mirror" in self.out:
            if in_cage:
                assert cage is not None
                self.mirror = Mirror(
                    cage.shown_x + cfg.px(CAGE_MIRROR[0]),
                    cage.y - cfg.px(FLOOR - CAGE_MIRROR[1]),
                    "cage",
                    reflecting,
                )
            elif not away:
                area = ctx.area()
                if self._ground_x is None:
                    self._ground_x = self._spot(ctx)
                self._ground_x = area.clamp_x(self._ground_x, ctx.margin)
                self.mirror = Mirror(self._ground_x, area.bottom, "ground", reflecting)

    def _spot(self, ctx: Context) -> float:
        """A little way from him, on the side with more room."""
        area, body, cfg = ctx.area(), ctx.body, ctx.config
        side = 1 if area.right - body.x > body.x - area.left else -1
        return body.x + side * cfg.px(ctx.rng.uniform(60, 100))
