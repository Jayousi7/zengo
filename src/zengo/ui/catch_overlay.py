"""The dimmed screen you drag a box on to catch Zengo."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPen, QScreen
from PySide6.QtWidgets import QWidget


class CatchOverlay(QWidget):
    """Covers one screen. Drag a box with either button; Esc or a plain click cancels.

    It takes the drag itself, so nothing underneath reacts to it.
    """

    selected = Signal(QRect)
    """The box, in screen coordinates."""
    cancelled = Signal()

    def __init__(self, screen: QScreen) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Catch Zengo")
        self.setGeometry(screen.geometry())
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._start: QPoint | None = None
        self._end: QPoint | None = None

    def start(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def _box(self) -> QRect | None:
        if self._start is None or self._end is None:
            return None
        return QRect(self._start, self._end).normalized()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(16, 20, 28, 90))
        p.setPen(QColor(255, 255, 255, 220))
        p.drawText(
            self.rect().adjusted(0, 24, 0, 0),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            "Drag a box around Zengo to catch him   ·   Esc to cancel",
        )
        box = self._box()
        if box is not None:
            p.fillRect(box, QColor(255, 255, 255, 40))
            pen = QPen(QColor("white"), 2, Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.drawRect(box)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            self._start = self._end = event.position().toPoint()
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._start is not None:
            self._end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        box = self._box()
        if box is None:
            return
        if box.width() < 6 or box.height() < 6:
            self.cancelled.emit()
        else:
            self.selected.emit(box.translated(self.geometry().topLeft()))
        self.close()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()

    def contextMenuEvent(self, event) -> None:  # a right-drag must not open a menu
        event.accept()
