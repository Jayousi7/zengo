"""Qt conversion of composed frames: scaling, mirroring and click masks."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QBitmap, QImage, QPixmap, QRegion

from zengo.behavior.body import Facing
from zengo.sprites.compose import Frame
from zengo.sprites.looks import PLAIN, Look, frame_in


def frame_to_image(frame: Frame, scale: int) -> QImage:
    """Nearest-neighbour upscale; smoothing would blur the pixel art."""
    image = QImage(
        frame.to_rgba_bytes(), frame.width, frame.height, QImage.Format.Format_RGBA8888
    ).copy()  # detach from the temporary bytes buffer
    return image.scaled(
        frame.width * scale,
        frame.height * scale,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.FastTransformation,
    )


@dataclass(frozen=True)
class Sprite:
    pixmap: QPixmap
    mask: QRegion
    """Opaque area only, so clicks on transparent pixels fall through to the desktop."""


class SpriteSheet:
    """Every frame pre-rendered for both facings, so playback never rasterises.

    Frames in another look (damp, a scarf, dimmed: see :mod:`zengo.sprites.looks`)
    are drawn the first time they're shown and kept: most never are."""

    def __init__(
        self, frames: Mapping[str, Frame], scale: int, custom: frozenset[str] = frozenset()
    ) -> None:
        self._frames, self._scale, self._custom = frames, scale, custom
        self._sprites: dict[tuple[str, Look, Facing], Sprite] = {}
        for name in frames:
            self._render(name, PLAIN)

    def get(self, name: str, facing: Facing, look: Look = PLAIN) -> Sprite:
        if (name, look, facing) not in self._sprites:
            self._render(name, look)
        return self._sprites[name, look, facing]

    def _render(self, name: str, look: Look) -> None:
        image = frame_to_image(frame_in(name, look, self._frames, self._custom), self._scale)
        self._sprites[name, look, Facing.RIGHT] = _sprite(image)
        self._sprites[name, look, Facing.LEFT] = _sprite(mirror(image))


def _sprite(image: QImage) -> Sprite:
    pixmap = QPixmap.fromImage(image)
    return Sprite(pixmap, QRegion(QBitmap(pixmap.mask())))


def clip_to(full: QRect, bounds: QRect | None) -> tuple[QRect, QPoint]:
    """Trim a window's rectangle to the desktop.

    Window managers push windows that stick off the screen back onto it, which
    would shift Zengo away from where he should be (out of his cage, say).
    Instead the window is trimmed to the desktop and the picture drawn offset
    inside it. Returns the rectangle to give the window, and where the
    picture's top-left corner falls in it.
    """
    shown = full.intersected(bounds) if bounds is not None else full
    if shown.isEmpty():
        shown = full
    return shown, full.topLeft() - shown.topLeft()


def mirror(image: QImage) -> QImage:
    """Flip an image left to right. ``QImage.flipped`` replaced ``mirrored`` in Qt 6.9;
    older versions only have the latter."""
    if hasattr(image, "flipped"):
        return image.flipped(Qt.Orientation.Horizontal)
    return image.mirrored(True, False)
