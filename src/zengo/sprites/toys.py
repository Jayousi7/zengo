"""His toys: a little brass bell on a chain, and a mirror in a wooden frame."""

from __future__ import annotations

from zengo.sprites.compose import Frame, Layer, compose
from zengo.sprites.palette import PALETTE, outline_for

BELL = (
    "...m...",
    "...M...",
    "..hGG..",
    ".hGGGg.",
    ".GGGGg.",
    "GGGGGGg",
    "ggggggg",
    "...K...",
)
"""Hanging from the top of its chain (column 3, row 0)."""

BELL_WIDTH, BELL_HEIGHT = len(BELL[0]), len(BELL)
BELL_PIVOT = 3

BELL_HANG_COLUMN = 62
"""Branch art column it hangs from: past the perch, towards the tip."""
BRANCH_UNDERSIDE = 14
"""Branch art row just below the wood there."""

CAGE_BELL = (7, 11)
"""Where it hangs in the cage: art px right of the middle, and the row (from
the top of the cage art) just under the roof bar."""

MIRROR = (
    "..NOOON..",
    ".NAAAAAN.",
    "NAAWAAAaN",
    "NAWAAAAaN",
    "NAAAAAAaN",
    "NAAAAAaaN",
    "NAAAAAaaN",
    ".NaaaaaN.",
    "..NNNNN..",
)
MIRROR_STAND = ("....n....", "..nnnnn..")
MIRROR_HOOK = ("....m....",)
REFLECTION = Layer.parse(
    """
    .WW
    WKW
    WWQ
    """,
    x=3,
    y=3,
)
"""His own face looking back, when he's in front of it."""

MIRROR_WIDTH = len(MIRROR[0])

CAGE_MIRROR = (-8, 30)
"""Where it hangs in the cage: art px left of the middle, and the row (from the
top of the cage art) of its bottom edge, about his head's height."""


def build_bell(swing: int) -> Frame:
    """The bell swung ``swing`` (-1, 0 or 1) pixels sideways under its chain, with
    a clear border of two columns either side (room to swing) and one row."""
    layers = [Layer(BELL[:2], 2, 1), Layer(BELL[2:], 2 + swing, 3)]
    return compose(layers, BELL_WIDTH + 4, BELL_HEIGHT + 2, PALETTE, outline_for)


def build_mirror(hanging: bool, reflecting: bool) -> Frame:
    """The mirror on its stand (or on a hook), with his reflection if he's at it.
    Its bottom row stands on (or hangs to) the point given; clear border round."""
    top = MIRROR_HOOK if hanging else ()
    bottom = () if hanging else MIRROR_STAND
    rows = (*top, *MIRROR, *bottom)
    layers = [Layer(rows, 1, 1)]
    if reflecting:
        layers.append(REFLECTION.shifted(1, 1 + len(top)))
    return compose(layers, MIRROR_WIDTH + 2, len(rows) + 2, PALETTE, outline_for)
