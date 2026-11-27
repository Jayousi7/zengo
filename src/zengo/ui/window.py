"""The transparent, always-on-top window Zengo lives in."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QContextMenuEvent, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QApplication, QWidget

from zengo.ui.sprites import Sprite


class PetWindow(QWidget):
    """Displays one sprite and translates raw mouse input into pet gestures.

    The window knows nothing about behaviour: it reports clicks, double-clicks
    and drags in screen coordinates and draws whatever it is told to. A single
    click is held back for the double-click interval, so the first click of a
    double-click doesn't also count as a poke.
    """

    clicked = Signal()
    double_clicked = Signal()
    grabbed = Signal(float, float)
    dragged = Signal(float, float)
    released = Signal()
    menu_requested = Signal(QPoint)
    """Right-clicked, at this screen point: the app shows the menu."""

    def __init__(self, drag_threshold: int) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # keeps it out of the taskbar and Alt+Tab
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Zengo")

        self._drag_threshold = drag_threshold
        self._sprite: Sprite | None = None
        self._press: QPointF | None = None
        self._dragging = False
        self._double = False
        self._pending_click = QTimer(self, singleShot=True)
        self._pending_click.setInterval(QApplication.styleHints().mouseDoubleClickInterval())
        self._pending_click.timeout.connect(self.clicked.emit)

    def show_sprite(self, sprite: Sprite, top_left: QPoint) -> None:
        if sprite is not self._sprite:
            self._sprite = sprite
            self.resize(sprite.pixmap.size())
            self.setMask(sprite.mask)
            self.update()
        if self.pos() != top_left:
            self.move(top_left)

    def paintEvent(self, event: QPaintEvent) -> None:
        if self._sprite is not None:
            QPainter(self).drawPixmap(0, 0, self._sprite.pixmap)

    # --- Gestures ----------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.globalPosition()
            self._dragging = False

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press is None:
            return
        position = event.globalPosition()
        if not self._dragging:
            if (position - self._press).manhattanLength() < self._drag_threshold:
                return
            self._dragging = True
            self.grabbed.emit(self._press.x(), self._press.y())
        self.dragged.emit(position.x(), position.y())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._press is None:
            return
        if self._dragging:
            self.released.emit()
        elif self._double:
            self._double = False  # the release that ends a double-click
        else:
            self._pending_click.start()
        self._press = None
        self._dragging = False

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pending_click.stop()
            self._double = True
            self.double_clicked.emit()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self.menu_requested.emit(event.globalPos())
