"""The "▶ Start" button by his head when a break's over and he's asking if
you're ready for the next focus session. The cloud above him can't be clicked
(clicks pass through it), so the button is a little window of its own."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QFont, QFontMetrics, QMouseEvent, QPainter, QPaintEvent, QPixmap
from PySide6.QtWidgets import QWidget

from zengo.ui.bubble_window import INK, PAPER

LABEL = "▶ Start"


class StartButton(QWidget):
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
        self.setWindowTitle("Start the next focus session")
        self.setToolTip("Start the next focus session")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._scale = scale
        self._pixmap = self._draw()
        self.resize(self._pixmap.size())

    def _draw(self) -> QPixmap:
        s = self._scale
        font = QFont()
        font.setPixelSize(7 * s)
        font.setBold(True)
        metrics = QFontMetrics(font)
        w = metrics.horizontalAdvance(LABEL) + 8 * s
        h = metrics.height() + 4 * s
        w += -w % s
        h += -h % s
        pixmap = QPixmap(w, h)
        pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(pixmap)
        # The cloud's look: an outlined box with its corners cut, ink on paper reversed.
        p.fillRect(s, 0, w - 2 * s, h, INK)
        p.fillRect(0, s, w, h - 2 * s, INK)
        p.fillRect(2 * s, s, w - 4 * s, h - 2 * s, PAPER)
        p.fillRect(s, 2 * s, w - 2 * s, h - 4 * s, PAPER)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setFont(font)
        p.setPen(INK)
        p.drawText(QRect(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, LABEL)
        p.end()
        return pixmap

    def show_beside(self, head: QPoint | None, side: int, screen: QRect) -> None:
        """By ``head`` on its ``side`` (-1 left, 1 right), kept on ``screen``; or
        hidden with ``None``."""
        if head is None:
            self.hide()
            return
        w, h = self.width(), self.height()
        left = head.x() if side > 0 else head.x() - w
        left = min(max(left, screen.left()), screen.right() - w)
        top = min(max(head.y() - h // 2, screen.top()), screen.bottom() - h)
        if self.pos() != QPoint(left, top):
            self.move(left, top)
        if not self.isVisible():
            self.show()
            self.raise_()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def paintEvent(self, event: QPaintEvent) -> None:
        QPainter(self).drawPixmap(0, 0, self._pixmap)
