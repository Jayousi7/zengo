"""The window the seed pile is drawn in."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPainter, QPaintEvent, QPixmap
from PySide6.QtWidgets import QWidget

from zengo.behavior.food import Food
from zengo.config import Config
from zengo.sprites.food import MAX_SEEDS, PILE_HEIGHT, PILE_WIDTH, build_pile
from zengo.ui.sprites import frame_to_image


class FoodWindow(QWidget):
    """A little pile of sunflower seeds, shrinking as he eats. Clicks pass through."""

    def __init__(self, config: Config) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Zengo's seeds")
        self._config = config
        self._piles = [
            QPixmap.fromImage(frame_to_image(build_pile(n), config.scale))
            for n in range(MAX_SEEDS + 1)
        ]
        self._seeds = 0
        self.resize(self._piles[0].size())

    def show_food(self, food: Food | None) -> bool:
        """Draw ``food``. Returns True when it has just appeared."""
        if food is None or food.seeds <= 0:
            self.hide()
            return False
        px = self._config.px
        # The pile's bottom row of seeds rests on what it's put on.
        left = round(food.x - px((PILE_WIDTH + 2) / 2))
        top = round(food.y - px(PILE_HEIGHT + 1))
        if food.seeds != self._seeds:
            self._seeds = food.seeds
            self.update()
        if self.pos() != QPoint(left, top):
            self.move(left, top)
        if self.isVisible():
            return False
        self.show()
        self.raise_()
        return True

    def paintEvent(self, event: QPaintEvent) -> None:
        QPainter(self).drawPixmap(0, 0, self._piles[min(self._seeds, MAX_SEEDS)])
