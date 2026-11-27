"""The cage Zengo can be caught in, and where it ends up.

The cage is moved by dragging it. Let go near the top of the screen and it
hangs from a chain, swinging a little before it settles; near a side edge and
it sits on a shelf fixed to that edge; anywhere else it falls to the ground.
Zengo sits inside on the tray, so wherever the cage goes, he goes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from zengo.behavior.food import Pile
from zengo.sprites.cage import CAGE_HEIGHT, CAGE_WIDTH, FLOOR, SHELF_WIDTH

if TYPE_CHECKING:
    from zengo.behavior.context import Context
    from zengo.config import Config
    from zengo.world import Area

BELOW_FLOOR = CAGE_HEIGHT - FLOOR
"""Art rows from the tray's top surface down to the bottom of the cage."""


@dataclass
class Cage:
    x: float
    """Screen x of the cage's centre line, where Zengo's anchor is."""
    y: float
    """Screen y of the tray's top surface, where his feet rest."""
    mount: str = "falling"
    """``"ground"``, ``"chain"``, ``"shelf"``, ``"held"`` (being dragged) or ``"falling"``."""
    side: int = 0
    """For a shelf: -1 on the left edge of the screen, +1 on the right."""
    vx: float = 0.0
    vy: float = 0.0
    sway: float = 0.0
    """Hanging: how far the cage has swung sideways from under the chain's top."""
    sway_speed: float = 0.0
    pivot: tuple[float, float] | None = None
    """Hanging: where the chain is fixed, on the top edge of the screen."""
    door_open: bool = False
    left: bool = False
    """He has flown out through the open door."""
    escaped: bool = False
    """He opened the door himself."""
    dish: Pile = field(default_factory=Pile)
    """Seeds on the tray."""
    caged_for: float = 0.0
    feedings: int = 0
    """Times he's been fed in here: each makes him less keen to escape."""
    _next_try: float | None = None
    empty_for: float = 0.0
    """Seconds since he left through the open door; the cage goes soon after."""
    events: list[str] = field(default_factory=list)
    """What happened to the cage since he last looked: ``"bump"``, ``"hung"``, ``"shelved"``."""
    _grab: tuple[float, float] = (0.0, 0.0)
    _last_held: tuple[float, float] | None = None

    @property
    def shown_x(self) -> float:
        """Where the cage is drawn, swing included."""
        return self.x + self.sway

    def top(self, ctx: Context) -> float:
        """Screen y of the top of the hook."""
        return self.y - ctx.config.px(FLOOR)

    def take_events(self) -> list[str]:
        events, self.events = self.events, []
        return events

    # --- Dragging ------------------------------------------------------------

    def grab(self, x: float, y: float) -> None:
        self._grab = (self.x - x, self.y - y)
        self.mount, self.sway, self.sway_speed, self.pivot = "held", 0.0, 0.0, None
        self.vx = self.vy = 0.0
        self._last_held = None

    def drag(self, x: float, y: float, ctx: Context) -> None:
        """Follow the mouse, but stay whole on the screen: it stops at the edges
        rather than sliding off them."""
        if self.mount != "held":
            return
        dx, dy = self._grab
        x, y = x + dx, y + dy
        cfg = ctx.config
        area = ctx.world.area_at(x, y - cfg.px(FLOOR / 2))
        half = cfg.px(CAGE_WIDTH / 2)
        self.x = min(max(x, area.left + half), area.right - half)
        self.y = min(max(y, area.top + cfg.px(FLOOR)), area.bottom - cfg.px(BELOW_FLOOR))

    def release(self, ctx: Context) -> None:
        """Let go: hang it from the top, stand it on a side shelf, or let it fall."""
        if self.mount != "held":
            return
        cfg, area = ctx.config, self._area(ctx)
        half = cfg.px(CAGE_WIDTH / 2)
        self.x = min(max(self.x, area.left + half), area.right - half)
        if self.top(ctx) - area.top <= cfg.px(cfg.cage_hang_reach):
            self._hang(ctx, area)
        elif self.x - half - area.left <= cfg.px(cfg.cage_shelf_reach):
            self._shelve(ctx, area, side=-1)
        elif area.right - (self.x + half) <= cfg.px(cfg.cage_shelf_reach):
            self._shelve(ctx, area, side=1)
        else:
            self.mount = "falling"
            self.vy = max(self.vy, 0.0)

    def _hang(self, ctx: Context, area: Area) -> None:
        cfg = ctx.config
        self.mount, self.pivot = "chain", (self.x, area.top)
        self.y = max(self.y, area.top + cfg.px(cfg.cage_min_chain + FLOOR))
        # Swing off with some of the speed it was let go at.
        limit = cfg.px(80)
        self.sway, self.sway_speed = 0.0, min(max(self.vx * 0.5, -limit), limit) or cfg.px(25)
        self.events.append("hung")

    def _shelve(self, ctx: Context, area: Area, side: int) -> None:
        cfg = ctx.config
        self.mount, self.side = "shelf", side
        inset = cfg.px(SHELF_WIDTH / 2 + 1)
        self.x = area.left + inset if side < 0 else area.right - inset
        self.events.append("shelved")

    # --- Each tick ---------------------------------------------------------------

    def update(self, ctx: Context, dt: float) -> None:
        cfg = ctx.config
        if self.mount == "held":
            if self._last_held is not None and dt > 0:
                self.vx = (self.x - self._last_held[0]) / dt
                self.vy = (self.y - self._last_held[1]) / dt
            self._last_held = (self.x, self.y)
        elif self.mount == "falling":
            self.vy = min(self.vy + cfg.px(cfg.gravity) * dt, cfg.px(400))
            self.y += self.vy * dt
            ground = self._area(ctx).bottom - cfg.px(BELOW_FLOOR)
            if self.y >= ground:
                self.y, self.vy, self.mount = ground, 0.0, "ground"
                self.events.append("bump")
        elif self.mount == "chain":
            # A damped pendulum, small enough to treat as a sideways spring.
            k, c = cfg.cage_swing_stiffness, cfg.cage_swing_damping
            self.sway_speed += (-k * self.sway - c * self.sway_speed) * dt
            self.sway += self.sway_speed * dt
        elif self.mount == "ground":
            self.y = self._area(ctx).bottom - cfg.px(BELOW_FLOOR)  # follows the desktop
        if self.door_open and self.left:
            self.empty_for += dt
        elif not self.door_open:
            self.caged_for += dt
        self.dish.update(dt)

    # --- Escaping ------------------------------------------------------------

    def tries_to_escape(self, ctx: Context) -> bool:
        """Called while he's free to try (awake, not being carried): is this the
        moment he gets the door open? He tries once a minute after five, with the
        odds of :func:`escape_chance`."""
        cfg = ctx.config
        if self._next_try is None:
            self._next_try = cfg.escape_after
        if self.caged_for < self._next_try:
            return False
        self._next_try = self.caged_for + cfg.escape_every
        return ctx.rng.random() < escape_chance(cfg, self.caged_for, self.feedings)

    def _area(self, ctx: Context) -> Area:
        return ctx.world.area_at(self.x, self.y - ctx.config.px(4))


def escape_chance(cfg: Config, caged_for: float, feedings: int) -> float:
    """Odds he gets out at a try: ``escape_chance`` at the first, rising by
    ``escape_chance_rise`` with every try after, less ``escape_feed_penalty`` for each
    time he's been fed in the cage."""
    if caged_for < cfg.escape_after:
        return 0.0
    tries_before = int((caged_for - cfg.escape_after) // cfg.escape_every)
    chance = (
        cfg.escape_chance
        + tries_before * cfg.escape_chance_rise
        - feedings * cfg.escape_feed_penalty
    )
    return min(max(chance, 0.0), 1.0)


def caught_in(ctx: Context, left: float, top: float, right: float, bottom: float) -> bool:
    """Does a box drawn on screen take in Zengo? It must include the middle of him."""
    x, y = ctx.body.x, ctx.body.y - ctx.config.px(12)
    return min(left, right) <= x <= max(left, right) and min(top, bottom) <= y <= max(top, bottom)
