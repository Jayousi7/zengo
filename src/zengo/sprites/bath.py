"""His bath dish: a shallow glazed dish, water rippling in it.

Seen side on, like him: the rim and a sliver of water above it. Standing in it,
he's drawn behind the dish, so its rim (taller than his legs) hides his feet and
the water comes up round him.
"""

from __future__ import annotations

from zengo.sprites.compose import Frame, Layer, compose
from zengo.sprites.palette import PALETTE, outline_for

DISH = Layer.parse(
    """
    UUUUUUUUUUUUUUUUUUUUUUUUU
    .uUUUUUUUUUUUUUUUUUUUUUu.
    ..uUUUUUUUUUUUUUUUUUUUu..
    ...uuuuuuuuuuuuuuuuuuu...
    """,
    x=0,
    y=2,
)

WATER = (
    ".aAAaAAaAAaAAaAAaAAaAAaA.",
    ".AaAAaAAaAAaAAaAAaAAaAAa.",
    ".AAaAAaAAaAAaAAaAAaAAaAA.",
)
"""The water's surface, one ripple pattern per frame."""

SPLASHING = Layer.parse(
    """
    ..A...a.....A....a...A...
    .aAaAAaAAaAAaAAaAAaAAaAa.
    """,
    x=0,
    y=0,
)
"""The water thrown about while he splashes."""

DISH_WIDTH = len(DISH.rows[0])
DISH_HEIGHT = 6
"""Rows, from the splash at the top to the foot of the dish."""

RIPPLES = len(WATER)


def build_dish(ripple: int, splashing: bool = False) -> Frame:
    """The dish with its water at ripple ``ripple``, with a clear border for the
    outline. Its bottom row stands on the ground."""
    water = SPLASHING if splashing else Layer((WATER[ripple % RIPPLES],), 0, 1)
    layers = [water.shifted(1, 1), DISH.shifted(1, 1)]
    return compose(layers, DISH_WIDTH + 2, DISH_HEIGHT + 2, PALETTE, outline_for)
