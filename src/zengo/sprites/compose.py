"""Turn layered ASCII pixel art into RGBA frames.

Art is authored as text so it diffs cleanly and can be edited without an image
editor. Each character is a palette key; see :mod:`zengo.sprites.palette`.
The silhouette outline is generated here rather than drawn by hand, so parts can
be moved and recombined without redrawing their edges.

Pure Python by design: no Qt, so it is testable headless and reusable by tooling.
"""

from __future__ import annotations

import textwrap
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from zengo.sprites.palette import ERASE, RGBA, TRANSPARENT


@dataclass(frozen=True)
class Layer:
    """A block of pixel art whose top-left corner sits at ``(x, y)`` on the canvas."""

    rows: tuple[str, ...]
    x: int = 0
    y: int = 0

    @classmethod
    def parse(cls, art: str, x: int = 0, y: int = 0) -> Layer:
        """Build a layer from an indented triple-quoted string."""
        rows = tuple(textwrap.dedent(art).strip("\n").splitlines())
        return cls(rows, x, y)

    def shifted(self, dx: int, dy: int) -> Layer:
        return Layer(self.rows, self.x + dx, self.y + dy)


@dataclass(frozen=True)
class Frame:
    """A rendered frame: row-major pixels, ``None`` where transparent."""

    width: int
    height: int
    pixels: tuple[RGBA | None, ...]

    def pixel(self, x: int, y: int) -> RGBA | None:
        return self.pixels[y * self.width + x]

    def to_rgba_bytes(self) -> bytes:
        """Packed RGBA8888, the layout ``QImage.Format_RGBA8888`` expects."""
        clear = (0, 0, 0, 0)
        return b"".join(bytes(p or clear) for p in self.pixels)


def compose(
    layers: Iterable[Layer],
    width: int,
    height: int,
    palette: Mapping[str, RGBA],
    outline: Callable[[RGBA], RGBA] | None = None,
) -> Frame:
    """Paint ``layers`` bottom-to-top onto a ``width`` x ``height`` canvas.

    Pixels falling outside the canvas are clipped. If ``outline`` is given, every
    transparent pixel 4-adjacent to an opaque one becomes ``outline(c)``, where
    ``c`` is the darkest of those neighbours. Diagonals are left clear, which
    keeps pixel-art edges crisp.

    Raises:
        ValueError: a layer uses a character missing from ``palette``.
    """
    canvas: list[RGBA | None] = [None] * (width * height)

    for layer in layers:
        for row_index, row in enumerate(layer.rows):
            y = layer.y + row_index
            if not 0 <= y < height:
                continue
            for col_index, key in enumerate(row):
                x = layer.x + col_index
                if key == TRANSPARENT or not 0 <= x < width:
                    continue
                if key == ERASE:
                    canvas[y * width + x] = None
                elif key in palette:
                    canvas[y * width + x] = palette[key]
                else:
                    raise ValueError(
                        f"unknown palette key {key!r} at row {row_index}, column {col_index}"
                    )

    if outline is not None:
        canvas = _outlined(canvas, width, height, outline)

    return Frame(width, height, tuple(canvas))


def _outlined(
    canvas: list[RGBA | None], width: int, height: int, colour_for: Callable[[RGBA], RGBA]
) -> list[RGBA | None]:
    result = list(canvas)
    for y in range(height):
        for x in range(width):
            if canvas[y * width + x] is not None:
                continue
            neighbours = [
                pixel
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
                if 0 <= nx < width
                and 0 <= ny < height
                and (pixel := canvas[ny * width + nx]) is not None
            ]
            if neighbours:
                result[y * width + x] = colour_for(min(neighbours, key=lambda c: sum(c[:3])))
    return result
