"""Zengo's behaviours, one class per state.

A state plays a clip on entry, then each tick may move the body and returns the
next state, or ``None`` to stay. States are short-lived objects: per-visit data
(timers, targets) lives on the instance, so re-entering a state starts fresh.

Input-driven transitions (click, drag, drop) are owned by
:class:`zengo.behavior.machine.Brain`, not by the states themselves.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import ClassVar

from zengo.behavior.context import Context
from zengo.behavior.flight import FlightPath, Point, ease


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
    options: list[tuple[Callable[[Context], State], float]] = [
        (lambda _: Idle(), 1.0),
        (lambda _: Walk(), 4.0),
        (lambda _: Preen(), 2.0),
        (Fly.hop, 0.6),
        (Fly.tour, 0.8),
        (lambda _: Follow(), 1.5 if _cursor_on_same_screen(ctx) else 0.0),
        (Fly.to_cursor, 3.0 if cursor_is_inviting(ctx) else 0.0),
    ]
    makers, weights = zip(*options, strict=True)
    return ctx.rng.choices(makers, weights)[0](ctx)


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


class Fly(State):
    """Fly a curved path through ``waypoints`` and land on the last one.

    Flights come from the planners: :meth:`hop` to another spot on the ground,
    :meth:`tour` around the screen, :meth:`to_cursor` to perch on a resting
    mouse pointer, and :meth:`down` back to the ground from a perch. A bare
    ``Fly()`` is a hop.

    The wings follow the path: flapping while climbing or flying level, held out
    in a glide on the way down, and flared for the last moment before touchdown.
    """

    clip = "fly"
    grounded = False

    glide_above: ClassVar[float] = 0.3
    flap_below: ClassVar[float] = 0.05
    """Descent (sine of the angle below level) at which he starts gliding, and
    below which he flaps again. The gap stops the wings flickering between the two."""
    flare_seconds: ClassVar[float] = 0.45

    def __init__(self, waypoints: Sequence[Point] | None = None, *, onto: str = "ground") -> None:
        super().__init__()
        self.waypoints = None if waypoints is None else tuple(waypoints)
        self.onto = onto
        """What he lands on: ``"ground"`` or ``"cursor"``."""

    # --- Planners -----------------------------------------------------------

    @classmethod
    def hop(cls, ctx: Context) -> Fly:
        """Climb steeply, then come in on a long shallow glide to another spot."""
        area, cfg, (x0, g) = ctx.area(), ctx.config, (ctx.body.x, ctx.area().bottom)
        lo, hi = area.left + ctx.margin, area.right - ctx.margin
        x1 = ctx.rng.uniform(lo, hi)
        if abs(x1 - x0) < cfg.px(60):  # too short to be worth flying
            x1 = hi if x0 - lo < hi - x0 else lo
        d, run = math.copysign(1.0, x1 - x0), abs(x1 - x0)
        height = min(cfg.px(70), 0.35 * run) + cfg.px(12)
        return cls(
            [(x0 + d * 0.35 * run, g - height), (x0 + d * 0.7 * run, g - 0.25 * height), (x1, g)]
        )

    @classmethod
    def tour(cls, ctx: Context) -> Fly:
        """Loop through two to four random points across the screen, then land."""
        area, cfg, rng = ctx.area(), ctx.config, ctx.rng
        lo, hi = area.left + ctx.margin, area.right - ctx.margin
        height = area.bottom - area.top
        y_lo, y_hi = area.top + max(0.12 * height, cfg.px(50)), area.bottom - 0.3 * height
        points, last_x = [], ctx.body.x
        for _ in range(rng.randint(2, 4)):
            x = rng.uniform(lo, hi)
            for _retry in range(8):  # keep each leg long enough to read as travel
                if abs(x - last_x) >= cfg.px(80):
                    break
                x = rng.uniform(lo, hi)
            points.append((x, rng.uniform(y_lo, max(y_lo, y_hi))))
            last_x = x
        landing = _landing(ctx, rng.uniform(lo, hi), coming_from=points[-1][0])
        return cls([*_takeoff(ctx, towards=points[0][0]), *points, *landing])

    @classmethod
    def to_cursor(cls, ctx: Context) -> Fly:
        """Fly up and land on the tip of the resting mouse pointer."""
        cfg, (cx, cy) = ctx.config, ctx.world.cursor()
        d = math.copysign(1.0, cx - ctx.body.x) if cx != ctx.body.x else float(ctx.body.facing)
        approach = (cx - d * min(cfg.px(45), abs(cx - ctx.body.x) / 2), cy - cfg.px(16))
        return cls([*_takeoff(ctx, towards=cx), approach, (cx, cy)], onto="cursor")

    @classmethod
    def down(cls, ctx: Context) -> Fly:
        """Glide down from a perch to the ground a little way ahead."""
        cfg = ctx.config
        x1 = ctx.body.x + int(ctx.body.facing) * ctx.rng.uniform(cfg.px(60), cfg.px(150))
        x1 = ctx.area().clamp_x(x1, ctx.margin)
        return cls(_landing(ctx, x1, coming_from=ctx.body.x))

    # --- Flying -------------------------------------------------------------

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        cfg, area = ctx.config, ctx.area()
        if self.waypoints is None:
            self.waypoints = Fly.hop(ctx).waypoints
        assert self.waypoints is not None
        top = area.top + cfg.px(34)  # room for the raised wing above him
        self.path = FlightPath.through(
            [(ctx.body.x, ctx.body.y), *self.waypoints], top=top, bottom=area.bottom
        )
        self.duration = max(1.0, self.path.length / cfg.px(cfg.fly_speed))
        self.gliding = False

    def step(self, ctx: Context, dt: float) -> State | None:
        cfg, body = ctx.config, ctx.body
        assert self.waypoints is not None
        landing_spot = self.waypoints[-1]
        p = min(self.elapsed / self.duration, 1.0)
        s = self.path.length * ease(p)
        body.x, body.y = self.path.at(s)
        dx, dy = self.path.heading(s, cfg.px(12))
        if abs(dx) > 0.5:
            body.face_towards(body.x + dx)

        if self.onto == "cursor" and math.dist(ctx.world.cursor(), landing_spot) > cfg.px(12):
            # The perch moved away: carry on with the speed he has and glide down.
            speed, norm = self.path.length / self.duration, math.hypot(dx, dy) or 1.0
            body.vx, body.vy = dx / norm * speed, dy / norm * speed
            return Glide.from_fall(ctx)
        if p >= 1.0:
            body.x, body.y = landing_spot
            return CursorPerch() if self.onto == "cursor" else Idle()

        descent = dy / (math.hypot(dx, dy) or 1.0)
        if self.gliding and descent < self.flap_below:
            self.gliding = False
        elif not self.gliding and descent > self.glide_above:
            self.gliding = True
        if p >= 1.0 - self.flare_seconds / self.duration:
            ctx.animator.play("flare")
        else:
            ctx.animator.play("glide" if self.gliding else "fly")
        return None


def _takeoff(ctx: Context, towards: float) -> list[Point]:
    """From the ground, lift off at an angle rather than straight up."""
    if ctx.body.y < ctx.area().bottom - 1:
        return []  # already airborne or on a perch
    cfg = ctx.config
    d = math.copysign(1.0, towards - ctx.body.x) if towards != ctx.body.x else int(ctx.body.facing)
    x = ctx.area().clamp_x(ctx.body.x + d * cfg.px(35), ctx.margin)
    return [(x, ctx.body.y - cfg.px(22))]


def _landing(ctx: Context, x: float, coming_from: float) -> list[Point]:
    """Come in low and shallow from the side, then touch down at ``x`` on the ground."""
    cfg, area = ctx.config, ctx.area()
    d = math.copysign(1.0, x - coming_from) if x != coming_from else int(ctx.body.facing)
    approach = area.clamp_x(x - d * cfg.px(60), ctx.margin)
    return [(approach, area.bottom - cfg.px(20)), (x, area.bottom)]


def cursor_is_inviting(ctx: Context) -> bool:
    """The pointer has been resting a while above the ground, within reach on his screen."""
    cfg, area = ctx.config, ctx.area()
    cx, cy = ctx.world.cursor()
    rest_from, rest_until = cfg.cursor_rest
    return (
        rest_from <= ctx.world.user_idle_seconds() <= rest_until
        and ctx.world.area_at(cx, cy) == area
        and area.left + ctx.margin <= cx <= area.right - ctx.margin
        and area.top + cfg.px(60) <= cy <= area.bottom - cfg.px(40)
        and abs(cx - ctx.body.x) <= cfg.px(cfg.cursor_reach)
    )


class CursorPerch(State):
    """Sitting on the tip of the resting mouse pointer.

    Moving the mouse startles him off (a hop up, then he flutters and glides
    down). Left alone, he flies back down to the ground after a while.
    """

    clip = "idle"
    grounded = False
    stay: ClassVar[tuple[float, float]] = (6.0, 20.0)
    startle_hop: ClassVar[float] = 60.0
    """Art px/s upwards when the pointer moves out from under him."""

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        self.spot = ctx.world.cursor()
        self.duration = ctx.rng.uniform(*self.stay)
        ctx.body.x, ctx.body.y = self.spot

    def step(self, ctx: Context, dt: float) -> State | None:
        if math.dist(ctx.world.cursor(), self.spot) > ctx.config.px(3):
            ctx.body.vx, ctx.body.vy = 0.0, -ctx.config.px(self.startle_hop)
            return Fall()
        if self.elapsed >= self.duration:
            return Fly.down(ctx)
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


class Shake(_OneShot):
    """A feather ruffle to settle down after landing from a drop or a throw."""

    clip = "shake"


class Dragged(State):
    """Held by the mouse, hanging from the grab point on a damped spring.

    ``target`` is where the grab point wants the body to be; the brain moves it as
    the mouse moves. The spring and gravity make Zengo lag behind, sag a little
    and swing, so he feels like he has weight. Moved fast, he flaps in protest.
    Held still, the grab point drifts gently side to side so he sways a little
    while the held clip plays his fidgets.
    """

    clip = "held"
    grounded = False
    protest_hold: ClassVar[float] = 0.4
    """Seconds he keeps flapping after the movement that set him off."""
    sway: ClassVar[tuple[float, float]] = (1.5, 2.4)
    """Art pixels and seconds: how far and how slowly he sways while hanging."""

    def __init__(self, target: tuple[float, float]) -> None:
        super().__init__()
        self.target = target
        self.protesting = 0.0

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        ctx.body.vx = ctx.body.vy = 0.0

    def step(self, ctx: Context, dt: float) -> State | None:
        cfg, body = ctx.config, ctx.body
        (tx, ty), k, c = self.target, cfg.drag_stiffness, cfg.drag_damping
        reach, period = self.sway
        tx += cfg.px(reach) * math.sin(2 * math.pi * self.elapsed / period)
        body.vx += (k * (tx - body.x) - c * body.vx) * dt
        body.vy += (k * (ty - body.y) - c * body.vy + cfg.px(cfg.gravity)) * dt
        body.x += body.vx * dt
        body.y += body.vy * dt
        if abs(body.vx) > cfg.px(10):
            body.face_towards(body.x + body.vx)

        if math.hypot(body.vx, body.vy) > cfg.px(cfg.struggle_speed):
            self.protesting = self.protest_hold
        else:
            self.protesting = max(0.0, self.protesting - dt)
        ctx.animator.play("flutter" if self.protesting else "held")
        return None


class Fall(State):
    """Let go: carried by whatever speed the drag gave him, flapping, then he
    catches the air and glides in. Dropped close to the ground, he just flutters down.
    """

    clip = "flutter"
    grounded = False
    recover_after: ClassVar[tuple[float, float]] = (0.25, 1.0)
    """Flaps at least this long, and once falling, at most this long, before gliding."""
    low_drop: ClassVar[float] = 25.0
    """Art pixels above the ground below which there's no room to glide."""

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        body, limit = ctx.body, ctx.config.px(ctx.config.max_throw_speed)
        speed = math.hypot(body.vx, body.vy)
        if speed > limit:
            body.vx, body.vy = body.vx * limit / speed, body.vy * limit / speed

    def step(self, ctx: Context, dt: float) -> State | None:
        cfg, body, area = ctx.config, ctx.body, ctx.area()
        body.vx *= math.exp(-cfg.air_drag * dt)
        body.vy = min(body.vy + cfg.px(cfg.gravity) * dt, cfg.px(cfg.max_fall_speed))
        body.x += body.vx * dt
        body.y += body.vy * dt

        lo, hi = area.left + ctx.margin, area.right - ctx.margin
        if not lo <= body.x <= hi:  # bounce softly off the screen's sides
            body.x = min(max(body.x, lo), hi)
            body.vx *= -0.4
        if body.y < area.top + cfg.px(30):
            body.y, body.vy = area.top + cfg.px(30), max(body.vy, 0.0)

        if body.y >= area.bottom:
            body.y, body.vx, body.vy = area.bottom, 0.0, 0.0
            return Shake()
        if area.bottom - body.y < cfg.px(self.low_drop):
            return None
        earliest, latest = self.recover_after
        if self.elapsed >= latest or (self.elapsed >= earliest and body.vy >= 0):
            return Glide.from_fall(ctx)
        return None


