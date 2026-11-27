"""The window the seed pile is drawn in."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPainter, QPaintEvent, QPixmap
from PySide6.QtWidgets import QWidget

from zengo.behavior.food import Pile
from zengo.config import Config
from zengo.sprites.food import MAX_SEEDS, PILE_HEIGHT, PILE_WIDTH, build_pile
from zengo.ui.layering import bypass_window_manager
from zengo.ui.sprites import frame_to_image


class FoodWindow(QWidget):
    """A pile of sunflower seeds: filling as stacks pour on, shrinking as he eats.
    Used for the pile on the ground and the dish in the cage. Clicks pass through."""

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
        self.setWindowTitle("Zengo's seeds")
        self._config = config
        self._piles = [
            QPixmap.fromImage(frame_to_image(build_pile(n), config.scale))
            for n in range(MAX_SEEDS + 1)
        ]
        self._seeds = 0
        self.resize(self._piles[0].size())

    def show_pile(self, pile: Pile | None, x: float = 0.0, y: float = 0.0) -> bool:
        """Draw ``pile`` centred on ``x``, resting on ``y``. Returns True when it has
        just appeared."""
        seeds = 0 if pile is None else round(pile.shown)
        if seeds <= 0:
            self.hide()
            return False
        px = self._config.px
        # The pile's bottom row of seeds rests on what it's put on.
        left = round(x - px((PILE_WIDTH + 2) / 2))
        top = round(y - px(PILE_HEIGHT + 1))
        if seeds != self._seeds:
            self._seeds = seeds
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
