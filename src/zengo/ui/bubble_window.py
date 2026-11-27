"""The speech cloud that pops up above Zengo's head."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPaintEvent, QPixmap
from PySide6.QtWidgets import QWidget

from zengo.ui.layering import bypass_window_manager

INK = QColor("#3a2a30")
PAPER = QColor("#fcf7ef")
HEART = QColor("#d9576b")
ANGRY = QColor("#b8433a")
MOOD_INK = {"love": HEART, "angry": ANGRY}


class BubbleWindow(QWidget):
    """A pixel-art cloud with a tail pointing down at his head.

    The outline is drawn in whole art pixels to match him; the words are set in
    an ordinary font so they stay readable. Clicks pass straight through.
    """

    def __init__(self, scale: int, in_front_of: QWidget | None = None) -> None:
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
        self.setWindowTitle("Zengo says")
        self._scale = scale
        self._said: tuple[str, str] | None = None
        self._pixmap = QPixmap()
        self._tail_x = 0

    def say(
        self,
        text: str | None,
        head: QPoint,
        screen: QRect,
        mood: str = "plain",
        keep_clear: QRect | None = None,
    ) -> None:
        """Show ``text`` with the tail's tip just above ``head``, kept on ``screen``.

        If that would cover ``keep_clear`` (a hung cage and its chain), the cloud
        goes beside it instead, level with ``head``, on whichever side has room.
        """
        if text is None:
            self._said = None
            self.hide()
            return
        if (text, mood) != self._said:
            self._said = (text, mood)
            self._pixmap = self._draw(text, mood)
            self.resize(self._pixmap.size())
            self.update()
        w, h = self._pixmap.width(), self._pixmap.height()
        left = min(max(head.x() - self._tail_x, screen.left()), screen.right() - w)
        top = max(head.y() - h, screen.top())
        if keep_clear is not None and QRect(left, top, w, h).intersects(keep_clear):
            gap = 2 * self._scale
            room_right = screen.right() - keep_clear.right()
            left = (
                keep_clear.right() + gap if room_right >= w + gap else keep_clear.left() - gap - w
            )
            top = min(max(head.y() - h // 2, screen.top()), screen.bottom() - h)
        if self.pos() != QPoint(left, top):
            self.move(left, top)
        if not self.isVisible():
            self.show()
        self.raise_()

    def _draw(self, text: str, mood: str) -> QPixmap:
        s = self._scale
        font = QFont()
        font.setPixelSize(7 * s)
        font.setBold(True)
        metrics = QFontMetrics(font)
        pad_x, pad_y, tail = 4 * s, 3 * s, 3 * s
        box_w = metrics.horizontalAdvance(text) + 2 * pad_x
        box_h = metrics.height() + 2 * pad_y
        box_w += -box_w % s  # whole art pixels
        box_h += -box_h % s
        self._tail_x = 4 * s + s // 2

        pixmap = QPixmap(box_w, box_h + tail)
        pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(pixmap)
        # Body: an outlined box with its corners cut a pixel, for a rounded pixel-art look.
        p.fillRect(s, 0, box_w - 2 * s, box_h, INK)
        p.fillRect(0, s, box_w, box_h - 2 * s, INK)
        p.fillRect(2 * s, s, box_w - 4 * s, box_h - 2 * s, PAPER)
        p.fillRect(s, 2 * s, box_w - 2 * s, box_h - 4 * s, PAPER)
        # Tail: a stepped wedge down to the tip, over the outline's bottom edge.
        for row in range(3):
            width = (3 - row) * s
            x = self._tail_x - s - (width - 2 * s) // 2
            p.fillRect(x, box_h - s + row * s, width + 2 * s, s, INK)
            if row < 2:
                p.fillRect(x + s, box_h - s + row * s, width, s, PAPER)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setFont(font)
        p.setPen(MOOD_INK.get(mood, INK))
        p.drawText(QRect(0, 0, box_w, box_h), Qt.AlignmentFlag.AlignCenter, text)
        p.end()
        return pixmap

    def paintEvent(self, event: QPaintEvent) -> None:
        QPainter(self).drawPixmap(0, 0, self._pixmap)
