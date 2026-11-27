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

    def ledges(self) -> list[Ledge]:
        """Visible tops of other windows that aren't maximized or minimized."""
        ...

    def input_idle_seconds(self) -> float | None:
        """Seconds since any keyboard or mouse input at all, or None if unknown."""
        ...

    def local_hour(self) -> int: ...


@dataclass(frozen=True)
class Window:
    """Another application's window, as the desktop reports it."""

    id: int
    left: float
    top: float
    right: float
    bottom: float


@dataclass(frozen=True)
class Ledge:
    """A stretch of a window's top edge that's in view: somewhere to perch."""

    window: int
    left: float
    right: float
    y: float
    """Screen y of the top edge: his feet rest on it."""
    window_left: float
    """Where that window's left edge is, so he can ride along when it moves."""


def visible_ledges(windows: list[Window], min_width: float = 1.0) -> list[Ledge]:
    """The parts of each window's top edge not hidden by a window above it.

    ``windows`` runs from the front-most down. A window above hides the part of
    a lower window's top edge that it lies across.
    """
    ledges: list[Ledge] = []
    for i, window in enumerate(windows):
        spans = [(window.left, window.right)]
        for above in windows[:i]:
            if not above.top <= window.top < above.bottom:
                continue
            spans = [
                piece
                for lo, hi in spans
                for piece in ((lo, min(hi, above.left)), (max(lo, above.right), hi))
                if piece[1] - piece[0] > 0
            ]
        ledges.extend(
            Ledge(window.id, lo, hi, window.top, window.left)
            for lo, hi in spans
            if hi - lo >= min_width
        )
    return ledges
