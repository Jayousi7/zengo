"""A window for one feather he's dropped: click it to clear it away."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPaintEvent, QPixmap
from PySide6.QtWidgets import QWidget

from zengo.behavior.moult import Feather
from zengo.sprites.feather import build_feathers
from zengo.ui.sprites import frame_to_image


class FeatherWindow(QWidget):
    """Shows one feather, falling or lying where it landed. Unlike his other
    little windows it takes clicks: one click and it's gone."""

    clicked = Signal()

    def __init__(self, scale: int) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("A feather")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("One of Zengo's feathers. Click to clear it away.")
        self._pictures = {
            key: QPixmap.fromImage(frame_to_image(frame, scale))
            for key, frame in build_feathers().items()
        }
        self._drawn: tuple[QPixmap, float] | None = None
        self.resize(next(iter(self._pictures.values())).size())

    def show_feather(self, feather: Feather | None) -> None:
        if feather is None:
            self._drawn = None
            self.hide()
            return
        picture = self._pictures[feather.tilt, feather.white]
        at = QPoint(round(feather.x) - picture.width() // 2, round(feather.y) - picture.height())
        drawn = (picture, round(feather.alpha, 2))
        if drawn != self._drawn:
            self._drawn = drawn
            self.update()
        if self.pos() != at:
            self.move(at)
        if not self.isVisible():
            self.show()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def paintEvent(self, event: QPaintEvent) -> None:
        if self._drawn is not None:
            picture, alpha = self._drawn
            painter = QPainter(self)
            painter.setOpacity(alpha)
            painter.drawPixmap(0, 0, picture)
