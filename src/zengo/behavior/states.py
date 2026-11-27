"""Zengo's behaviours, one class per state.

A state plays a clip on entry, then each tick may move the body and returns the
next state, or ``None`` to stay. States are short-lived objects: per-visit data
(timers, targets) lives on the instance, so re-entering a state starts fresh.

Input-driven transitions (click, drag, drop) are owned by
:class:`zengo.behavior.machine.Brain`, not by the states themselves.
"""

from __future__ import annotations

import math
from typing import ClassVar

from zengo.behavior.context import Context


class State:
    clip: ClassVar[str]

    grounded: ClassVar[bool] = True
    """Grounded states are kept on the ground line and inside the screen by the brain."""

    def __init__(self) -> None:
        self.elapsed = 0.0

    def enter(self, ctx: Context) -> None:
        ctx.animator.play(self.clip, restart=True)

    def update(self, ctx: Context, dt: float) -> State | None:
        self.elapsed += dt
        return self.step(ctx, dt)

    def step(self, ctx: Context, dt: float) -> State | None:
        return None

    def __repr__(self) -> str:
        return type(self).__name__


class Idle(State):
    clip = "idle"

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        self.duration = ctx.rng.uniform(*ctx.config.idle_seconds)

    def step(self, ctx: Context, dt: float) -> State | None:
        cx, cy = ctx.world.cursor()
        reach = ctx.config.px(ctx.config.watch_radius)
        if abs(cx - ctx.body.x) < reach and abs(cy - ctx.body.y) < 2 * reach:
            ctx.body.face_towards(cx)
        return choose_activity(ctx) if self.elapsed >= self.duration else None


def is_sleepy(ctx: Context) -> bool:
    cfg = ctx.config
    return ctx.world.user_idle_seconds() >= cfg.sleep_after or cfg.is_night(ctx.world.local_hour())


def choose_activity(ctx: Context) -> State:
    """Weighted pick of what to do after idling."""
    if is_sleepy(ctx) and ctx.rng.random() < 0.6:
        return Sleep()
    options: list[tuple[type[State], float]] = [
        (Idle, 1.0),
        (Walk, 4.0),
        (Preen, 2.0),
        (Fly, 1.0),
        (Follow, 1.5 if _cursor_on_same_screen(ctx) else 0.0),
    ]
    kinds, weights = zip(*options, strict=True)
    return ctx.rng.choices(kinds, weights)[0]()


def _cursor_on_same_screen(ctx: Context) -> bool:
    return ctx.world.area_at(*ctx.world.cursor()) == ctx.area()


class Walk(State):
    """Waddle to ``target`` (screen x), or to a random nearby spot."""

    clip = "walk"

    def __init__(self, target: float | None = None) -> None:
        super().__init__()
        self.target = target

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        if self.target is None:
            distance = ctx.config.px(ctx.rng.uniform(25, 130)) * ctx.rng.choice((-1, 1))
            self.target = ctx.body.x + distance
        self.target = ctx.area().clamp_x(self.target, ctx.margin)
        ctx.body.face_towards(self.target)

    def step(self, ctx: Context, dt: float) -> State | None:
        assert self.target is not None
        return Idle() if _walk_towards(ctx, self.target, dt) else None


class Follow(State):
    """Walk after the cursor's x position for a while."""

    clip = "walk"
    give_up_after: ClassVar[float] = 10.0
    close_enough: ClassVar[float] = 18.0  # art px

    def step(self, ctx: Context, dt: float) -> State | None:
        if self.elapsed >= self.give_up_after or not _cursor_on_same_screen(ctx):
            return Idle()
        target = ctx.area().clamp_x(ctx.world.cursor()[0], ctx.margin)
        if abs(target - ctx.body.x) <= ctx.config.px(self.close_enough):
            ctx.body.face_towards(target)
            return Idle()
        _walk_towards(ctx, target, dt)
        return None


STEPPING_FRAMES = frozenset({"step_back", "step_front"})
"""Walk frames with a foot lifted. Zengo only moves on these, so the body
advances in steps instead of sliding at constant speed over still feet."""


