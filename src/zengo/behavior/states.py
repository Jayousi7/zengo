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

from zengo.behavior.body import Facing
from zengo.behavior.context import Context
from zengo.behavior.flight import FlightPath, Point, ease
from zengo.behavior.food import PECK_REACH, SECONDS_PER_SEED
from zengo.behavior.scenery import Branch


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

    def clicked(self, ctx: Context) -> State | None:
        """A poke. It startles him when he's settled on the ground; mid-air or held,
        he doesn't notice."""
        return Alert() if self.grounded else None

    def double_clicked(self, ctx: Context) -> State | None:
        """Double-clicked: on the ground he whistles a tune."""
        return Whistle() if self.grounded else None

    def petted(self, ctx: Context) -> State | None:
        """Being stroked: on the ground he settles into it, even from a nap."""
        return Petted() if self.grounded else None

    def food_nearby(self, ctx: Context) -> State | None:
        """Seeds are down. Settled on the ground, he goes straight for them; held
        or mid-air, he gets to them once he's landed."""
        return go_to_food(ctx) if self.grounded else None

    @property
    def holds_branch(self) -> bool:
        """He's on the branch or on his way to it, so it mustn't withdraw yet."""
        return False

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
        (lambda _: FrontIdle(), 1.2),
        (Fly.to_cursor, 3.0 if cursor_is_inviting(ctx) else 0.0),
        (Fly.to_branch, 6.0 if branch_is_inviting(ctx) else 0.0),  # he loves the branch
    ]
    makers, weights = zip(*options, strict=True)
    return ctx.rng.choices(makers, weights)[0](ctx)


def _cursor_on_same_screen(ctx: Context) -> bool:
    return ctx.world.area_at(*ctx.world.cursor()) == ctx.area()


def branch_is_inviting(ctx: Context) -> bool:
    """A branch is fully out on Zengo's screen and staying a while."""
    branch = ctx.scenery.branch
    if branch is None or not branch.ready or ctx.scenery.phase != "out":
        return False
    lo, hi = branch.perch_span(ctx.config)
    return ctx.world.area_at((lo + hi) / 2, branch.top) == ctx.area()


class FrontIdle(State):
    """Sitting facing you for a while, looking about."""

    clip = "front_idle"
    sit_for: ClassVar[tuple[float, float]] = (4.0, 10.0)

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        self.duration = ctx.rng.uniform(*self.sit_for)

    def step(self, ctx: Context, dt: float) -> State | None:
        return choose_activity(ctx) if self.elapsed >= self.duration else None


