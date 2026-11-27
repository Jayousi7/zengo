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
from zengo.behavior.food import SECONDS_PER_SEED, SEEDS_PER_STACK, STAND_OFF
from zengo.sounds import CHIRPS, whistle_for
from zengo.sprites.bath import DISH_WIDTH
from zengo.sprites.clips import RING_PECKS
from zengo.world import Area, Ledge


class State:
    clip: ClassVar[str]

    grounded: ClassVar[bool] = True
    """Grounded states are kept on the ground line and inside the screen by the brain."""

    effort: ClassVar[float] = 1.0
    """How hard he's working, as a multiple of resting: how fast he gets hungry."""

    chirpy: ClassVar[bool] = False
    """Pottering about, he chirps now and then (see ``Config.chirp_every``)."""

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

    def typing(self, ctx: Context) -> State | None:
        """You're typing. Sitting about with nothing better to do, he bobs along."""
        return None

    def go_eat(self, ctx: Context) -> State | None:
        """He's hungry and there are seeds down. Settled on the ground he goes for
        them; held or mid-air, once he's landed."""
        return go_to_food(ctx) if self.grounded else None

    def ask_for_food(self, ctx: Context) -> State | None:
        """He's hungry and there's nothing to eat: he comes to you and asks."""
        return go_ask(ctx) if self.grounded else None

    @property
    def holds_branch(self) -> bool:
        """He's on the branch or on his way to it, so it mustn't withdraw yet."""
        return False

    @property
    def holds_bath(self) -> bool:
        """He's in his bath or on his way to it, so it mustn't go yet."""
        return False

    @property
    def at_mirror(self) -> bool:
        """He's in front of his mirror: his reflection shows in it."""
        return False

    def __repr__(self) -> str:
        return type(self).__name__


AFTERNOON = (13, 18)
"""Local hours [start, end) when a summer day is at its hottest."""


class Idle(State):
    clip = "idle"
    chirpy = True

    def typing(self, ctx: Context) -> State | None:
        return Bob()

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        if ctx.season() == "summer" and AFTERNOON[0] <= ctx.world.local_hour() < AFTERNOON[1]:
            ctx.animator.play("pant", restart=True)  # hot: beak open, panting
        self.duration = ctx.rng.uniform(*ctx.config.idle_seconds)

    def step(self, ctx: Context, dt: float) -> State | None:
        cx, cy = ctx.world.cursor()
        reach = ctx.config.px(ctx.config.watch_radius)
        if abs(cx - ctx.body.x) < reach and abs(cy - ctx.body.y) < 2 * reach:
            if ctx.bond.grumpy(ctx.config) and self.elapsed > 0.5:
                # Grumpy: he'd rather not. Off he waddles, the other way.
                away = -1 if cx > ctx.body.x else 1
                ctx.say("hmph", 1.2, mood="angry")
                return Walk(ctx.body.x + away * ctx.config.px(ctx.rng.uniform(70, 120)))
            ctx.body.face_towards(cx)
        return choose_activity(ctx) if self.elapsed >= self.duration else None


def is_sleepy(ctx: Context) -> bool:
    cfg = ctx.config
    return ctx.world.user_idle_seconds() >= cfg.sleep_after or cfg.is_night(ctx.world.local_hour())


def can_fly(ctx: Context) -> bool:
    """Not while he's damp from his bath: he walks till he's dry."""
    return ctx.damp <= 0


def choose_activity(ctx: Context) -> State:
    """Weighted pick of what to do after idling."""
    if is_sleepy(ctx) and ctx.rng.random() < 0.6:
        return Sleep()
    flies = can_fly(ctx)
    season = ctx.season()
    # Devoted, he seeks you out; grumpy, he keeps away.
    bond, cfg = ctx.bond, ctx.config
    fondness = 2.2 if bond.close(cfg) else 0.0 if bond.grumpy(cfg) else 1.0
    options: list[tuple[Callable[[Context], State], float]] = [
        (lambda _: Idle(), 1.0),
        (lambda _: Walk(), 4.0),
        (lambda _: Preen(), 5.0 if ctx.moult.moulting_day(ctx) else 2.0),
        (Fly.hop, 0.6 if flies else 0.0),
        (Fly.tour, 0.8 if flies else 0.0),
        (lambda _: Follow(), 1.5 * fondness if _cursor_on_same_screen(ctx) else 0.0),
        (lambda _: FrontIdle(), 1.2),
        (lambda _: Puffed(), 3.0 if season == "winter" else 0.0),  # cold
        (lambda _: Whistle(), 1.5 if season == "spring" else 0.0),  # full of song
        (Fly.to_cursor, 3.0 * fondness if flies and cursor_is_inviting(ctx) else 0.0),
        (lambda _: Sulk(), 3.0 if ctx.bond.grumpy(ctx.config) else 0.0),
        (Fly.to_branch, 6.0 if flies and branch_is_inviting(ctx) else 0.0),  # he loves it
        (Fly.to_window, 2.5 if flies and perchable_ledges(ctx) else 0.0),
        (go_to_bath, 8.0 if ctx.bath.usable else 0.0),  # and he loves a bath
        (go_to_mirror, 1.5 if mirror_is_inviting(ctx) else 0.0),
    ]
    makers, weights = zip(*options, strict=True)
    return ctx.rng.choices(makers, weights)[0](ctx)


def _cursor_on_same_screen(ctx: Context) -> bool:
    return ctx.world.area_at(*ctx.world.cursor()) == ctx.area()


def perchable_ledges(ctx: Context) -> list[Ledge]:
    """Window tops on his screen he could sit on: wide enough for his feet, with room
    for him above, and up off the ground."""
    cfg, area = ctx.config, ctx.area()
    return [
        ledge
        for ledge in ctx.world.ledges()
        if ledge.right - ledge.left >= cfg.px(cfg.ledge_min_width)
        and area.top + cfg.px(36) <= ledge.y <= area.bottom - cfg.px(60)
        and ctx.world.area_at((ledge.left + ledge.right) / 2, ledge.y) == area
    ]


