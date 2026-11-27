"""Zengo's head in the system tray, so he's easy to find.

Click it and he flies to the middle of your screen. Its menu shows or hides him,
feeds him, opens the settings or quits. A small dot on the icon says he needs
you: hungry, or caged and wanting out. Where the desktop has no tray it's simply
not there (and appears later if a tray does, as when he starts before the panel).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from PySide6.QtCore import QObject, QRect, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from zengo.sprites.compose import Frame
from zengo.sprites.frames import PADDING
from zengo.ui.sprites import frame_to_image

HEAD = QRect(28 + PADDING, PADDING - 1, 18, 18)
"""Art pixels of his head and crest in the perched frame."""

BADGE = QColor("#e07a5f")


def head_icon(frame: Frame, size: int = 64, badge: bool = False) -> QPixmap:
    """His head, scaled up sharp, with a dot in the top corner if ``badge``."""
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
    return pixmap


class Tray(QObject):
    """The tray icon and its menu. ``actions`` maps "summon", "show", "hide",
    "feed", "settings" and "quit" to what they do."""

    def __init__(
        self, frames: Mapping[str, Frame], actions: Mapping[str, Callable[[], None]], style: str
    ) -> None:
        super().__init__()
        perch = frames["perch"]
        self._icons = {flag: QIcon(head_icon(perch, badge=flag)) for flag in (False, True)}
        self._badge: bool | None = None
        self._icon = QSystemTrayIcon(self._icons[False])
        self._icon.setToolTip("Zengo")
        self._menu = QMenu()
        self._menu.setStyleSheet(style)
        self._show_hide = self._menu.addAction("Hide Zengo")
        self._show_hide.triggered.connect(self._toggle)
        self._feed = self._menu.addAction("Feed Zengo", actions["feed"])
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

    def update(self, *, needs_you: bool, away: bool, can_hide: bool, can_feed: bool) -> None:
        """Keep the icon and menu in step with him (cheap when nothing changed)."""
        if needs_you != self._badge:
            self._badge = needs_you
            self._icon.setIcon(self._icons[needs_you])
            self._icon.setToolTip("Zengo needs you" if needs_you else "Zengo")
        self._away = away
        self._show_hide.setText("Show Zengo" if away else "Hide Zengo")
        self._show_hide.setEnabled(away or can_hide)
        self._feed.setEnabled(can_feed)

    def _toggle(self) -> None:
        self._actions["show" if self._away else "hide"]()

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._actions["summon"]()
