"""The cage Zengo can be caught in, and what it hangs from.

Seen from the front. The bars are drawn without a generated outline: with gaps
this narrow an outline would fill them in. Zengo sits inside, behind the bars,
with his feet on the tray.
"""

from __future__ import annotations

from zengo.sprites.compose import Frame, Layer, compose
from zengo.sprites.palette import PALETTE, outline_for

CAGE = Layer.parse(
    """
    ..............hh
    .............h..h
    ..............hh
    ...............g
    ............GGGGG
    ..............g
    .........GG.G...g.gg
    ......G.G..G.....g..g.g
    ....G..G...G.....g...g..g
    ..G...G...G.......g...g...g
    ..GGGGGGGGGGGGGGGGGGGGGGGGG
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..GGGGGGGGGGGGGGGGGGGGGGGGG
    ..G...G...G.......g...g...g
    ..G...G..GGGGGGGGGGG..g...g
    ..G...G..GG.......gg..g...g
    ..G...G..GG.......gg..g...g
    ..G...G..GG.......ggh.g...g
    ..G...G..GG.......gg..g...g
    ..G...G..GG.......gg..g...g
    ..G...G..GG.......gg..g...g
    ..G...G..GG.......gg..g...g
    hhhhhhhhhhhhhhhhhhhhhhhhhhhhh
    OOOOOOOOOOOOOOOOOOOOOOOOOOOOO
    NNNNNNNNNNNNNNNNNNNNNNNNNNNNN
    nnnnnnnnnnnnnnnnnnnnnnnnnnnnn
    .n.........................n
    """
)

CAGE_OPEN = Layer.parse(
    """
    ..............hh
    .............h..h
    ..............hh
    ...............g
    ............GGGGG
    ..............g
    .........GG.G...g.gg
    ......G.G..G.....g..g.g
    ....G..G...G.....g...g..g
    ..G...G...G.......g...g...g
    ..GGGGGGGGGGGGGGGGGGGGGGGGG
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..G...G...G.......g...g...g
    ..GGGGGGGGGGGGGGGGGGGGGGGGG
    ..G...G...G.......g...g...g
    ..G...GgG.G.......g...g...g
    ..G...GgG.............g...g
    ..G...GgG.............g...g
    ..G...hgG.............g...g
    ..G...GgG.............g...g
    ..G...GgG.............g...g
    ..G...GgG.............g...g
    ..G...GgG.............g...g
    hhhhhhhhhhhhhhhhhhhhhhhhhhhhh
    OOOOOOOOOOOOOOOOOOOOOOOOOOOOO
    NNNNNNNNNNNNNNNNNNNNNNNNNNNNN
    nnnnnnnnnnnnnnnnnnnnnnnnnnnnn
    .n.........................n
    """
)
"""The door swung open, edge-on to the left of the doorway."""

CAGE_WIDTH = max(len(row) for row in CAGE.rows)
CAGE_HEIGHT = len(CAGE.rows)

CENTRE = 14
"""Column Zengo's anchor lines up with."""

FLOOR = 41
"""Row of the tray's top surface, where his feet rest."""

CHAIN_LINK = Layer.parse(
    """
    ..M..
    .M.M.
    .M.M.
    ..M..
    ..m..
    """
)
"""One link of the chain the cage hangs from; repeated down from the top of the screen."""

CHAIN_CENTRE = 2
"""Column of the link the chain runs through."""

SHELF = Layer.parse(
    """
    OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
    NNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNN
    nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn
    .mMMMMMMMMM
    .m.......M
    .m......M
    .m.....M
    .m....M
    .m...M
    .m..M
    .m.M
    .mm
    """
)
"""A plank on a bracket: a plate against the screen edge at column 1, an arm under
the plank, and a brace from low on the wall up to the end of the arm."""

SHELF_WIDTH = max(len(row) for row in SHELF.rows)
SHELF_HEIGHT = len(SHELF.rows)


def build_cage(*, door_open: bool = False) -> Frame:
    layer = CAGE_OPEN if door_open else CAGE
    return compose([layer.shifted(1, 1)], CAGE_WIDTH + 2, CAGE_HEIGHT + 2, PALETTE, None)


def build_chain_link() -> Frame:
    width, height = max(len(r) for r in CHAIN_LINK.rows), len(CHAIN_LINK.rows)
    return compose([CHAIN_LINK.shifted(1, 0)], width + 2, height, PALETTE, outline_for)


def build_shelf() -> Frame:
    return compose([SHELF.shifted(0, 1)], SHELF_WIDTH + 1, SHELF_HEIGHT + 2, PALETTE, outline_for)