def _ledge_under(ctx: Context, window: int, x: float) -> Ledge | None:
    """The visible stretch of ``window``'s top edge at screen ``x``, if there is one."""
    reach = ctx.config.px(3)
    for ledge in ctx.world.ledges():
        if ledge.window == window and ledge.left - reach <= x <= ledge.right + reach:
            return ledge
    return None


def branch_is_inviting(ctx: Context) -> bool:
    """A branch is fully out on Zengo's screen and staying a while."""
    branch = ctx.scenery.branch
    if branch is None or not branch.ready or ctx.scenery.phase != "out":
        return False
    lo, hi = branch.perch_span(ctx.config)
    return ctx.world.area_at((lo + hi) / 2, branch.top) == ctx.area()


class Sulk(State):
    """Grumpy: sitting with his back to you, peeking round now and then to see if
    you've noticed. Petting brings him round."""

    clip = "sulk"
    effort = 0.6

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        self.duration = ctx.rng.uniform(8.0, 16.0)
        if ctx.rng.random() < 0.5:
            ctx.say("hmph", 1.5, mood="angry")

    def clicked(self, ctx: Context) -> State | None:
        ctx.say("...", 1.0)
        return None

    def double_clicked(self, ctx: Context) -> State | None:
        return None

    def step(self, ctx: Context, dt: float) -> State | None:
        return Idle() if self.elapsed >= self.duration else None


class Puffed(State):
    """Winter: sitting about puffed up against the cold."""

    clip = "puffed"
    chirpy = True
    effort = 0.8

    def typing(self, ctx: Context) -> State | None:
        return Bob()

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        self.duration = ctx.rng.uniform(6.0, 14.0)

    def step(self, ctx: Context, dt: float) -> State | None:
        return Idle() if self.elapsed >= self.duration else None


class FrontIdle(State):
    """Sitting facing you for a while, looking about."""

    clip = "front_idle"
    chirpy = True
    sit_for: ClassVar[tuple[float, float]] = (4.0, 10.0)

    def typing(self, ctx: Context) -> State | None:
        return Bob(facing_you=True)

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        self.duration = ctx.rng.uniform(*self.sit_for)

    def step(self, ctx: Context, dt: float) -> State | None:
        return choose_activity(ctx) if self.elapsed >= self.duration else None


class Walk(State):
    """Waddle to ``target`` (screen x), or to a random nearby spot."""

    clip = "walk"
    chirpy = True
    effort = 1.6  # waddling

    def __init__(self, target: float | None = None, *, then: str | None = None) -> None:
        super().__init__()
        self.target = target
        self.then = then
        """On arrival: ``"eat"`` the seeds, ``"ask"`` you for some, ``"bathe"``, or
        chat to his ``"mirror"``."""

    @property
    def holds_bath(self) -> bool:
        return self.then == "bathe"

    def go_eat(self, ctx: Context) -> State | None:
        return None if self.then == "eat" else super().go_eat(ctx)

    def ask_for_food(self, ctx: Context) -> State | None:
        return None if self.then in ("eat", "ask") else super().ask_for_food(ctx)

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        if self.target is None:
            if (
                ctx.bond.close(ctx.config)
                and _cursor_on_same_screen(ctx)
                and ctx.rng.random() < 0.5
            ):
                # Devoted: he potters over to settle near where you're working.
                cx = ctx.world.cursor()[0]
                self.target = cx + ctx.config.px(ctx.rng.uniform(30, 60)) * ctx.rng.choice((-1, 1))
            else:
                distance = ctx.config.px(ctx.rng.uniform(25, 130)) * ctx.rng.choice((-1, 1))
                self.target = ctx.body.x + distance
        self.target = ctx.area().clamp_x(self.target, ctx.margin)
        ctx.body.face_towards(self.target)

    def step(self, ctx: Context, dt: float) -> State | None:
        assert self.target is not None
        if not _walk_towards(ctx, self.target, dt):
            return None
        if self.then == "eat" and ctx.food is not None:
            return Eat()
        if self.then == "bathe":
            return Bathe() if ctx.bath.usable else Idle()
        if self.then == "mirror":
            return PlayMirror() if ctx.toys.mirror is not None else Idle()
        return Ask() if self.then == "ask" else Idle()


class Follow(State):
    """Walk after the cursor's x position for a while."""

    clip = "walk"
    chirpy = True
    effort = 1.6  # waddling
    give_up_after: ClassVar[float] = 10.0
    close_enough: ClassVar[float] = 24.0  # art px

    def step(self, ctx: Context, dt: float) -> State | None:
        if self.elapsed >= self.give_up_after or not _cursor_on_same_screen(ctx):
            return Idle()
        target = ctx.area().clamp_x(ctx.world.cursor()[0], ctx.margin)
        if abs(target - ctx.body.x) <= ctx.config.px(self.close_enough):
            ctx.body.face_towards(target)
            return Idle()
        _walk_towards(ctx, target, dt)
        return None


STRIDE = 3
"""Art pixels between his feet, and so how far one step carries him."""


