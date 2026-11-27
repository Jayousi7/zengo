"""Qt implementation of :class:`zengo.world.World`."""

from __future__ import annotations

import time
from datetime import datetime

from PySide6.QtCore import QPoint
from PySide6.QtGui import QCursor, QGuiApplication

from zengo.ui.input_idle import InputIdle
from zengo.world import Area


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

    def input_idle_seconds(self) -> float | None:
        return self._input.seconds()

    def local_hour(self) -> int:
        return datetime.now().hour