class Walk(State):
    """Waddle to ``target`` (screen x), or to a random nearby spot."""

    clip = "walk"

    def __init__(self, target: float | None = None, *, eat: bool = False) -> None:
        super().__init__()
        self.target = target
        self.eat = eat
        """Walking to the seeds: eat them on arrival."""

    def food_nearby(self, ctx: Context) -> State | None:
        return None if self.eat else super().food_nearby(ctx)

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        if self.target is None:
            distance = ctx.config.px(ctx.rng.uniform(25, 130)) * ctx.rng.choice((-1, 1))
            self.target = ctx.body.x + distance
        self.target = ctx.area().clamp_x(self.target, ctx.margin)
        ctx.body.face_towards(self.target)

    def step(self, ctx: Context, dt: float) -> State | None:
        assert self.target is not None
        if not _walk_towards(ctx, self.target, dt):
            return None
        return Eat() if self.eat and ctx.food is not None else Idle()


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

    The wings follow the path the way a cockatiel's do. He's a strong, fast
    flapper: he flaps whenever climbing or flying level, and on the way down he
    only coasts in short glides between bursts of wingbeats. Coming in to land,
    he holds one steady glide, then flares his wings for touchdown.
    """

    clip = "fly"
    grounded = False

    glide_above: ClassVar[float] = 0.3
    flap_below: ClassVar[float] = 0.05
    """Descent (sine of the angle below level) steep enough for a glide, and
    shallow enough that he flaps again."""
    glide_bout: ClassVar[float] = 0.7
    flaps_between: ClassVar[float] = 0.4
    """Longest single glide on the way down, and the wingbeats before the next."""
    approach_seconds: ClassVar[float] = 1.0
    """The final glide in, before the flare."""
    flare_seconds: ClassVar[float] = 0.45
    turn_seconds: ClassVar[float] = 0.24
    """How long he shows his front, wings spread, when banking round to fly the other way."""
    turn_heading: ClassVar[float] = 0.2
    """How firmly the path must head the other way (share of the motion that is
    sideways) before he turns, so a near-vertical stretch doesn't set off a turn."""

    def __init__(self, waypoints: Sequence[Point] | None = None, *, onto: str = "ground") -> None:
        super().__init__()
        self.waypoints = None if waypoints is None else tuple(waypoints)
        self.onto = onto
        """What he lands on: ``"ground"``, ``"cursor"`` or ``"branch"``."""

    @property
    def holds_branch(self) -> bool:
        return self.onto == "branch"

    def food_nearby(self, ctx: Context) -> State | None:
        return None  # lands first; flying to the seeds already, or will after

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
    def to_branch(cls, ctx: Context) -> Fly:
        """Fly to the branch, coming in from the open side and landing on the perch."""
        cfg, branch = ctx.config, ctx.scenery.branch
        assert branch is not None
        lo, hi = branch.perch_span(cfg)
        x = ctx.rng.uniform(lo, hi)
        approach_x = ctx.area().clamp_x(x + branch.inward * cfg.px(55), ctx.margin)
        approach = (approach_x, branch.top - cfg.px(18))
        return cls([*_takeoff(ctx, towards=approach_x), approach, (x, branch.top)], onto="branch")

    @classmethod
    def down(cls, ctx: Context) -> Fly:
        """Hop off a perch and glide down to the ground a little way ahead."""
        cfg, body = ctx.config, ctx.body
        d = int(body.facing)
        x1 = ctx.area().clamp_x(body.x + d * ctx.rng.uniform(cfg.px(60), cfg.px(150)), ctx.margin)
        hop = [(body.x + d * cfg.px(20), body.y - cfg.px(10))]
        return cls([*hop, *_landing(ctx, x1, coming_from=body.x)])

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
        self.in_mode = 0.0
        """Seconds spent gliding, or flapping, since he last switched."""
        self.turning = 0.0
        dx, _ = self.path.heading(0.0, cfg.px(12))
        if dx:  # still on the ground or the perch: just turn to face the way out
            ctx.body.face_towards(ctx.body.x + dx)

    def step(self, ctx: Context, dt: float) -> State | None:
        cfg, body = ctx.config, ctx.body
        assert self.waypoints is not None
        landing_spot = self.waypoints[-1]
        p = min(self.elapsed / self.duration, 1.0)
        s = self.path.length * ease(p)
        body.x, body.y = self.path.at(s)
        dx, dy = self.path.heading(s, cfg.px(12))

        # Turning round in the air: bank, showing his front for a moment, rather
        # than flipping from one side view to the other.
        self.turning = max(0.0, self.turning - dt)
        if abs(dx) > self.turn_heading * (math.hypot(dx, dy) or 1.0):
            want = Facing.RIGHT if dx > 0 else Facing.LEFT
            if want is not body.facing and not self.turning:
                self.turning = self.turn_seconds
                body.facing = want

        if self._perch_is_gone(ctx, landing_spot):
            # The perch moved away: carry on with the speed he has and glide down.
            speed, norm = self.path.length / self.duration, math.hypot(dx, dy) or 1.0
            body.vx, body.vy = dx / norm * speed, dy / norm * speed
            return Glide.from_fall(ctx)
        if p >= 1.0:
            body.x, body.y = landing_spot
            if self.onto == "cursor":
                return CursorPerch()
            if self.onto == "food":
                return Eat() if ctx.food is not None else Idle()
            return OnBranch() if self.onto == "branch" else Idle()

        self._choose_glide(dx, dy, seconds_left=(1.0 - p) * self.duration, dt=dt)
        if p >= 1.0 - self.flare_seconds / self.duration:
            ctx.animator.play("flare")
        elif self.turning:
            ctx.animator.play("turn")
        else:
            ctx.animator.play("glide" if self.gliding else "fly")
        return None

    def _choose_glide(self, dx: float, dy: float, *, seconds_left: float, dt: float) -> None:
        """Flap or glide: short glides on the way down, one steady glide to land."""
        self.in_mode += dt
        descent = dy / (math.hypot(dx, dy) or 1.0)
        if seconds_left <= self.approach_seconds + self.flare_seconds:
            glide = descent > self.flap_below
        elif self.gliding:
            glide = descent > self.flap_below and self.in_mode < self.glide_bout
        else:
            glide = descent > self.glide_above and self.in_mode >= self.flaps_between
        if glide != self.gliding:
            self.gliding, self.in_mode = glide, 0.0

    def _perch_is_gone(self, ctx: Context, spot: Point) -> bool:
        if self.onto == "cursor":
            return math.dist(ctx.world.cursor(), spot) > ctx.config.px(12)
        if self.onto == "branch":
            branch = ctx.scenery.branch
            return branch is None or not branch.ready
        return False


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

    def food_nearby(self, ctx: Context) -> State | None:
        return go_to_food(ctx)

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