def _walk_towards(ctx: Context, target: float, dt: float) -> bool:
    """Advance one tick towards ``target``. Returns True on arrival.

    He moves in whole strides, one per step, at the instant the push-off frame
    gives way to the reach: in the push-off his front foot is planted under him,
    in the reach the same foot is a stride further back. Moving the body by
    exactly that much then keeps the planted foot still on the screen, so his
    feet never slide.
    """
    body = ctx.body
    body.face_towards(target)
    remaining = target - body.x
    if abs(remaining) < 0.5:
        body.x = target
        return True
    frame = ctx.animator.base_frame
    if body.gait == "step_back" and frame != "step_back":
        stride = ctx.config.px(STRIDE)
        body.x += max(-stride, min(stride, remaining))
    body.gait = frame
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
    effort = 3.0  # flight burns energy
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
        self.window: int | None = None
        self.offset = 0.0
        """Going to a window (``onto="window"``): which, and how far along it."""
        self.onto = onto
        """Where he's going: ``"ground"``, ``"cursor"``, ``"branch"``, to the seeds
        (``"food"``), to you to ask for some (``"ask"``), or off the screen
        (``"away"``)."""
        self.away_side = 1
        self.away_area: Area | None = None

    @property
    def holds_branch(self) -> bool:
        return self.onto == "branch"

    @property
    def holds_bath(self) -> bool:
        return self.onto == "bath"

    def go_eat(self, ctx: Context) -> State | None:
        return None  # lands first: flying to the seeds already, or will after

    def ask_for_food(self, ctx: Context) -> State | None:
        return None

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
        bell = ctx.toys.bell
        if bell is not None and bell.where == "branch" and ctx.rng.random() < 0.7:
            # His bell's out: he likes to sit where he can reach it.
            x = min(max(bell.x, lo), hi)
        approach_x = ctx.area().clamp_x(x + branch.inward * cfg.px(55), ctx.margin)
        approach = (approach_x, branch.top - cfg.px(18))
        return cls([*_takeoff(ctx, towards=approach_x), approach, (x, branch.top)], onto="branch")

    @classmethod
    def to_window(cls, ctx: Context) -> Fly:
        """Fly up onto the top of one of your windows, coming in from his side."""
        cfg = ctx.config
        ledge = ctx.rng.choice(perchable_ledges(ctx))
        inset = cfg.px(6)
        x = ctx.rng.uniform(ledge.left + inset, max(ledge.left + inset, ledge.right - inset))
        side = -1 if ctx.body.x < x else 1
        approach_x = ctx.area().clamp_x(x + side * cfg.px(55), ctx.margin)
        approach = (approach_x, ledge.y - cfg.px(18))
        flight = cls([*_takeoff(ctx, towards=approach_x), approach, (x, ledge.y)], onto="window")
        flight.window, flight.offset = ledge.window, x - ledge.window_left
        return flight

    @classmethod
    def to_middle(cls, ctx: Context) -> Fly:
        """Fly to the middle of the screen and land there: here I am!"""
        area = ctx.area()
        x = (area.left + area.right) / 2
        top = area.top + 0.45 * (area.bottom - area.top)
        return cls([*_takeoff(ctx, towards=x), (x, top), *_landing(ctx, x, coming_from=ctx.body.x)])

    @classmethod
    def away(cls, ctx: Context) -> Fly:
        """Fly up and off the nearer side of the screen, out of sight."""
        cfg, area = ctx.config, ctx.area()
        side = -1 if ctx.body.x - area.left < area.right - ctx.body.x else 1
        edge = area.left if side < 0 else area.right
        height = area.bottom - area.top
        out = (edge + side * cfg.px(OFF_SCREEN), area.top + 0.3 * height)
        flight = cls([*_takeoff(ctx, towards=edge), out], onto="away")
        flight.away_side, flight.away_area = side, area
        return flight

    @classmethod
    def back(cls, ctx: Context, away: Away) -> Fly:
        """In from the side he left by, to land a little way in."""
        cfg = ctx.config
        area = away.area or ctx.area()
        edge = area.left if away.side < 0 else area.right
        height = area.bottom - area.top
        ctx.body.x, ctx.body.y = edge + away.side * cfg.px(OFF_SCREEN), area.top + 0.3 * height
        x = edge - away.side * ctx.rng.uniform(cfg.px(120), cfg.px(260))
        x = area.clamp_x(x, ctx.margin)
        return cls(_landing(ctx, x, coming_from=ctx.body.x))

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
            if self.onto == "ask":
                return Ask()
            if self.onto == "bath":
                return Bathe() if ctx.bath.usable else Idle()
            if self.onto == "mirror":
                return PlayMirror() if ctx.toys.mirror is not None else Idle()
            if self.onto == "window":
                return OnWindow(self.window, self.offset)
            if self.onto == "away":
                return Away(self.away_side, self.away_area)
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
        if self.onto == "window":
            # Gone, moved, or covered where he means to land: he'll glide down instead.
            ledge = _ledge_under(ctx, self.window, spot[0])
            if ledge is None:
                return True
            moved = abs(ledge.window_left + self.offset - spot[0]) > ctx.config.px(4)
            return moved or abs(ledge.y - spot[1]) > ctx.config.px(4)
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

    clip = "ledge_idle"  # side-on, tail hanging down past the pointer
    grounded = False
    stay: ClassVar[tuple[float, float]] = (6.0, 20.0)
    startle_hop: ClassVar[float] = 60.0
    """Art px/s upwards when the pointer moves out from under him."""

    def go_eat(self, ctx: Context) -> State | None:
        return go_to_food(ctx)

    def ask_for_food(self, ctx: Context) -> State | None:
        return go_ask(ctx)

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
    effort = 0.4  # hardly anything
    nap_seconds: ClassVar[tuple[float, float]] = (120.0, 300.0)

    def go_eat(self, ctx: Context) -> State | None:
        return None  # hunger can wait till he wakes

    def ask_for_food(self, ctx: Context) -> State | None:
        return None

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
        ctx.whistle()


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
                ctx.say(ctx.phrase("petted"), 1.0, mood="love")
                self.since_heart = 0.0
        else:
            self.unpetted += dt
        return self.unpetted < self.stop_after


class Petted(State):
    """Being stroked: fluffed up, eyes shut, leaning into the hand. When the
    petting stops he gives a happy shake."""

    clip = "petted"
    effort = 0.8  # blissful

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
    effort = 2.0  # struggling
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
    effort = 2.0  # flapping hard
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
    effort = 1.5  # coasting
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


