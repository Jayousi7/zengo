"""Noticing that you're typing, to bob his head along.

There's input (keys, or clicks) but the pointer is still: that's typing. Only
the timing of input is known, never which keys; see ``ui/input_idle.py``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zengo.behavior.context import Context


@dataclass
class TypingSensor:
    recent: float = 0.35
    """Input this recent counts as a key going down now."""
    still_pointer: float = 0.6
    """The pointer has rested at least this long: the input isn't the mouse."""
    grace: float = 1.0
    """Seconds a pause between bursts still counts as typing."""

    active: bool = False
    _since: float = math.inf

    def update(self, ctx: Context, dt: float) -> None:
        idle = ctx.world.input_idle_seconds()
        typing_now = (
            idle is not None
            and idle < self.recent
            and ctx.world.user_idle_seconds() >= self.still_pointer
        )
        self._since = 0.0 if typing_now else self._since + dt
        self.active = self._since <= self.grace
