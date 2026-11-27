"""A feather he's dropped: fawn from his back, or white from his face."""

from __future__ import annotations

from zengo.sprites.compose import Frame, Layer, compose
from zengo.sprites.palette import PALETTE, outline_for

_ART: dict[int, tuple[str, ...]] = {
    0: ("..BLLL.", "SBBLLLW", "..BBL.."),
    1: ("....L", "...LL", "..BL.", ".BB..", "S...."),
    -1: ("L....", "LL...", ".LB..", "..BB.", "....S"),
}
"""Lying flat (or level as it falls), and tipped either way as it sways."""

_WHITE = str.maketrans({"S": "B", "B": "L", "L": "W"})

SIZE = 9
"""Its picture is this many art px square, the outline included."""


def build_feathers() -> dict[tuple[int, bool], Frame]:
    """Each tilt, fawn and white, keyed by ``(tilt, white)``."""
    frames = {}
    for tilt, rows in _ART.items():
        for white in (False, True):
            drawn = tuple(row.translate(_WHITE) for row in rows) if white else rows
            width = max(len(row) for row in drawn)
            layer = Layer(drawn, 1 + (SIZE - 2 - width) // 2, 1 + (SIZE - 2 - len(drawn)) // 2)
            frames[tilt, white] = compose([layer], SIZE, SIZE, PALETTE, outline_for)
    return frames