class _Perched(State):
    """Sitting somewhere up off the ground: a branch, the top of a window.

    He looks about, preens, fluffs up, naps when sleepy and bobs along to your
    typing; a poke startles him but he stays put, a double-click gets a whistle,
    and petting works here too. After a while he flies off. If the perch goes from
    under him, he drops off and glides down. Subclasses say where the perch is,
    which clips suit it, and how he leaves.
    """

    chirpy = True
    grounded = False
    sit_for: ClassVar[tuple[float, float]] = (4.0, 10.0)
    clips: ClassVar[dict[str, str]]

    def __init__(self, *, settle_in: bool = False) -> None:
        super().__init__()
        self.settle_in = settle_in
        """Landed in a hurry (caught it on the way down): ruffle his feathers first."""

    @property
    def effort(self) -> float:  # type: ignore[override]
        return 0.4 if getattr(self, "doing", "") == "sleep" else 1.0

    def visit(self, ctx: Context) -> tuple[float, float]:
        """Seconds he stays, at least and at most."""
        raise NotImplementedError

    def settle(self, ctx: Context) -> bool:
        """Put him on the perch where it is now. False if it's gone from under him."""
        raise NotImplementedError

    def fly_off(self, ctx: Context) -> State:
        raise NotImplementedError

    def go_eat(self, ctx: Context) -> State | None:
        return go_to_food(ctx)  # seeds beat any perch

    def ask_for_food(self, ctx: Context) -> State | None:
        return go_ask(ctx)

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        self.stay = ctx.rng.uniform(*self.visit(ctx))
        self._do(ctx, "fluff" if self.settle_in else "sit")

    def clicked(self, ctx: Context) -> State | None:
        self._do(ctx, "alert")
        return None

    def double_clicked(self, ctx: Context) -> State | None:
        self._do(ctx, "whistle")
        ctx.whistle()
        return None

    def petted(self, ctx: Context) -> State | None:
        if self.doing != "petted":
            self._do(ctx, "petted")
            self.contentment = _Contentment()
        return None

    def typing(self, ctx: Context) -> State | None:
        if self.doing == "sit":
            self._do(ctx, "bob")
        return None

    def step(self, ctx: Context, dt: float) -> State | None:
        if self.doing == "ring":
            _ring_bell(ctx, self.elapsed - self.did_at, dt)
        if not self.settle(ctx):  # it's gone: startled, he flaps off and glides down
            ctx.body.vx, ctx.body.vy = 0.0, -ctx.config.px(40)
            ctx.animator.interject("startle")
            ctx.play("chirp_b")
            return Fall()
        if self.doing == "petted":
            if not self.contentment.still_enjoying(ctx, dt):
                self._do(ctx, "fluff")
            return None
        if self.doing == "bob":
            if not ctx.typing.active:
                self._do(ctx, "sit")
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
            return self.fly_off(ctx)
        if is_sleepy(ctx) and ctx.rng.random() < 0.6:
            self._do(ctx, "sleep")
        elif "ring" in self.clips and bell_in_reach(ctx, "branch"):
            self._do(ctx, "ring")
        else:
            self._do(ctx, ctx.rng.choices(("preen", "fluff", "sit"), (0.4, 0.2, 0.4))[0])
        return None

    def _do(self, ctx: Context, what: str) -> None:
        if what == "ring" and ctx.toys.bell is not None:
            ctx.body.face_towards(ctx.toys.bell.x)
        if getattr(self, "doing", "") == "ring":
            ctx.toys.played(ctx)
        self.doing = what
        self.did_at = self.elapsed
        ctx.animator.play(self.clips[what], restart=True)
        self.until = self.elapsed + ctx.rng.uniform(*self.sit_for)


class OnBranch(_Perched):
    """Sitting on the branch, facing you."""

    clip = "branch_idle"
    clips: ClassVar[dict[str, str]] = {
        "sit": "branch_idle",
        "preen": "branch_preen",
        "fluff": "branch_fluff",
        "sleep": "branch_sleep",
        "alert": "branch_alert",
        "whistle": "branch_whistle",
        "petted": "branch_petted",
        "bob": "branch_bob",
        "ring": "branch_ring",
    }

    @property
    def holds_branch(self) -> bool:
        return True

    def visit(self, ctx: Context) -> tuple[float, float]:
        return ctx.config.branch_visit

    def settle(self, ctx: Context) -> bool:
        branch = ctx.scenery.branch
        if branch is None or not branch.ready:
            return False
        lo, hi = branch.perch_span(ctx.config)
        ctx.body.x, ctx.body.y = min(max(ctx.body.x, lo), hi), branch.top
        return True

    def fly_off(self, ctx: Context) -> State:
        """Launch into the screen, then glide down or set off on a tour."""
        branch = ctx.scenery.branch
        assert branch is not None
        cfg, body = ctx.config, ctx.body
        body.facing = Facing(branch.inward)
        if ctx.rng.random() >= 0.3:
            return Fly.down(ctx)
        launch = (body.x + branch.inward * cfg.px(30), branch.top - cfg.px(12))
        tour = Fly.tour(ctx).waypoints or ()
        return Fly([launch, *tour])