class Whistle(_OneShot):
    """Double-clicked: he bobs his head, crest up, and whistles (shown in a cloud)."""

    clip = "whistle"

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        ctx.say(ctx.rng.choice(ctx.config.whistles), ctx.config.speech_seconds)


class _Contentment:
    """Hearts now and then while he's being petted, and noticing when it stops."""

    heart_every: ClassVar[float] = 1.6
    stop_after: ClassVar[float] = 1.2
    """Seconds without a stroke before he decides the petting is over."""

    def __init__(self) -> None:
        self.since_heart = math.inf
        self.unpetted = 0.0

    def still_enjoying(self, ctx: Context, dt: float) -> bool:
        self.since_heart += dt
        if ctx.petting.active:
            self.unpetted = 0.0
            if self.since_heart >= self.heart_every:
                ctx.say("♥", 1.0, mood="love")
                self.since_heart = 0.0
        else:
            self.unpetted += dt
        return self.unpetted < self.stop_after


class Petted(State):
    """Being stroked: fluffed up, eyes shut, leaning into the hand. When the
    petting stops he gives a happy shake."""

    clip = "petted"

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        self.contentment = _Contentment()

    def petted(self, ctx: Context) -> State | None:
        return None  # already enjoying it

    def step(self, ctx: Context, dt: float) -> State | None:
        return None if self.contentment.still_enjoying(ctx, dt) else Shake()


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
        previous_y = body.y
        body.vx *= math.exp(-cfg.air_drag * dt)
        body.vy = min(body.vy + cfg.px(cfg.gravity) * dt, cfg.px(cfg.max_fall_speed))
        body.x += body.vx * dt
        body.y += body.vy * dt
        if _catches_branch(ctx, previous_y):
            return OnBranch(settle_in=True)

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
        previous_y = ctx.body.y
        ctx.body.x = x0 + (x1 - x0) * p
        ctx.body.y = y0 + (y1 - y0) * math.sin(math.pi / 2 * p)
        if _catches_branch(ctx, previous_y):
            return OnBranch(settle_in=True)
        if p >= 1.0:
            ctx.body.y = y1
            return Shake()
        if p >= self.flare_from:
            ctx.animator.play("flare")
        else:
            # A long way down: short glides between bursts of wingbeats, then one
            # steady glide for the last second, as in a flight (see Fly).
            cycle = Fly.glide_bout + Fly.flaps_between
            far_out = (1.0 - p) * self.duration > Fly.approach_seconds
            flapping = far_out and self.elapsed % cycle >= Fly.glide_bout
            ctx.animator.play("fly" if flapping else "glide")
        return None


def _catches_branch(ctx: Context, previous_y: float) -> bool:
    """Coming down through the branch's perch this tick: he grabs it."""
    branch = ctx.scenery.branch
    if branch is None or not branch.ready:
        return False
    lo, hi = branch.perch_span(ctx.config)
    reach = ctx.config.px(6)
    crossed = previous_y <= branch.top <= ctx.body.y
    if crossed and lo - reach <= ctx.body.x <= hi + reach:
        ctx.body.x = min(max(ctx.body.x, lo), hi)
        ctx.body.y, ctx.body.vx, ctx.body.vy = branch.top, 0.0, 0.0
        return True
    return False


