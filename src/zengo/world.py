"""What the pet can observe about the desktop.

Behaviour code depends only on the :class:`World` protocol, never on Qt, so it
can be driven by a fake in tests. The Qt implementation lives in
:mod:`zengo.ui.qt_world`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Area:
    """A screen's usable area in screen pixels, excluding panels and taskbars."""

    left: float
    top: float
    right: float
    bottom: float

    def clamp_x(self, x: float, margin: float = 0.0) -> float:
        return min(max(x, self.left + margin), self.right - margin)


class World(Protocol):
    def area_at(self, x: float, y: float) -> Area:
        """Usable area of the screen containing ``(x, y)``, or the primary screen."""
        ...

    def cursor(self) -> tuple[float, float]: ...

    def user_idle_seconds(self) -> float:
        """Seconds since the user last moved the mouse anywhere on the desktop."""
        ...

    def input_idle_seconds(self) -> float | None:
        """Seconds since any keyboard or mouse input at all, or None if unknown."""
        ...

    def local_hour(self) -> int: ...