class OnWindow(_Perched):
    """Sitting on top of one of your windows, side-on.

    Move the window and he rides along. Close, minimize or maximize it, or put
    another window over where he sits, and he startles and flutters down.
    """

    # Side-on, with his tail hanging down over the window's edge.
    clip = "ledge_idle"
    clips: ClassVar[dict[str, str]] = {
        "sit": "ledge_idle",
        "preen": "ledge_preen",
        "fluff": "ledge_shake",
        "sleep": "ledge_sleep",
        "alert": "ledge_alert",
        "whistle": "ledge_whistle",
        "petted": "ledge_petted",
        "bob": "ledge_bob",
    }

    def __init__(self, window: int, offset: float, *, settle_in: bool = False) -> None:
        super().__init__(settle_in=settle_in)
        self.window = window
        self.offset = offset
        """How far along the window, from its left edge, he sits."""

    def visit(self, ctx: Context) -> tuple[float, float]:
        return ctx.config.window_visit

    def settle(self, ctx: Context) -> bool:
        """Sit at his place along the window, wherever the window is right now.

        Whether his stretch of the top edge is still in view comes from the
        window list (re-read a few times a second); where the window is comes
        from a fresh read of it each frame when there is one, so he rides along
        smoothly as it's dragged.
        """
        reach = ctx.config.px(3)
        ledge = next(
            (
                ledge
                for ledge in ctx.world.ledges()
                if ledge.window == self.window
                and ledge.left - ledge.window_left - reach
                <= self.offset
                <= ledge.right - ledge.window_left + reach
            ),
            None,
        )
        if ledge is None:
            return False
        left, y = ledge.window_left, ledge.y
        live = ctx.world.window_frame(self.window)
        if live is not None:
            left, y = live.left, live.top
        along = min(
            max(self.offset, ledge.left - ledge.window_left), ledge.right - ledge.window_left
        )
        body = ctx.body
        x = left + along
        self.moving = abs(x - body.x) + abs(y - body.y) > 0.5 and self.elapsed > 0
        body.x, body.y = x, y
        return True

    def step(self, ctx: Context, dt: float) -> State | None:
        was = getattr(self, "doing", "")
        following = super().step(ctx, dt)
        if following is None and getattr(self, "moving", False):
            if was == "sleep":  # woken by the ride
                self._do(ctx, "alert")
            elif self.doing != "petted":
                ctx.animator.interject("ledge_grip")  # crest up, a wing out for balance
        return following

    def fly_off(self, ctx: Context) -> State:
        """Hop off towards the middle of the screen, then glide down or tour."""
        cfg, area, body = ctx.config, ctx.area(), ctx.body
        body.facing = Facing.RIGHT if body.x < (area.left + area.right) / 2 else Facing.LEFT
        if ctx.rng.random() >= 0.3:
            return Fly.down(ctx)
        hop = (body.x + int(body.facing) * cfg.px(25), body.y - cfg.px(12))
        return Fly([hop, *(Fly.tour(ctx).waypoints or ())])


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
        "escape": "front_pick",
        "bob": "front_bob",
        "ring": "front_ring",
        "chat": "front_chat",
    }

    @property
    def at_mirror(self) -> bool:
        return getattr(self, "doing", "") == "chat"

    def __init__(self, *, just_caught: bool = True) -> None:
        super().__init__()
        self.just_caught = just_caught
        """Furious if he's just been caught; calm if he was simply in here already
        (as when he's started up again caged)."""

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        self.until = 0.0
        self.next_seed = 0.0
        if self.just_caught:
            self._provoked(ctx, ctx.phrase("caged"))
            self.anger = ctx.rng.uniform(*self.tantrum)
        else:
            self.anger = 0.0
            self._do(ctx, "sit")
        self._place(ctx)

    def clicked(self, ctx: Context) -> State | None:
        return None

    def double_clicked(self, ctx: Context) -> State | None:
        return None

    def petted(self, ctx: Context) -> State | None:
        if ctx.cage is not None and ctx.cage.mount == "held":
            return None  # being carried about is no time for a cuddle
        if self.doing not in ("petted", "eat"):
            self._do(ctx, "petted")
            self.contentment = _Contentment()
            self.anger = 0.0
        return None

    @property
    def effort(self) -> float:  # type: ignore[override]
        doing = getattr(self, "doing", "")
        return {"angry": 1.5, "escape": 1.5, "sleep": 0.4}.get(doing, 1.0)

    def typing(self, ctx: Context) -> State | None:
        if self.doing == "sit":
            self._do(ctx, "bob")
        return None

    def go_eat(self, ctx: Context) -> State | None:
        return None  # only his dish counts in here, and he sees to that himself

    def ask_for_food(self, ctx: Context) -> State | None:
        return None

    def step(self, ctx: Context, dt: float) -> State | None:
        cage = ctx.cage
        if cage is None:
            return Idle()
        self._place(ctx)
        if cage.door_open:
            cage.left = True
            return self._fly_out(ctx, cage.x)
        hunger, dish = ctx.hunger, cage.dish
        busy = self.doing in ("eat", "escape")
        if hunger.hungry and dish.seeds > 0 and not busy:
            self._do(ctx, "eat")  # dinner! all is forgiven, for now
            self.anger, self.next_seed, self.to_eat = 0.0, 0.22, SEEDS_PER_STACK
        elif hunger.wants_to_ask and not busy and self.doing != "sleep":
            ctx.say(ctx.phrase("hungry"), ctx.config.complaint_seconds)
            ctx.play("ask")
            hunger.asked(ctx)  # all he can do from in here
        if self.doing == "escape":
            if self.elapsed >= self.door_at:
                cage.door_open = cage.escaped = True
                ctx.escape.escaped()  # out by his own wits: start over
            return None
        if (
            cage.mount != "held"
            and self.doing not in ("eat", "sleep", "petted")
            and ctx.escape.tries_to_escape(ctx)
        ):
            self._do(ctx, "escape")  # working the latch...
            self.door_at = self.elapsed + 2.2
            ctx.say("hmm...", 2.0)
            return None
        for event in cage.take_events():
            self._provoked(ctx, "ow!" if event == "bump" else None)
        if cage.mount == "held" and self.doing != "angry":
            self._provoked(ctx)

        if self.doing == "angry":
            self.anger -= dt
            self.next_complaint -= dt
            if self.next_complaint <= 0:
                ctx.say(
                    ctx.phrase("caged"),
                    ctx.config.complaint_seconds,
                    mood="angry",
                )
                ctx.play("chirp_b")  # cross, but soft: no squawking at your desk
                self.next_complaint = ctx.rng.uniform(*ctx.config.complaint_every)
            if self.anger <= 0 and cage.mount != "held":
                self._do(ctx, "sit")
            return None
        if self.doing == "eat":
            self.next_seed -= dt
            if self.next_seed <= 0:
                self.next_seed += SECONDS_PER_SEED
                if dish.take_seed():
                    self.to_eat -= 1
                    hunger.ate_seed(ctx)
                if self.to_eat <= 0 or dish.seeds <= 0 or hunger.full:
                    hunger.fed()
                    ctx.say(ctx.phrase("fed"), 1.8, mood="love")
                    ctx.play("trill")
                    self._do(ctx, "fluff")
            return None
        if self.doing == "petted":
            if not self.contentment.still_enjoying(ctx, dt):
                self._do(ctx, "fluff")
            return None
        if self.doing == "bob":
            if not ctx.typing.active:
                self._do(ctx, "sit")
            return None
        if self.doing == "sleep":
            if not is_sleepy(ctx):
                self._do(ctx, "sit")
            return None
        into = self.elapsed - self.did_at
        if self.doing == "ring":
            _ring_bell(ctx, into, dt)
        if self.doing == "chat" and into - dt < PlayMirror.chat_at <= into:
            ctx.say(ctx.phrase("toy"), 1.8)
            ctx.play(ctx.rng.choice(CHIRPS))
        if self.doing != "sit":
            if ctx.animator.finished:
                self._do(ctx, "sit")
            return None
        if self.elapsed < self.until:
            return None
        if is_sleepy(ctx) and ctx.rng.random() < 0.6:
            self._do(ctx, "sleep")
            return None
        games = [
            *(["ring"] if bell_in_reach(ctx, "cage") else []),
            *(["chat"] if ctx.toys.ready() and ctx.toys.mirror is not None else []),
        ]
        if games and ctx.rng.random() < 0.6:
            self._do(ctx, ctx.rng.choice(games))
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
        ctx.say(
            text or ctx.phrase("caged"),
            ctx.config.complaint_seconds,
            mood="angry",
        )
        ctx.play("chirp_b")  # cross, but soft: no squawking at your desk
        self.next_complaint = ctx.rng.uniform(*ctx.config.complaint_every)

    def _place(self, ctx: Context) -> None:
        if ctx.cage is not None:
            ctx.body.x, ctx.body.y = ctx.cage.shown_x, ctx.cage.y
            ctx.body.vx = ctx.body.vy = 0.0

    def _fly_out(self, ctx: Context, cage_x: float) -> Fly:
        """Out of the door and down, heading into the screen, away from the nearer edge."""
        cfg, body, area = ctx.config, ctx.body, ctx.area()
        d = 1 if cage_x < (area.left + area.right) / 2 else -1
        body.facing = Facing(d)
        assert ctx.cage is not None
        ctx.say(ctx.phrase("freed") if ctx.cage.escaped else "hmph.", 2.0)
        if ctx.cage.escaped:
            ctx.play("trill")
        x1 = area.clamp_x(body.x + d * ctx.rng.uniform(cfg.px(70), cfg.px(160)), ctx.margin)
        hop = (body.x + d * cfg.px(18), body.y - cfg.px(16))
        return Fly([hop, *_landing(ctx, x1, coming_from=body.x)])

    def _do(self, ctx: Context, what: str) -> None:
        toy = {"ring": ctx.toys.bell, "chat": ctx.toys.mirror}.get(what)
        if toy is not None:
            ctx.body.face_towards(toy.x)
        if getattr(self, "doing", "") in ("ring", "chat"):
            ctx.toys.played(ctx)
        self.doing = what
        self.did_at = self.elapsed
        ctx.animator.play(self.clips[what], restart=True)
        self.until = self.elapsed + ctx.rng.uniform(*self.sit_for)


