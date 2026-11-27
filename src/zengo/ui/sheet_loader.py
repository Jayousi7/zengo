"""Load hand-drawn frames from an Aseprite sprite-sheet export.

Lets art drawn in a pixel editor (Aseprite, LibreSprite, Piskel via Aseprite
JSON) replace any of the built-in frames. Export with JSON data in either the
"hash" or "array" layout; each frame's name must be one of the built-in frame
names (``perch``, ``blink``, ...) and its size must match the canvas, so it
lines up with the ground row and anchor column.
"""

from __future__ import annotations

import json
from collections.abc import Collection
from pathlib import Path

from PySide6.QtGui import QImage

from zengo.sprites.compose import Frame
from zengo.sprites.frames import CANVAS_HEIGHT, CANVAS_WIDTH


class SheetError(ValueError):
    pass


def load_sheet(json_path: Path, known_names: Collection[str]) -> dict[str, Frame]:
    """Read frames from an Aseprite JSON export and the PNG it references.

    Raises:
        SheetError: unreadable image, unknown frame name, or wrong frame size.
    """
    data = json.loads(json_path.read_text(encoding="utf-8"))
    image_path = json_path.parent / data["meta"]["image"]
    image = QImage(str(image_path))
    if image.isNull():
        raise SheetError(f"cannot read image {image_path}")
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)

    entries = data["frames"]
    named = entries.items() if isinstance(entries, dict) else ((e["filename"], e) for e in entries)

    frames: dict[str, Frame] = {}
    for name, entry in named:
        if name not in known_names:
            raise SheetError(f"unknown frame {name!r}; expected one of {sorted(known_names)}")
        rect = entry["frame"]
        if (rect["w"], rect["h"]) != (CANVAS_WIDTH, CANVAS_HEIGHT):
            raise SheetError(
                f"frame {name!r} is {rect['w']}x{rect['h']}, "
                f"expected {CANVAS_WIDTH}x{CANVAS_HEIGHT}"
            )
        frames[name] = _to_frame(image.copy(rect["x"], rect["y"], rect["w"], rect["h"]))
    return frames


def _to_frame(image: QImage) -> Frame:
    width, height = image.width(), image.height()
    stride = image.bytesPerLine()
    data = bytes(image.constBits())
    pixels = []
    for y in range(height):
        row = data[y * stride : y * stride + width * 4]
        for x in range(0, width * 4, 4):
            r, g, b, a = row[x : x + 4]
            pixels.append((r, g, b, a) if a else None)
    return Frame(width, height, tuple(pixels))
