"""Zengo's colours.

Sampled from reference photos of a cinnamon white-face cockatiel. Lights lean
warm (cream) and shadows lean cool (mauve) rather than just darkening, which
keeps a pale bird from turning muddy at small sizes.
"""

RGBA = tuple[int, int, int, int]

TRANSPARENT = "."
"""Leaves the pixel underneath untouched."""

ERASE = "_"
"""Clears the pixel underneath, so a layer can cut into the layers below it."""


def _rgb(hex_code: str) -> RGBA:
    value = int(hex_code.lstrip("#"), 16)
    return (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF, 0xFF


PALETTE: dict[str, RGBA] = {
    # Plumage.
    "W": _rgb("#fcf7ef"),  # white face mask
    "P": _rgb("#f7f0e6"),  # pale wing patch
    "L": _rgb("#efe4d6"),  # light fawn: head, chest
    "B": _rgb("#dbc9ba"),  # mid fawn: body
    "S": _rgb("#baa5a0"),  # shadow, shifted towards mauve
    "C": _rgb("#cbac94"),  # cinnamon coverts
    "D": _rgb("#a08076"),  # cinnamon primaries
    "T": _rgb("#d6c4b6"),  # tail
    "t": _rgb("#aa9187"),  # tail shadow
    # Bare parts.
    "K": _rgb("#2a1c22"),  # eye
    "Q": _rgb("#f0c4b6"),  # beak
    "q": _rgb("#ce928a"),  # beak shadow
    "F": _rgb("#eca8a0"),  # feet
    # Scenery: the branch's bark and leaves.
    "O": _rgb("#a8876c"),  # bark, lit upper surface
    "N": _rgb("#8b6b55"),  # bark
    "n": _rgb("#634a3c"),  # bark shadow
    "Y": _rgb("#aecb8f"),  # leaf, lit side
    "V": _rgb("#86a86e"),  # leaf
    "v": _rgb("#5f8052"),  # leaf shadow
    # The cage: brass bars, and the iron chain and bracket it hangs from.
    "G": _rgb("#d4b06a"),  # brass
    "g": _rgb("#a07f3f"),  # brass in shadow
    "h": _rgb("#efd99a"),  # brass highlight
    "M": _rgb("#a3a3ab"),  # iron
    "m": _rgb("#66666e"),  # iron in shadow
}


def outline_for(neighbour: RGBA) -> RGBA:
    """Outline colour for an edge next to ``neighbour``: a dark, mauve-shifted shade of it.

    Edges take their colour from what they border instead of one flat line
    colour, so the pink beak gets a rosy edge and the white face a soft grey one.
    """
    r, g, b, _ = neighbour
    return int(r * 0.42) + 10, int(g * 0.34) + 8, int(b * 0.38) + 14, 0xFF
