"""Sunflower seeds: a little pile of them, shrinking as Zengo eats."""

from __future__ import annotations

from zengo.sprites.compose import Frame, Layer, compose
from zengo.sprites.palette import PALETTE, outline_for

SEED = "KkK"
"""One sunflower seed lying on its side: black, with a pale stripe."""

SPOTS = (
    (0, 2), (4, 2), (8, 2), (12, 2),
    (2, 1), (6, 1), (10, 1),
    (6, 0),
)  # fmt: skip
"""Where each seed lies in the pile, bottom row first; the top seed is eaten first."""

MAX_SEEDS = len(SPOTS)
PILE_WIDTH = max(x for x, _ in SPOTS) + len(SEED)
PILE_HEIGHT = max(y for _, y in SPOTS) + 1


def build_pile(seeds: int) -> Frame:
    """The pile with ``seeds`` left in it, with a clear border for the outline.

    Its bottom row rests on the ground; its centre is the pile's x position.
    """
    layers = [Layer((SEED,), x + 1, y + 1) for x, y in SPOTS[: max(0, min(seeds, MAX_SEEDS))]]
    return compose(layers, PILE_WIDTH + 2, PILE_HEIGHT + 2, PALETTE, outline_for)
