"""Qt implementation of :class:`zengo.world.World`."""

from __future__ import annotations

import time
from datetime import datetime

from PySide6.QtCore import QPoint, QTimeZone
from PySide6.QtGui import QCursor, QGuiApplication

from zengo.ui.desktop_windows import windows_reader
from zengo.ui.input_idle import InputIdle
from zengo.world import Area, Ledge, Window, visible_ledges

LEDGES_EVERY = 0.25
"""Seconds between looks at where the other windows are."""


def time_zone() -> str:
    """The computer's time zone, as an IANA name (``Europe/Berlin``) where the
    system gives one; Qt translates Windows' own names."""
    return bytes(QTimeZone.systemTimeZoneId().data()).decode(errors="replace")


class QtWorld:
    """Reads screen geometry and the global cursor.

    User activity is inferred from cursor movement, sampled once per frame. That
    is portable (no OS input hooks or extra permissions) and good enough to tell
    whether someone is at the desk.
    """

    def __init__(self) -> None:
        self._last_cursor = QCursor.pos()
        self._last_activity = time.monotonic()
        self._input = InputIdle()
        self._read_windows = windows_reader()
        self._ledges: list[Ledge] = []
        self._ledges_read = -LEDGES_EVERY

    def sample(self) -> None:
        position = QCursor.pos()
        if position != self._last_cursor:
            self._last_cursor = position
            self._last_activity = time.monotonic()

    def area_at(self, x: float, y: float) -> Area:
        screen = QGuiApplication.screenAt(QPoint(round(x), round(y)))
        geometry = (screen or QGuiApplication.primaryScreen()).availableGeometry()
        # QRect.right()/bottom() are inclusive; Area edges are exclusive.
        return Area(geometry.left(), geometry.top(), geometry.right() + 1, geometry.bottom() + 1)

    def cursor(self) -> tuple[float, float]:
        position = QCursor.pos()
        return float(position.x()), float(position.y())

    def user_idle_seconds(self) -> float:
        return time.monotonic() - self._last_activity

    def ledges(self) -> list[Ledge]:
        """Visible tops of other windows, re-read a few times a second (asking the
        window manager every frame would be wasteful)."""
        now = time.monotonic()
        if now - self._ledges_read >= LEDGES_EVERY:
            self._ledges_read = now
            self._ledges = visible_ledges(self._read_windows())
        return self._ledges

    def window_frame(self, window: int) -> Window | None:
        """One window's rectangle, read now: cheap enough to do every frame for the
        window he's riding on, so he moves with it smoothly."""
        read = getattr(self._read_windows, "frame", None)
        try:
            rect = None if read is None else read(window)
        except OSError:
            return None
        return None if rect is None else Window(window, *rect)

    def input_idle_seconds(self) -> float | None:
        return self._input.seconds()

    def local_hour(self) -> int:
        return datetime.now().hour
