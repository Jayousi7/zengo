"""Break reminders, for when you're not using the focus timer.

After a long stretch at the computer (50 minutes to begin with, or as you set
it, or off), he comes over to your pointer and suggests a break: a stretch, a
glass of water. Ignore him and he asks once more ten minutes later, then lets
it go. Getting up for five minutes or more counts as a break and starts the
count again. Never during a focus session.

"At the computer" goes by the time since any input, where the system says
(keys too, never which); elsewhere by the pointer moving.

Pure Python: no Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zengo.behavior.context import Context

A_BREAK = 300.0
"""Seconds without input that count as having taken a break."""
ASK_AGAIN = 600.0
"""Seconds after the first nudge before the second (and last)."""


@dataclass
class Reminders:
    minutes: int = 50
    """Your setting: a nudge after this long at it; 0 is off."""
    at_it: float = 0.0
    """Seconds at the computer since your last break."""
    nudges: int = 0
    """Nudges so far this stretch: one, then one more, then he lets it go."""

    def update(self, ctx: Context, dt: float) -> bool:
        """Count time at the computer; True when it's time for a nudge."""
        focus = ctx.focus
        if self.minutes <= 0 or focus.phase != "off":
            self.at_it, self.nudges = 0.0, 0  # the timer's looking after you
            return False
        idle = ctx.world.input_idle_seconds()
        if idle is None:
            idle = ctx.world.user_idle_seconds()
        if idle >= A_BREAK:
            self.at_it, self.nudges = 0.0, 0
            return False
        self.at_it += dt
        due = self.minutes * 60.0 + self.nudges * ASK_AGAIN
        if self.nudges < 2 and self.at_it >= due:
            self.nudges += 1
            return True
        return False
