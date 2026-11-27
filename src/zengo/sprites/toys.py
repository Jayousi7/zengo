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

STANDING_MIRROR = (
    "...NNOOONN...",
    "..NAAAAAAAN..",
    ".NAAWWAAAAaN.",
    "NAAWAAAAAAAaN",
    "NAWAAAAAAAAaN",
    "NAAAAAAAAAAaN",
    "NAAAAAAAAAaaN",
    "NAAAAAAAAAaaN",
    "NAAAAAAAAAaaN",
    "NAAAAAAAAaaaN",
    "NAAAAAAAAaaaN",
    "NAAAAAAAaaaaN",
    ".NAAAAAaaaaN.",
    "..NaaaaaaaN..",
    "...NNNNNNN...",
    "......n......",
    "......n......",
    "....nnnnn....",
    "..nnnnnnnnn..",
)
"""His mirror on the ground: an oval glass in a wooden frame, on a stand, about
two thirds his height, so he can see himself in it."""

STANDING_REFLECTION = Layer.parse(
    """
    .B.B.B.
    ..LLL..
    .WWWWW.
    WKWWWKW
    WWWQWWW
    .WQqWW.
    ..WWW..
    """,
    x=3,
    y=3,
)
"""His own face looking back, when he's in front of it."""

HANGING_MIRROR = (
    "....m....",
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
"""The small one that hangs on his cage bars (a big one wouldn't fit in)."""

HANGING_REFLECTION = Layer.parse(
    """
    .WW
    WKW
    WWQ
    """,
    x=3,
    y=4,
)

STANDING_WIDTH = len(STANDING_MIRROR[0])

CAGE_MIRROR = (-8, 31)
"""Where it hangs in the cage: art px left of the middle, and the row (from the
top of the cage art) of its bottom edge, about his head's height."""


def build_bell(swing: int) -> Frame:
    """The bell swung ``swing`` (-1, 0 or 1) pixels sideways under its chain, with
    a clear border of two columns either side (room to swing) and one row."""
    layers = [Layer(BELL[:2], 2, 1), Layer(BELL[2:], 2 + swing, 3)]
    return compose(layers, BELL_WIDTH + 4, BELL_HEIGHT + 2, PALETTE, outline_for)


def build_mirror(hanging: bool, reflecting: bool) -> Frame:
    """The mirror on its stand (or the small one on a hook), with his reflection
    if he's at it. Its bottom row stands on (or hangs to) the point given, with a
    clear border round it."""
    rows = HANGING_MIRROR if hanging else STANDING_MIRROR
    layers = [Layer(rows, 1, 1)]
    if reflecting:
        layers.append((HANGING_REFLECTION if hanging else STANDING_REFLECTION).shifted(1, 1))
    width = max(len(row) for row in rows)
    return compose(layers, width + 2, len(rows) + 2, PALETTE, outline_for)