class Glide(State):
    """Glide down from mid-air to land at ``target`` (screen x) on the ground.

    The descent is steep at first and flattens out, so he comes in shallow, and
    the wings flare for the last stretch.
    """

    clip = "glide"
    grounded = False
    flare_from: ClassVar[float] = 0.85
    min_duration: ClassVar[float] = 0.6

    def __init__(self, target: float) -> None:
        super().__init__()
        self.target = target

    @classmethod
    def from_fall(cls, ctx: Context) -> Glide:
        """Glide onwards in the direction he was moving, far enough to look like a
        glide rather than a drop; turn back if the screen edge is in the way."""
        body, area = ctx.body, ctx.area()
        height = area.bottom - body.y
        direction = 1 if body.vx > 0 else -1 if body.vx < 0 else int(body.facing)
        run = max(abs(body.vx) * 0.8, 0.8 * height)
        target = area.clamp_x(body.x + direction * run, ctx.margin)
        if abs(target - body.x) < run / 2:
            target = area.clamp_x(body.x - direction * run, ctx.margin)
        return cls(target)

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        cfg, body = ctx.config, ctx.body
        self.start = (body.x, body.y)
        self.end = (self.target, ctx.area().bottom)
        distance = math.dist(self.start, self.end)
        self.duration = max(self.min_duration, distance / cfg.px(cfg.glide_speed))
        body.vx = body.vy = 0.0
        body.face_towards(self.target)

    def step(self, ctx: Context, dt: float) -> State | None:
        p = min(self.elapsed / self.duration, 1.0)
        (x0, y0), (x1, y1) = self.start, self.end
        ctx.body.x = x0 + (x1 - x0) * p
        ctx.body.y = y0 + (y1 - y0) * math.sin(math.pi / 2 * p)
        if p >= 1.0:
            ctx.body.y = y1
            return Shake()
        ctx.animator.play("glide" if p < self.flare_from else "flare")
        return None
