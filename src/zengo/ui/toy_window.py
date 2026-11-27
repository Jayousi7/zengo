"""Windows for his toys: the bell, hanging and swinging, and the mirror."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPainter, QPaintEvent, QPixmap
from PySide6.QtWidgets import QWidget

from zengo.behavior.toys import Bell, Mirror
from zengo.config import Config
from zengo.sprites.toys import BELL_PIVOT, build_bell, build_mirror
from zengo.ui.layering import bypass_window_manager
from zengo.ui.sprites import frame_to_image


class _ToyWindow(QWidget):
    """Click-through, in front of him (so a bell in his cage hangs before him)."""

    def __init__(self, title: str, in_front_of: QWidget | None) -> None:
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
        self.setWindowTitle(title)
        self._picture: QPixmap | None = None

    def _show(self, picture: QPixmap | None, at: QPoint) -> None:
        if picture is None:
            self._picture = None
            self.hide()
            return
        if picture is not self._picture:
            self._picture = picture
            self.resize(picture.size())
            self.update()
        if self.pos() != at:
            self.move(at)
        if not self.isVisible():
            self.show()

    def paintEvent(self, event: QPaintEvent) -> None:
        if self._picture is not None:
            QPainter(self).drawPixmap(0, 0, self._picture)


class BellWindow(_ToyWindow):
    def __init__(self, config: Config, in_front_of: QWidget | None = None) -> None:
        super().__init__("Zengo's bell", in_front_of)
        self._config = config
        self._swings = {
            swing: QPixmap.fromImage(frame_to_image(build_bell(swing), config.scale))
            for swing in (-1, 0, 1)
        }

    def show_bell(self, bell: Bell | None) -> None:
        if bell is None:
            self._show(None, QPoint())
            return
        px = self._config.px
        # The top of its chain (two columns of room, one row of border in) hangs there.
        at = QPoint(round(bell.x - px(BELL_PIVOT + 2.5)), round(bell.y - px(1)))
        self._show(self._swings[bell.swing], at)


class MirrorWindow(_ToyWindow):
    def __init__(self, config: Config, in_front_of: QWidget | None = None) -> None:
        super().__init__("Zengo's mirror", in_front_of)
        self._config = config
        self._pictures = {
            (hanging, reflecting): QPixmap.fromImage(
                frame_to_image(build_mirror(hanging, reflecting), config.scale)
            )
            for hanging in (False, True)
            for reflecting in (False, True)
        }

    def show_mirror(self, mirror: Mirror | None) -> None:
        if mirror is None:
            self._show(None, QPoint())
            return
        picture = self._pictures[mirror.where == "cage", mirror.reflecting]
        px = self._config.px
        at = QPoint(
            round(mirror.x - picture.width() / 2), round(mirror.y - picture.height() + px(1))
        )
        self._show(picture, at)
