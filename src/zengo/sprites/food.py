"""Sunflower seeds: a pile of up to three stacks, filling up and shrinking seed by seed."""

from __future__ import annotations

from zengo.sprites.compose import Frame, Layer, compose
from zengo.sprites.palette import PALETTE, outline_for

SEED = "KkK"
"""One sunflower seed lying on its side: black, with a pale stripe."""

SEEDS_PER_STACK = 8
MAX_STACKS = 3
MAX_SEEDS = SEEDS_PER_STACK * MAX_STACKS

_ROWS = (6, 5, 5, 4, 3, 1)
"""Seeds in each row of a full pile, from the bottom up: a mound."""

SPOTS = tuple(
    ((_ROWS[0] - count) * 2 + i * 4, len(_ROWS) - 1 - row)
    for row, count in enumerate(_ROWS)
    for i in range(count)
)
"""Where each seed lies, in the order they're piled on: bottom row first, so one
stack makes a low heap and three a full mound. The last one on is eaten first."""

PILE_WIDTH = max(x for x, _ in SPOTS) + len(SEED)
PILE_HEIGHT = len(_ROWS)


def build_pile(seeds: int) -> Frame:
    """The pile with ``seeds`` in it, with a clear border for the outline.

    Its bottom row rests on whatever it's put on; its centre is the pile's x.
    """
    layers = [Layer((SEED,), x + 1, y + 1) for x, y in SPOTS[: max(0, min(seeds, MAX_SEEDS))]]
    return compose(layers, PILE_WIDTH + 2, PILE_HEIGHT + 2, PALETTE, outline_for)
