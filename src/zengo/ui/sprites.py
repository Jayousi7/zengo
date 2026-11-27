"""Qt conversion of composed frames: scaling, mirroring and click masks."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QBitmap, QImage, QPixmap, QRegion

from zengo.behavior.body import Facing
from zengo.sprites.compose import Frame


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
    """Every frame pre-rendered for both facings, so playback never rasterises."""

    def __init__(self, frames: Mapping[str, Frame], scale: int) -> None:
        self._sprites: dict[tuple[str, Facing], Sprite] = {}
        for name, frame in frames.items():
            image = frame_to_image(frame, scale)
            self._sprites[name, Facing.RIGHT] = _sprite(image)
            self._sprites[name, Facing.LEFT] = _sprite(image.mirrored(True, False))

    def get(self, name: str, facing: Facing) -> Sprite:
        return self._sprites[name, facing]


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