def _walk_towards(ctx: Context, target: float, dt: float) -> bool:
    """Advance one tick towards ``target``. Returns True on arrival.

    Half the walk cycle is spent stepping, so the stepping speed is doubled to
    keep the average at ``walk_speed``.
    """
    ctx.body.face_towards(target)
    remaining = target - ctx.body.x
    if abs(remaining) < 0.5:
        ctx.body.x = target
        return True
    if ctx.animator.frame not in STEPPING_FRAMES:
        return False
    stride = 2 * ctx.config.px(ctx.config.walk_speed) * dt
    ctx.body.x += max(-stride, min(stride, remaining))
    return False


def flight_profile(p: float) -> tuple[float, float]:
    """Horizontal progress and height (both 0..1) at flight fraction ``p``.

    A powered climb peaks a third of the way, then a long glide flattens out so
    the landing comes in shallow rather than dropping straight down. Horizontal
    speed eases only slightly, so takeoff and landing never look vertical.
    """
    progress = 0.6 * p + 0.4 * p * p * (3 - 2 * p)
    peak = 0.35
    if p < peak:
        height = math.sin(math.pi / 2 * p / peak) ** 0.8
    else:
        height = math.cos(math.pi / 2 * (p - peak) / (1 - peak)) ** 1.3
    return progress, height


class Fly(State):
    """Take off, climb, glide in and land somewhere else along the bottom edge.

    The clip follows the phase of the flight: flapping on the climb, wings held
    level on the glide, wings flared for touchdown.
    """

    clip = "fly"
    grounded = False

    glide_from: ClassVar[float] = 0.5
    flare_from: ClassVar[float] = 0.9
    """Fractions of the flight at which gliding and the landing flare begin."""

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        area, cfg = ctx.area(), ctx.config
        self.start = (ctx.body.x, ctx.body.y)
        lo, hi = area.left + ctx.margin, area.right - ctx.margin
        target = ctx.rng.uniform(lo, hi)
        if abs(target - ctx.body.x) < cfg.px(60):  # too short to be worth flying
            target = hi if ctx.body.x - lo < hi - ctx.body.x else lo
        self.end = (target, area.bottom)
        distance = abs(target - ctx.body.x)
        self.duration = max(1.0, distance / cfg.px(cfg.fly_speed))
        self.height = min(cfg.px(70), 0.35 * distance) + cfg.px(12)
        ctx.body.face_towards(target)

    def step(self, ctx: Context, dt: float) -> State | None:
        p = min(self.elapsed / self.duration, 1.0)
        (x0, y0), (x1, y1) = self.start, self.end
        progress, height = flight_profile(p)
        ctx.body.x = x0 + (x1 - x0) * progress
        ctx.body.y = y0 + (y1 - y0) * progress - self.height * height
        if p >= 1.0:
            ctx.body.y = y1
            return Idle()
        phase = "fly" if p < self.glide_from else "glide" if p < self.flare_from else "flare"
        ctx.animator.play(phase)
        return None


class _OneShot(State):
    """Plays a non-looping clip once, then idles."""

    def step(self, ctx: Context, dt: float) -> State | None:
        return Idle() if ctx.animator.finished else None


class Preen(_OneShot):
    clip = "preen"


class Alert(_OneShot):
    """Crest up: Zengo was poked or startled."""

    clip = "alert"


class Sleep(State):
    """Fluffed up and asleep.

    Wakes when the user comes back, unless it is night, when Zengo stays down for
    a proper nap first. A click always wakes Zengo (handled by the brain).
    """

    clip = "sleep"
    nap_seconds: ClassVar[tuple[float, float]] = (120.0, 300.0)

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        self.nap = ctx.rng.uniform(*self.nap_seconds)

    def step(self, ctx: Context, dt: float) -> State | None:
        if ctx.config.is_night(ctx.world.local_hour()):
            return Idle() if self.elapsed >= self.nap else None
        return Idle() if ctx.world.user_idle_seconds() < 1.0 else None


class Dragged(State):
    """Held by the mouse. Position is driven by the brain's drag handler."""

    clip = "flutter"
    grounded = False


class Fall(State):
    """Dropped: flutter down under gravity until reaching the ground."""

    clip = "flutter"
    grounded = False

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        ctx.body.vy = 0.0

    def step(self, ctx: Context, dt: float) -> State | None:
        ground = ctx.area().bottom
        cfg = ctx.config
        ctx.body.vy = min(ctx.body.vy + cfg.px(cfg.gravity) * dt, cfg.px(cfg.max_fall_speed))
        ctx.body.y += ctx.body.vy * dt
        if ctx.body.y < ground:
            return None
        ctx.body.y, ctx.body.vy = ground, 0.0
        return Alert()