class OnBranch(State):
    """Sitting on the branch, facing you.

    He looks about, preens, fluffs up, and naps when sleepy, then after a while
    flies off, down to the ground or on a tour. If the branch goes, he drops off
    and glides down. A poke startles him, but he stays put; a double-click gets
    a whistle and petting works here too.
    """

    clip = "branch_idle"
    grounded = False
    sit_for: ClassVar[tuple[float, float]] = (4.0, 10.0)
    clips: ClassVar[dict[str, str]] = {
        "sit": "branch_idle",
        "preen": "branch_preen",
        "fluff": "branch_fluff",
        "sleep": "branch_sleep",
        "alert": "branch_alert",
        "whistle": "branch_whistle",
        "petted": "branch_petted",
    }

    def __init__(self, *, settle_in: bool = False) -> None:
        super().__init__()
        self.settle_in = settle_in
        """Caught the branch on the way down: ruffle his feathers first."""

    @property
    def holds_branch(self) -> bool:
        return True

    def food_nearby(self, ctx: Context) -> State | None:
        return go_to_food(ctx)  # seeds beat a branch

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        self.stay = ctx.rng.uniform(*ctx.config.branch_visit)
        self._do(ctx, "fluff" if self.settle_in else "sit")

    def clicked(self, ctx: Context) -> State | None:
        self._do(ctx, "alert")
        return None

    def double_clicked(self, ctx: Context) -> State | None:
        self._do(ctx, "whistle")
        ctx.say(ctx.rng.choice(ctx.config.whistles), ctx.config.speech_seconds)
        return None

    def petted(self, ctx: Context) -> State | None:
        if self.doing != "petted":
            self._do(ctx, "petted")
            self.contentment = _Contentment()
        return None

    def step(self, ctx: Context, dt: float) -> State | None:
        branch = ctx.scenery.branch
        if branch is None or not branch.ready:  # it's going: drop off and glide down
            ctx.body.vx = ctx.body.vy = 0.0
            return Fall()
        lo, hi = branch.perch_span(ctx.config)
        ctx.body.x, ctx.body.y = min(max(ctx.body.x, lo), hi), branch.top

        if self.doing == "petted":
            if not self.contentment.still_enjoying(ctx, dt):
                self._do(ctx, "fluff")
            return None
        if self.doing == "sleep":
            if not is_sleepy(ctx):
                self._do(ctx, "sit")
            return None
        if self.doing != "sit":
            if ctx.animator.finished:
                self._do(ctx, "sit")
            return None
        if self.elapsed < self.until:
            return None
        if self.elapsed >= self.stay:
            return self._fly_off(ctx, branch)
        if is_sleepy(ctx) and ctx.rng.random() < 0.6:
            self._do(ctx, "sleep")
        else:
            self._do(ctx, ctx.rng.choices(("preen", "fluff", "sit"), (0.4, 0.2, 0.4))[0])
        return None

    def _fly_off(self, ctx: Context, branch: Branch) -> Fly:
        """Launch into the screen, then glide down or set off on a tour."""
        cfg, body = ctx.config, ctx.body
        body.facing = Facing(branch.inward)
        if ctx.rng.random() >= 0.3:
            return Fly.down(ctx)
        launch = (body.x + branch.inward * cfg.px(30), branch.top - cfg.px(12))
        tour = Fly.tour(ctx).waypoints or ()
        return Fly([launch, *tour])

    def _do(self, ctx: Context, what: str) -> None:
        self.doing = what
        ctx.animator.play(self.clips[what], restart=True)
        self.until = self.elapsed + ctx.rng.uniform(*self.sit_for)


