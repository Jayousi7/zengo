"""His bath: a shallow dish of water that turns up on the ground now and then.

Every so often (more often in summer) a dish appears near him, fading in. It
stays a few minutes, never going while he's in it or on his way, then fades
away. Like the branch it doesn't come while he's caged or away: one that falls
due then appears once he's back out. The bathing itself is in the states.

Pure Python: no Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from zengo.sprites.bath import DISH_WIDTH

if TYPE_CHECKING:
    from zengo.behavior.context import Context

SUMMER_SOONER = 0.6
"""In summer the wait between baths is this much as long."""


@dataclass
class Dish:
    x: float
    """Screen x of its middle."""
    y: float
    """Screen y of the ground it stands on."""
    shown: float = 0.0
    """How far it has faded in, 0 to 1."""
    used: bool = False
    """He's bathed in it: he won't again till the next one."""
    splash: float = 0.0
    """Seconds of splashing left: the water ripples hard meanwhile."""

    @property
    def ready(self) -> bool:
        return self.shown >= 1.0


class BathCycle:
    """Waiting, appearing, out, going, then waiting again."""

    def __init__(self) -> None:
        self.dish: Dish | None = None
        self.phase = "waiting"
        self._timer: float | None = None

    def _wait(self, ctx: Context) -> float:
        wait = ctx.rng.uniform(*ctx.config.bath_every)
        return wait * SUMMER_SOONER if ctx.season() == "summer" else wait

    def update(self, ctx: Context, dt: float, *, occupied: bool, free: bool) -> None:
        """Advance by ``dt``. ``occupied``: he's in the dish or on his way to it;
        ``free``: he's neither caged nor away, so a dish may appear."""
        cfg = ctx.config
        if self._timer is None:
            self._timer = self._wait(ctx)
        dish = self.dish
        if dish is not None:
            dish.splash = max(0.0, dish.splash - dt)
        if self.phase == "waiting":
            self._timer -= dt
            if self._timer <= 0 and free:
                self.fill(ctx)
        elif self.phase == "appearing":
            assert dish is not None
            dish.shown = min(1.0, dish.shown + dt / cfg.bath_fade_seconds)
            if dish.ready:
                self.phase, self._timer = "out", ctx.rng.uniform(*cfg.bath_stays)
        elif self.phase == "out":
            if not occupied:
                self._timer -= dt
                if self._timer <= 0 or not free:
                    self.phase = "going"
        elif self.phase == "going":
            assert dish is not None
            if occupied and free:
                self.phase = "appearing"  # he got there just in time
                return
            dish.shown -= dt / cfg.bath_fade_seconds
            if dish.shown <= 0:
                self.dish, self.phase, self._timer = None, "waiting", self._wait(ctx)

    def fill(self, ctx: Context) -> Dish:
        """Put a dish out now, on the ground a little way from him (away from his
        seeds, if they're down), and on the side with more room."""
        cfg, area, body = ctx.config, ctx.area(), ctx.body
        gap = cfg.px(ctx.rng.uniform(55.0, 90.0))
        room_right = area.right - body.x > body.x - area.left
        side = 1 if room_right else -1
        if ctx.food is not None and (ctx.food.x - body.x) * side > 0:
            side = -side  # not on top of his seeds
        half = cfg.px(DISH_WIDTH / 2) + ctx.margin
        x = min(max(body.x + side * gap, area.left + half), area.right - half)
        self.dish = Dish(x, area.bottom)
        self.phase = "appearing"
        return self.dish

    @property
    def usable(self) -> bool:
        """Out, and not bathed in yet."""
        return self.phase == "out" and self.dish is not None and not self.dish.used
