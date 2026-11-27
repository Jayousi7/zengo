"""The one window all the droplets, snowflakes and leaves are drawn in."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QPainter, QPaintEvent, QPixmap
from PySide6.QtWidgets import QWidget

from zengo.behavior.effects import Particle
from zengo.sprites.effects import build_particles, particle_name
from zengo.ui.layering import bypass_window_manager
from zengo.ui.sprites import frame_to_image


class EffectsWindow(QWidget):
    """Sized each frame to just cover the particles there are, and hidden when
    there are none. Clicks pass through."""

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
        self.setWindowTitle("Zengo's surroundings")
        self._pictures = {
            name: QPixmap.fromImage(frame_to_image(frame, scale))
            for name, frame in build_particles().items()
        }
        self._drawn: list[tuple[QPixmap, QPoint, float]] = []

    def show_particles(self, particles: Sequence[Particle]) -> None:
        drawn = []
        for p in particles:
            picture = self._pictures[particle_name(p.kind, p.tilt)]
            # Centred on the particle's position.
            at = QPoint(round(p.x) - picture.width() // 2, round(p.y) - picture.height() // 2)
            drawn.append((picture, at, p.alpha))
        if not drawn:
            self._drawn = []
            self.hide()
            return
        bounds = QRect()
        for picture, at, _ in drawn:
            bounds = bounds.united(QRect(at, picture.size()))
        self._drawn = [(picture, at - bounds.topLeft(), alpha) for picture, at, alpha in drawn]
        if self.geometry() != bounds:
            self.setGeometry(bounds)
        if not self.isVisible():
            self.show()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        for picture, at, alpha in self._drawn:
            painter.setOpacity(alpha)
            painter.drawPixmap(at, picture)