class Caged(State):
    """Shut in the cage, sitting on its tray facing you.

    Furious at first: crest up, puffing and stamping, with angry clouds. Then he
    sulks, preens, naps and grumbles now and then. Being carried about, hung up
    or bumped down sets him off again; petting through the bars calms him. When
    the door opens he flies out, a little huffy.
    """

    clip = "front_angry"
    grounded = False
    tantrum: ClassVar[tuple[float, float]] = (8.0, 12.0)
    sit_for: ClassVar[tuple[float, float]] = (5.0, 12.0)
    clips: ClassVar[dict[str, str]] = {
        "angry": "front_angry",
        "sit": "front_idle",
        "preen": "front_preen",
        "fluff": "front_fluff",
        "sleep": "front_sleep",
        "petted": "front_petted",
        "eat": "front_eat",
    }

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        self.until = 0.0
        self.next_seed = 0.0
        self._provoked(ctx, ctx.rng.choice(ctx.config.complaints))
        self.anger = ctx.rng.uniform(*self.tantrum)
        self._place(ctx)

    def clicked(self, ctx: Context) -> State | None:
        return None

    def double_clicked(self, ctx: Context) -> State | None:
        return None

    def petted(self, ctx: Context) -> State | None:
        if self.doing not in ("petted", "eat"):
            self._do(ctx, "petted")
            self.contentment = _Contentment()
            self.anger = 0.0
        return None

    def food_nearby(self, ctx: Context) -> State | None:
        return None  # only seeds on his tray, which he sees to himself

    def step(self, ctx: Context, dt: float) -> State | None:
        cage = ctx.cage
        if cage is None:
            return Idle()
        self._place(ctx)
        if cage.door_open:
            cage.left = True
            return self._fly_out(ctx, cage.x)
        food = ctx.food
        if food is not None and food.in_cage and self.doing != "eat":
            self._do(ctx, "eat")  # seeds! all is forgiven, for now
            self.anger, self.next_seed = 0.0, 0.22
        for event in cage.take_events():
            self._provoked(ctx, "ow!" if event == "bump" else None)
        if cage.mount == "held" and self.doing != "angry":
            self._provoked(ctx)

        if self.doing == "angry":
            self.anger -= dt
            self.next_complaint -= dt
            if self.next_complaint <= 0:
                ctx.say(ctx.rng.choice(ctx.config.complaints), 2.0, mood="angry")
                self.next_complaint = ctx.rng.uniform(2.0, 3.5)
            if self.anger <= 0 and cage.mount != "held":
                self._do(ctx, "sit")
            return None
        if self.doing == "eat":
            self.next_seed -= dt
            if food is None or not food.in_cage:
                self._do(ctx, "sit")
            elif self.next_seed <= 0:
                food.seeds -= 1
                self.next_seed += SECONDS_PER_SEED
                if food.seeds <= 0:
                    ctx.food = None
                    ctx.say("yum! ♥", 1.8, mood="love")
                    self._do(ctx, "fluff")
            return None
        if self.doing == "petted":
            if not self.contentment.still_enjoying(ctx, dt):
                self._do(ctx, "fluff")
            return None
        if self.doing == "sleep":
            if not is_sleepy(ctx):
                self._do(ctx, "sit")
            return None
        if self.doing != "sit":
            if ctx.animator.finished:
                self._do(ctx, "sit")
            return None
        if self.elapsed < self.until:
            return None
        if is_sleepy(ctx) and ctx.rng.random() < 0.6:
            self._do(ctx, "sleep")
            return None
        pick = ctx.rng.choices(("preen", "fluff", "sit", "grumble"), (0.3, 0.2, 0.3, 0.2))[0]
        if pick == "grumble":
            self._provoked(ctx)
            self.anger = ctx.rng.uniform(2.0, 3.0)
        else:
            self._do(ctx, pick)
        return None

    def _provoked(self, ctx: Context, text: str | None = None) -> None:
        self.anger = max(getattr(self, "anger", 0.0), 3.0)
        self._do(ctx, "angry")
        ctx.say(text or ctx.rng.choice(ctx.config.complaints), 2.0, mood="angry")
        self.next_complaint = ctx.rng.uniform(2.0, 3.5)

    def _place(self, ctx: Context) -> None:
        if ctx.cage is not None:
            ctx.body.x, ctx.body.y = ctx.cage.shown_x, ctx.cage.y
            ctx.body.vx = ctx.body.vy = 0.0

    def _fly_out(self, ctx: Context, cage_x: float) -> Fly:
        """Out of the door and down, heading into the screen, away from the nearer edge."""
        cfg, body, area = ctx.config, ctx.body, ctx.area()
        d = 1 if cage_x < (area.left + area.right) / 2 else -1
        body.facing = Facing(d)
        ctx.say("hmph.", 1.5)
        x1 = area.clamp_x(body.x + d * ctx.rng.uniform(cfg.px(70), cfg.px(160)), ctx.margin)
        hop = (body.x + d * cfg.px(18), body.y - cfg.px(16))
        return Fly([hop, *_landing(ctx, x1, coming_from=body.x)])

    def _do(self, ctx: Context, what: str) -> None:
        self.doing = what
        ctx.animator.play(self.clips[what], restart=True)
        self.until = self.elapsed + ctx.rng.uniform(*self.sit_for)


def go_to_food(ctx: Context) -> State:
    """Head for the seeds: walk if they're near, fly if they're far or he's up high.

    He stands beside the pile on the side he comes from, so that pecking puts his
    beak right on it.
    """
    food, cfg, body, area = ctx.food, ctx.config, ctx.body, ctx.area()
    assert food is not None
    side = -1 if body.x > food.x else 1
    spot = food.x - side * cfg.px(PECK_REACH)
    on_ground = body.y >= area.bottom - 1
    if on_ground and abs(spot - body.x) <= cfg.px(160):
        return Walk(spot, eat=True)
    return Fly(
        [*_takeoff(ctx, towards=spot), *_landing(ctx, spot, coming_from=body.x)], onto="food"
    )


class Eat(State):
    """Pecking up the seeds one by one, cracking each open. When they're gone he's
    very pleased with himself."""

    clip = "eat"

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        if ctx.food is not None:
            ctx.body.face_towards(ctx.food.x)
        self.next_seed = 0.24  # the first peck lands this far into the clip

    def food_nearby(self, ctx: Context) -> State | None:
        return None

    def step(self, ctx: Context, dt: float) -> State | None:
        food = ctx.food
        if food is None or food.in_cage:
            return Idle()
        self.next_seed -= dt
        if self.next_seed > 0:
            return None
        food.seeds -= 1
        self.next_seed += SECONDS_PER_SEED
        if food.seeds > 0:
            return None
        ctx.food = None
        ctx.say("yum! ♥", 1.8, mood="love")
        return Shake()
