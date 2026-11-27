"""The focus timer: a stretch of focus, then a break, and round again.

You set the lengths (25 minutes' focus and a 5-minute break to begin with, a
longer break after every few sessions). A session is timed by the wall clock,
so it keeps going while he's suspended or closed: start him again and it's
where it would be. When a focus session ends, a break begins; when the break
ends, he either starts the next session himself or asks you first ("back to
it?"), as you chose. Pause and stop whenever you like.

The timer only keeps time and says when things happen (see :attr:`Focus.events`);
what he does about them is in the states.

Pure Python: no Qt.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

PHASES = ("off", "focus", "break", "waiting")
"""Not running; focusing; on a break; the break's over, waiting for you to start
the next session."""


@dataclass(frozen=True)
class Plan:
    """The lengths, in seconds, and what happens after a break."""

    focus: float = 25 * 60
    short_break: float = 5 * 60
    long_break: float = 15 * 60
    long_after: int = 4
    """A long break after this many focus sessions; 0 for never."""
    auto: bool = False
    """Start the next session without asking."""


@dataclass
class Focus:
    plan: Plan = field(default_factory=Plan)
    """The lengths for the next session. A session keeps the plan it started with."""
    phase: str = "off"
    long_break: bool = False
    ends_at: float | None = None
    """Wall-clock time (seconds since the epoch) the current phase ends."""
    paused_left: float | None = None
    """Paused: seconds that were left."""
    done: int = 0
    """Focus sessions finished since the last long break."""
    session: Plan = field(default_factory=Plan)
    suggested: bool = False
    """He suggested something (a bath, a game) at the last break: not this time."""
    events: list[str] = field(default_factory=list)
    """What's just happened, for the brain: ``"focus"`` (a session began),
    ``"break"`` (focus is over: break time), ``"back"`` (the break's over: back to
    it?), ``"stopped"``."""

    # --- Asking about it ----------------------------------------------------------

    @property
    def running(self) -> bool:
        return self.phase in ("focus", "break")

    @property
    def paused(self) -> bool:
        return self.paused_left is not None

    @property
    def focusing(self) -> bool:
        """In a focus session and not paused: he keeps quiet."""
        return self.phase == "focus" and not self.paused

    @property
    def on_break(self) -> bool:
        return self.phase == "break"

    def left(self, now: float) -> float:
        """Seconds left in the current phase."""
        if self.paused_left is not None:
            return self.paused_left
        if self.ends_at is None:
            return 0.0
        return max(0.0, self.ends_at - now)

    def length(self) -> float:
        """How long the current phase is in all."""
        if self.phase == "focus":
            return self.session.focus
        if self.phase == "break":
            return self.session.long_break if self.long_break else self.session.short_break
        return 0.0

    def fraction_left(self, now: float) -> float:
        length = self.length()
        return min(1.0, self.left(now) / length) if length else 0.0

    # --- Doing ----------------------------------------------------------------------

    def start(self, now: float) -> None:
        """Begin a focus session with the current plan (from anywhere: off, a
        break, or waiting for you)."""
        self.session = replace(self.plan)
        self.phase, self.long_break, self.paused_left = "focus", False, None
        self.ends_at = now + self.session.focus
        self.events.append("focus")

    def pause(self, now: float) -> None:
        if self.running and not self.paused:
            self.paused_left = self.left(now)

    def resume(self, now: float) -> None:
        if self.running and self.paused_left is not None:
            self.ends_at, self.paused_left = now + self.paused_left, None

    def stop(self) -> None:
        if self.phase != "off":
            self.events.append("stopped")
        self.phase, self.ends_at, self.paused_left, self.long_break = "off", None, None, False
        self.done = 0

    def update(self, now: float) -> None:
        """Move on to the next phase when this one's over."""
        if not self.running or self.paused or self.ends_at is None or now < self.ends_at:
            return
        if self.phase == "focus":
            self._to_break(self.ends_at)
            self.events.append("break")
        elif self.session.auto:
            ended = self.ends_at
            self.start(ended)  # straight into the next one
        else:
            self.phase, self.ends_at = "waiting", None
            self.events.append("back")

    def catch_up(self, now: float) -> None:
        """Started again after being closed: put the session where it would be,
        without the fuss (no events). A focus session that ended meanwhile goes
        to its break; a break that ended goes to waiting for you, even if the
        next session would have started by itself: you weren't here."""
        if not self.running or self.paused or self.ends_at is None or now < self.ends_at:
            return
        if self.phase == "focus":
            self._to_break(self.ends_at)
        if self.ends_at is not None and now >= self.ends_at:
            self.phase, self.ends_at = "waiting", None

    def _to_break(self, focus_ended: float) -> None:
        self.done += 1
        every = self.session.long_after
        self.long_break = bool(every) and self.done >= every
        if self.long_break:
            self.done = 0
        self.phase = "break"
        length = self.session.long_break if self.long_break else self.session.short_break
        self.ends_at = focus_ended + length

    def take_events(self) -> list[str]:
        events, self.events = self.events, []
        return events