def go_to_food(ctx: Context) -> State:
    """Head for the seeds: walk if they're near, fly if they're far or he's up high.

    He stands beside the pile on the side he comes from, so that pecking puts his
    beak just inside its near edge.
    """
    food, cfg, body, area = ctx.food, ctx.config, ctx.body, ctx.area()
    assert food is not None
    side = -1 if body.x > food.x else 1
    spot = food.x - side * cfg.px(STAND_OFF)
    on_ground = body.y >= area.bottom - 1
    if on_ground and (abs(spot - body.x) <= cfg.px(160) or not can_fly(ctx)):
        return Walk(spot, then="eat")
    return Fly(
        [*_takeoff(ctx, towards=spot), *_landing(ctx, spot, coming_from=body.x)], onto="food"
    )


class Eat(State):
    """Hungry, he pecks up seeds one by one, cracking each open, each filling him
    up a little: a meal is one stack, or less if he's full first. Then he's very
    pleased with himself."""

    clip = "eat"

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        if ctx.food is not None:
            ctx.body.face_towards(ctx.food.x)
        self.next_seed = 0.24  # the first peck lands this far into the clip
        self.to_eat = SEEDS_PER_STACK

    def go_eat(self, ctx: Context) -> State | None:
        return None

    def ask_for_food(self, ctx: Context) -> State | None:
        return None

    def step(self, ctx: Context, dt: float) -> State | None:
        food = ctx.food
        if food is None:
            return Idle()
        self.next_seed -= dt
        if self.next_seed > 0:
            return None
        self.next_seed += SECONDS_PER_SEED
        if food.pile.take_seed():
            self.to_eat -= 1
            ctx.hunger.ate_seed(ctx)
        if self.to_eat > 0 and food.pile.seeds > 0 and not ctx.hunger.full:
            return None
        ctx.hunger.fed()
        ctx.say(ctx.phrase("fed"), 1.8, mood="love")
        ctx.play("trill")
        return Shake()


BATH_STAND = DISH_WIDTH / 2 + 7
"""Art px from the middle of his bath to where he stands to hop in."""


