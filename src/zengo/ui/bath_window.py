"""The window his bath dish is drawn in."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPainter, QPaintEvent, QPixmap
from PySide6.QtWidgets import QWidget

from zengo.behavior.bath import Dish
from zengo.config import Config
from zengo.sprites.bath import DISH_HEIGHT, DISH_WIDTH, RIPPLES, build_dish
from zengo.ui.layering import bypass_window_manager
from zengo.ui.sprites import frame_to_image

RIPPLE_SECONDS = 0.5
"""How long each ripple pattern shows; splashing, the water's thrown about."""


class BathWindow(QWidget):
    """The dish, fading in and out, its water rippling. In front of him, so
    standing in it the rim hides his feet. Clicks pass through."""

    def __init__(self, config: Config, in_front_of: QWidget | None = None) -> None:
        super().__init__(
            in_front_of,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput,
        )
        if in_front_of is not None:
            bypass_window_manager(self)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Zengo's bath")
        self._config = config
        picture = lambda *a: QPixmap.fromImage(frame_to_image(build_dish(*a), config.scale))  # noqa: E731
        self._ripples = [picture(i) for i in range(RIPPLES)]
        self._splash = picture(0, True)
        self._drawn: tuple[QPixmap, float] | None = None
        self.resize(self._splash.size())

    def show_dish(self, dish: Dish | None, clock: float) -> None:
        """Draw ``dish`` (or nothing), its ripples going by ``clock`` (seconds)."""
        if dish is None or dish.shown <= 0:
            self._drawn = None
            self.hide()
            return
        px = self._config.px
        picture = (
            self._splash
            if dish.splash > 0
            else self._ripples[int(clock / RIPPLE_SECONDS) % RIPPLES]
        )
        left = round(dish.x - px((DISH_WIDTH + 2) / 2))
        top = round(dish.y - px(DISH_HEIGHT + 1))
        drawn = (picture, round(dish.shown, 2))
        if drawn != self._drawn:
            self._drawn = drawn
            self.update()
        if self.pos() != QPoint(left, top):
            self.move(left, top)
        if not self.isVisible():
            self.show()

    def paintEvent(self, event: QPaintEvent) -> None:
        if self._drawn is not None:
            picture, shown = self._drawn
            painter = QPainter(self)
            painter.setOpacity(shown)
            painter.drawPixmap(0, 0, picture)
