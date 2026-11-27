"""Zengo's head in the system tray, so he's easy to find.

Click it and he flies to the middle of your screen. Its menu shows or hides him,
feeds him, opens the settings or quits. A small dot on the icon says he needs
you: hungry, or caged and wanting out. Where the desktop has no tray it's simply
not there (and appears later if a tray does, as when he starts before the panel).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from PySide6.QtCore import QObject, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from zengo.sprites.compose import Frame
from zengo.sprites.frames import PADDING
from zengo.ui.sprites import frame_to_image

HEAD = QRect(28 + PADDING, PADDING - 1, 18, 18)
"""Art pixels of his head and crest in the perched frame."""

BADGE = QColor("#e07a5f")
RING = {"focus": QColor("#9db7d8"), "break": QColor("#8dbb74")}
RING_STEPS = 24
"""The ring round the icon shows the time left in this many steps."""


def head_icon(
    frame: Frame, size: int = 64, badge: bool = False, ring: tuple[str, float] | None = None
) -> QPixmap:
    """His head, scaled up sharp, with a dot in the top corner if ``badge``, and
    a ring round it for a focus session or break: ``(phase, share left)``."""
    image = frame_to_image(frame, 1).copy(HEAD)
    sharp = Qt.TransformationMode.FastTransformation  # no smoothing: crisp pixels
    pixmap = QPixmap.fromImage(image.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, sharp))
    if badge:
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("#231c1f"))
        painter.setBrush(BADGE)
        dot = size * 0.32
        painter.drawEllipse(1, 1, round(dot), round(dot))  # top left, clear of his face
        painter.end()
    if ring is not None:
        phase, left = ring
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = size * 0.09
        box = QRectF(width / 2, width / 2, size - width, size - width)
        painter.setPen(QPen(QColor(35, 28, 31, 160), width))
        painter.drawEllipse(box)
        pen = QPen(RING.get(phase, RING["focus"]), width)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        # From the top, clockwise, as much as is left.
        painter.drawArc(box, 90 * 16, -round(360 * 16 * max(0.0, min(1.0, left))))
        painter.end()
    return pixmap


class Tray(QObject):
    """The tray icon and its menu. ``actions`` maps "summon", "show", "hide",
    "feed", "focus" (open the Focus settings), "pause" (or resume), "stop",
    "settings" and "quit" to what they do."""

    def __init__(
        self, frames: Mapping[str, Frame], actions: Mapping[str, Callable[[], None]], style: str
    ) -> None:
        super().__init__()
        self._perch = frames["perch"]
        self._icons: dict[tuple[bool, str, int], QIcon] = {}
        self._shown: tuple[bool, str, int] | None = None
        self._badge: bool | None = None
        self._icon = QSystemTrayIcon(self._icon_for((False, "off", 0)))
        self._icon.setToolTip("Zengo")
        self._menu = QMenu()
        self._menu.setStyleSheet(style)
        self._show_hide = self._menu.addAction("Hide Zengo")
        self._show_hide.triggered.connect(self._toggle)
        self._feed = self._menu.addAction("Feed Zengo", actions["feed"])
        self._focus = self._menu.addAction("Focus…", actions["focus"])
        self._pause = self._menu.addAction("Pause focus", actions["pause"])
        self._stop = self._menu.addAction("Stop focus", actions["stop"])
        self._menu.addAction("Settings…", actions["settings"])
        self._menu.addSeparator()
        self._menu.addAction("Quit Zengo", actions["quit"])
        self._icon.setContextMenu(self._menu)
        self._icon.activated.connect(self._activated)
        self._actions = actions
        self._away = False

    @staticmethod
    def available() -> bool:
        """Whether to make one at all. Started at login he may come up before the
        desktop's panel does, and Qt shows the icon once a tray appears, so it's
        made wherever there's a real screen (not for headless tests)."""
        return QGuiApplication.platformName() != "offscreen"

    def show(self) -> None:
        self._icon.show()

    def hide(self) -> None:
        self._icon.hide()

    def _icon_for(self, key: tuple[bool, str, int]) -> QIcon:
        if key not in self._icons:
            badge, phase, step = key
            ring = (phase, step / RING_STEPS) if phase in RING else None
            self._icons[key] = QIcon(head_icon(self._perch, badge=badge, ring=ring))
        return self._icons[key]

    def update(
        self,
        *,
        needs_you: bool,
        away: bool,
        can_hide: bool,
        can_feed: bool,
        focus: tuple[str, float, bool, str] = ("off", 0.0, False, ""),
    ) -> None:
        """Keep the icon and menu in step with him (cheap when nothing changed).
        ``focus``: the timer's phase, share of it left, whether it's paused, and
        what to say about it."""
        phase, left, paused, words = focus
        step = round(left * RING_STEPS) if phase in RING else 0
        key = (needs_you, phase, step)
        if key != self._shown:
            self._shown = key
            self._icon.setIcon(self._icon_for(key))
        tip = "Zengo needs you" if needs_you else "Zengo"
        tip = f"{tip}\n{words}" if words else tip
        if tip != self._icon.toolTip():
            self._icon.setToolTip(tip)
        running = phase in RING
        self._focus.setText(f"Focus: {words}" if words else "Focus…")
        self._pause.setVisible(running)
        self._pause.setText("Resume focus" if paused else "Pause focus")
        self._stop.setVisible(phase != "off")
        self._away = away
        self._show_hide.setText("Show Zengo" if away else "Hide Zengo")
        self._show_hide.setEnabled(away or can_hide)
        self._feed.setEnabled(can_feed)

    def _toggle(self) -> None:
        self._actions["show" if self._away else "hide"]()

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._actions["summon"]()