def go_to_bath(ctx: Context) -> State:
    """Head for his bath: walk if it's near (or he's damp), fly if it's far or
    he's up high. He stops beside it, on the side he comes from, to hop in."""
    dish, cfg, body, area = ctx.bath.dish, ctx.config, ctx.body, ctx.area()
    assert dish is not None
    side = -1 if body.x > dish.x else 1
    spot = area.clamp_x(dish.x - side * cfg.px(BATH_STAND), ctx.margin)
    on_ground = body.y >= area.bottom - 1
    if on_ground and (abs(spot - body.x) <= cfg.px(160) or not can_fly(ctx)):
        return Walk(spot, then="bathe")
    return Fly(
        [*_takeoff(ctx, towards=spot), *_landing(ctx, spot, coming_from=body.x)], onto="bath"
    )


class Bathe(State):
    """His bath: he hops in, dips his head, splashes with flicking wings (water
    flying), dips and splashes again, hops out the far side, and shakes himself
    dry in a spray of droplets. Then he's damp for a while, and preens."""

    clip = "bath_hop"
    grounded = False  # hopping in and out
    effort = 1.4
    hop_seconds: ClassVar[float] = 0.45
    hop_height: ClassVar[float] = 9.0
    """Art px he rises hopping in or out."""
    PLAN: ClassVar[tuple[tuple[str, float], ...]] = (
        ("in", hop_seconds),
        ("dip", 2.3),
        ("splash", 2.6),
        ("dip", 1.2),
        ("splash", 1.8),
        ("out", hop_seconds),
        ("shake", 1.3),
    )
    drops_every: ClassVar[float] = 0.12

    def __init__(self) -> None:
        super().__init__()
        self.step_index = -1
        self.step_left = 0.0
        self.drops_in = 0.0
        self.start_x = 0.0
        self.end_x = 0.0

    @property
    def holds_bath(self) -> bool:
        return True

    @property
    def doing(self) -> str:
        return self.PLAN[self.step_index][0]

    def enter(self, ctx: Context) -> None:
        dish = ctx.bath.dish
        if dish is not None:
            ctx.body.face_towards(dish.x)
        self._next(ctx)

    def clicked(self, ctx: Context) -> State | None:
        return None  # busy

    def double_clicked(self, ctx: Context) -> State | None:
        return None

    def petted(self, ctx: Context) -> State | None:
        return None

    def go_eat(self, ctx: Context) -> State | None:
        return None

    def ask_for_food(self, ctx: Context) -> State | None:
        return None

    def _next(self, ctx: Context) -> None:
        self.step_index += 1
        if self.step_index >= len(self.PLAN):
            return
        what, self.step_left = self.PLAN[self.step_index]
        body, cfg, dish = ctx.body, ctx.config, ctx.bath.dish
        if what in ("in", "out"):
            self.start_x = body.x
            if what == "in" and dish is not None:
                self.end_x = dish.x
            else:
                self.end_x = ctx.area().clamp_x(
                    body.x + int(body.facing) * cfg.px(BATH_STAND), ctx.margin
                )
            ctx.animator.play("bath_hop", restart=True)
        elif what == "dip":
            ctx.animator.play("bath_dip", restart=True)
        elif what == "splash":
            ctx.animator.play("bath_splash", restart=True)
            self.drops_in = 0.0
        elif what == "shake":
            ctx.animator.play("shake", restart=True)
            area = ctx.area()
            ctx.effects.splash(body.x, body.y - cfg.px(14), area.bottom, ctx.rng, cfg.scale, 12)
        if what == "out":
            ctx.damp = cfg.damp_seconds
            if dish is not None:
                dish.used = True

    def step(self, ctx: Context, dt: float) -> State | None:
        body, cfg, area = ctx.body, ctx.config, ctx.area()
        ground = area.bottom
        dish = ctx.bath.dish
        if dish is None and self.doing not in ("out", "shake"):
            body.y = ground  # it's gone from under him
            return Shake()
        self.step_left -= dt
        what = self.doing
        if what in ("in", "out"):
            t = min(1.0, 1.0 - self.step_left / self.hop_seconds)
            body.x = self.start_x + (self.end_x - self.start_x) * t
            body.y = ground - cfg.px(self.hop_height) * math.sin(math.pi * t)
        elif what == "splash":
            assert dish is not None
            dish.splash = 0.3
            self.drops_in -= dt
            if self.drops_in <= 0:
                self.drops_in += self.drops_every
                front = body.x + int(body.facing) * cfg.px(ctx.rng.uniform(-6, 10))
                ctx.effects.splash(front, ground - cfg.px(6), ground, ctx.rng, cfg.scale, 2)
        else:
            body.y = ground
        if self.step_left > 0:
            return None
        if what == "shake":
            ctx.say(ctx.phrase("bathed"), 2.0)
            ctx.play("trill")
            return Preen()
        self._next(ctx)
        return None


# --- Toys -----------------------------------------------------------------------

MIRROR_STAND_OFF = 15
"""Art px from his mirror to where he stands to chat to it."""
BELL_REACH = 16
"""Art px from the bell he may be, on the branch, and still peck it."""


def bell_in_reach(ctx: Context, where: str) -> bool:
    """His bell's hanging ``where`` (``"branch"`` or ``"cage"``), he can reach it,
    and he's in the mood for a game."""
    bell = ctx.toys.bell
    if bell is None or bell.where != where or not ctx.toys.ready():
        return False
    return where == "cage" or abs(bell.x - ctx.body.x) <= ctx.config.px(BELL_REACH)


def _ring_bell(ctx: Context, into: float, dt: float) -> None:
    """Pecking his bell, ``into`` seconds into it: each peck swings and rings it."""
    bell = ctx.toys.bell
    if bell is None:
        return
    for peck in RING_PECKS:
        if into - dt < peck <= into:
            bell.strike(1 if bell.x >= ctx.body.x else -1)
            ctx.play("ting")


