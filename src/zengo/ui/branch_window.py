"""The window the branch is drawn in."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPainter, QPaintEvent, QPixmap
from PySide6.QtWidgets import QWidget

from zengo.behavior.scenery import Branch
from zengo.config import Config
from zengo.sprites.branch import TOP_ROW, build_branch
from zengo.ui.sprites import frame_to_image, mirror

_PADDING = 1
"""The clear border :func:`build_branch` leaves round the art for its outline."""


class BranchWindow(QWidget):
    """Shows the branch growing out of a screen edge.

    Clicks pass straight through: it sits on the screen's edge, over scrollbars
    and the like. It stays above Zengo's window, so when he sits on it his tail
    hangs down behind the branch, as it would.
    """

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
        self.setWindowTitle("Zengo's branch")
        self._config = config
        image = frame_to_image(build_branch(), config.scale)
        self._pixmaps = {
            -1: QPixmap.fromImage(image),  # grows rightwards from the left edge
            1: QPixmap.fromImage(mirror(image)),
        }
        self._side = -1

    def show_branch(self, branch: Branch | None) -> None:
        if branch is None or branch.shown <= 0:
            self.hide()
            return
        pixmap = self._pixmaps[branch.side]
        visible = max(1, round(pixmap.width() * min(branch.shown, 1.0)))
        top = round(branch.top - self._config.px(TOP_ROW + _PADDING))
        left = round(branch.edge) if branch.side < 0 else round(branch.edge) - visible
        self._side = branch.side
        if self.size().width() != visible or self.size().height() != pixmap.height():
            self.resize(visible, pixmap.height())
            self.update()
        if self.pos() != QPoint(left, top):
            self.move(left, top)
        if not self.isVisible():
            self.show()
            self.raise_()

    def keep_in_front(self) -> None:
        if self.isVisible():
            self.raise_()

    def paintEvent(self, event: QPaintEvent) -> None:
        pixmap = self._pixmaps[self._side]
        # Only the part that has grown out shows: the tip end, flush with the window's
        # far side, so it seems to slide out of the screen edge.
        x = self.width() - pixmap.width() if self._side < 0 else 0
        QPainter(self).drawPixmap(x, 0, pixmap)
