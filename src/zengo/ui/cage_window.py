"""The cage's window, and the window for the chain or shelf it hangs from."""

from __future__ import annotations

import math

from PySide6.QtCore import QPoint, QPointF, QRect, Qt, Signal
from PySide6.QtGui import (
    QContextMenuEvent,
    QGuiApplication,
    QImage,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPixmap,
    QRegion,
)
from PySide6.QtWidgets import QWidget

from zengo.behavior.cage import BELOW_FLOOR, Cage
from zengo.config import Config
from zengo.sprites.cage import (
    CENTRE,
    CHAIN_CENTRE,
    FLOOR,
    build_cage,
    build_chain_link,
    build_shelf,
)
from zengo.ui.sprites import frame_to_image

_FLAGS = (
    Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
    | Qt.WindowType.Tool
    | Qt.WindowType.WindowDoesNotAcceptFocus
)


def _silhouette(image: QImage) -> QRegion:
    """Each row filled from its first opaque pixel to its last: the cage's whole
    outline, between the bars too, so a click anywhere on it lands on the cage."""
    region = QRegion()
    for y in range(image.height()):
        xs = [x for x in range(image.width()) if image.pixelColor(x, y).alpha()]
        if xs:
            region += QRect(xs[0], y, xs[-1] - xs[0] + 1, 1)
    return region


class CageWindow(QWidget):
    """The cage, in front of Zengo so the bars are over him. Drag it with the left
    button; right-click for the menu."""

    grabbed = Signal(float, float)
    dragged = Signal(float, float)
    released = Signal()
    menu_requested = Signal(QPoint)

    def __init__(self, config: Config, drag_threshold: int) -> None:
        super().__init__(None, _FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Zengo's cage")
        self._config = config
        self._threshold = drag_threshold
        images = {
            door: frame_to_image(build_cage(door_open=door), config.scale) for door in (False, True)
        }
        self._pixmaps = {door: QPixmap.fromImage(image) for door, image in images.items()}
        self._mask = _silhouette(images[False])
        self._door = False
        self._press: QPointF | None = None
        self._dragging = False
        self.resize(self._pixmaps[False].size())
        self.setMask(self._mask)

    def show_cage(self, cage: Cage | None) -> None:
        if cage is None:
            self.hide()
            return
        px = self._config.px
        left = round(cage.shown_x - px(CENTRE + 1 + 0.5))
        top = round(cage.y - px(FLOOR + 1))
        if cage.door_open != self._door:
            self._door = cage.door_open
            self.update()
        if self.pos() != QPoint(left, top):
            self.move(left, top)
        if not self.isVisible():
            self.show()
            self.raise_()  # in front of him: he's behind the bars

    def paintEvent(self, event: QPaintEvent) -> None:
        QPainter(self).drawPixmap(0, 0, self._pixmaps[self._door])

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press, self._dragging = event.globalPosition(), False

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press is None:
            return
        position = event.globalPosition()
        if not self._dragging:
            if (position - self._press).manhattanLength() < self._threshold:
                return
            self._dragging = True
            self.grabbed.emit(self._press.x(), self._press.y())
        self.dragged.emit(position.x(), position.y())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self.released.emit()
        self._press, self._dragging = None, False

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self.menu_requested.emit(event.globalPos())


class MountWindow(QWidget):
    """The chain a hung cage hangs from, or the shelf it stands on. Clicks pass through."""

    def __init__(self, config: Config) -> None:
        super().__init__(None, _FLAGS | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Zengo's cage mount")
        self._config = config
        self._link = QPixmap.fromImage(frame_to_image(build_chain_link(), config.scale))
        shelf = frame_to_image(build_shelf(), config.scale)
        self._shelves = {
            -1: QPixmap.fromImage(shelf),
            1: QPixmap.fromImage(shelf.mirrored(True, False)),
        }
        self._draw: tuple = ()

    def show_mount(self, cage: Cage | None) -> None:
        if cage is None or cage.mount not in ("chain", "shelf"):
            self.hide()
            return
        px = self._config.px
        if cage.mount == "chain":
            assert cage.pivot is not None
            top = QPointF(*cage.pivot)
            hook = QPointF(cage.shown_x, cage.y - px(FLOOR))
            pad = self._link.width()
            box = QRect(
                round(min(top.x(), hook.x()) - pad),
                round(top.y()),
                round(abs(hook.x() - top.x()) + 2 * pad),
                max(1, round(hook.y() - top.y()) + px(2)),
            )
            self._draw = ("chain", top - QPointF(box.topLeft()), hook - QPointF(box.topLeft()))
        else:
            shelf = self._shelves[cage.side]
            screen = QGuiApplication.screenAt(QPoint(round(cage.x), round(cage.y)))
            area = (screen or QGuiApplication.primaryScreen()).availableGeometry()
            left = area.left() if cage.side < 0 else area.right() + 1 - shelf.width()
            top = round(cage.y + px(BELOW_FLOOR)) - px(1)  # the tray's underside on the plank
            box = QRect(left, top, shelf.width(), shelf.height())
            self._draw = ("shelf", cage.side)
        if self.geometry() != box:
            self.setGeometry(box)
        self.update()
        if not self.isVisible():
            self.show()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        if not self._draw:
            return
        if self._draw[0] == "shelf":
            painter.drawPixmap(0, 0, self._shelves[self._draw[1]])
            return
        _, top, hook = self._draw
        link_h = self._link.height()
        length = math.dist((top.x(), top.y()), (hook.x(), hook.y()))
        count = max(1, math.ceil(length / link_h))
        offset = self._config.px(CHAIN_CENTRE + 1 + 0.5)
        for i in range(count):
            t = (i * link_h) / max(length, 1)
            x = top.x() + (hook.x() - top.x()) * t
            y = top.y() + (hook.y() - top.y()) * t
            painter.drawPixmap(round(x - offset), round(y), self._link)