def mirror_is_inviting(ctx: Context) -> bool:
    mirror = ctx.toys.mirror
    return (
        mirror is not None
        and mirror.where == "ground"
        and ctx.toys.ready()
        and ctx.world.area_at(mirror.x, mirror.y - 1) == ctx.area()
    )


def go_to_mirror(ctx: Context) -> State:
    """Over to his mirror, to stand beside it facing it: walk if it's near (or
    he's damp), fly if not."""
    mirror, cfg, body, area = ctx.toys.mirror, ctx.config, ctx.body, ctx.area()
    assert mirror is not None
    side = -1 if body.x > mirror.x else 1
    spot = area.clamp_x(mirror.x - side * cfg.px(MIRROR_STAND_OFF), ctx.margin)
    on_ground = body.y >= area.bottom - 1
    if on_ground and (abs(spot - body.x) <= cfg.px(160) or not can_fly(ctx)):
        return Walk(spot, then="mirror")
    return Fly(
        [*_takeoff(ctx, towards=spot), *_landing(ctx, spot, coming_from=body.x)], onto="mirror"
    )


class PlayMirror(State):
    """Chatting to his reflection: bobbing at it, crest up, a little song."""

    clip = "mirror_chat"
    effort = 1.5
    chat_at: ClassVar[float] = 1.4

    @property
    def at_mirror(self) -> bool:
        return True

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        if ctx.toys.mirror is not None:
            ctx.body.face_towards(ctx.toys.mirror.x)

    def typing(self, ctx: Context) -> State | None:
        return None

    def step(self, ctx: Context, dt: float) -> State | None:
        if ctx.toys.mirror is None:
            return Idle()  # put away
        if self.elapsed - dt < self.chat_at <= self.elapsed:
            ctx.say(ctx.phrase("toy"), 1.8)
            ctx.play(whistle_for(ctx.rng.randrange(6)))
        if ctx.animator.finished:
            ctx.toys.played(ctx)
            return Idle()
        return None


def go_ask(ctx: Context) -> State:
    """Hungry with nothing to eat: he comes over to where your pointer is, lands
    below it and asks. If it's on another screen, he asks from where he is."""
    cfg, body, area = ctx.config, ctx.body, ctx.area()
    cx, cy = ctx.world.cursor()
    if ctx.world.area_at(cx, cy) != area:
        return Ask()
    x = area.clamp_x(cx, ctx.margin)
    on_ground = body.y >= area.bottom - 1
    if on_ground and (abs(x - body.x) <= cfg.px(100) or not can_fly(ctx)):
        return Walk(x, then="ask") if abs(x - body.x) > 1 else Ask()
    return Fly([*_takeoff(ctx, towards=x), *_landing(ctx, x, coming_from=body.x)], onto="ask")


class Ask(State):
    """Looking up at you, crest up, calling for seeds. Feed him and he goes
    straight to them; ignored for a while, he gives up and asks again later."""

    clip = "front_ask"
    gives_up_after: ClassVar[float] = 40.0

    def enter(self, ctx: Context) -> None:
        super().enter(ctx)
        self._call_out(ctx)  # the moment he's in front of you

    def ask_for_food(self, ctx: Context) -> State | None:
        return None

    def step(self, ctx: Context, dt: float) -> State | None:
        if not ctx.hunger.hungry:
            return Idle()
        if self.elapsed >= self.gives_up_after:
            ctx.hunger.asked(ctx)  # he'll try you again in a while
            return Idle()
        self.next_line -= dt
        if self.next_line <= 0:
            self._call_out(ctx)
        return None

    def _call_out(self, ctx: Context) -> None:
        ctx.say(ctx.phrase("hungry"), ctx.config.complaint_seconds)
        ctx.play("ask")
        self.next_line = ctx.rng.uniform(*ctx.config.complaint_every)


class Bob(State):
    """Bobbing his head along while you type: side-on, or facing you if that's how
    he was sitting. When the typing stops, he goes back to sitting about."""

    clip = "bob"

    def __init__(self, *, facing_you: bool = False) -> None:
        super().__init__()
        self.facing_you = facing_you

    def enter(self, ctx: Context) -> None:
        ctx.animator.play("front_bob" if self.facing_you else "bob", restart=True)

    def typing(self, ctx: Context) -> State | None:
        return None

    def step(self, ctx: Context, dt: float) -> State | None:
        if ctx.typing.active:
            return None
        return FrontIdle() if self.facing_you else Idle()


OFF_SCREEN = 60.0
"""Art px past the screen's edge where he waits, out of sight, while away."""


class Away(State):
    """Out of sight, off the side of the screen (hidden from the tray), until he's
    asked back. His needs go on as if he were resting; nothing reaches him."""

    clip = "glide"
    effort = 0.5
    grounded = False

    def __init__(self, side: int = 1, area: Area | None = None) -> None:
        super().__init__()
        self.side, self.area = side, area

    def go_eat(self, ctx: Context) -> State | None:
        return None

    def ask_for_food(self, ctx: Context) -> State | None:
        return None


class Listen(State):
    """A lesson: head cocked, listening to the word you've typed, then his try
    at it in a cloud, beak working."""

    clip = "listen"
    listen_for: ClassVar[float] = 1.4
    say_for: ClassVar[float] = 2.2

    def __init__(self, said: str, learned: bool) -> None:
        super().__init__()
        self.said, self.learned, self.trying = said, learned, False

    def clicked(self, ctx: Context) -> State | None:
        return None  # listening

    def typing(self, ctx: Context) -> State | None:
        return None

    def step(self, ctx: Context, dt: float) -> State | None:
        if not self.trying and self.elapsed >= self.listen_for:
            self.trying = True
            ctx.animator.play("talk", restart=True)
            ctx.say(self.said, self.say_for, mood="love" if self.learned else "plain")
            ctx.play("trill" if self.learned else "chirp_c")
        if self.trying and self.elapsed >= self.listen_for + self.say_for:
            return Idle()
        return None
