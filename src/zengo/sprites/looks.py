"""How he looks just now, on top of whatever pose he's in.

- **Damp** after a bath: darker, cooler feathers and his crest slicked down.
- **Scarf** in winter: a little knitted one round his neck.
- **Dim** late in the evening: everything softer and a little blue.

None of these redraws a pose. The damp colours and the dimming are palette
changes; the slicked crest and the scarf swap or add a layer, found by the
layers each frame is built from: whichever head a pose uses, the scarf goes
round its neck. A frame replaced from an Aseprite sheet has no layers to go by,
so it gets the colour changes only.

Pure Python: no Qt.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from zengo.sprites import art
from zengo.sprites.compose import Frame, Layer, compose
from zengo.sprites.frames import (
    ANCHOR_COLUMN,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    FRAME_LAYERS,
    PADDING,
)
from zengo.sprites.palette import PALETTE, RGBA, outline_for


@dataclass(frozen=True)
class Look:
    damp: bool = False
    scarf: bool = False
    dim: bool = False


PLAIN = Look()

PLUMAGE = "WPLBSCDTt"
"""Palette keys for feathers: what a bath darkens."""


def _wet(colour: RGBA) -> RGBA:
    r, g, b, a = colour
    return round(r * 0.88), round(g * 0.87), round(b * 0.92), a


def _dimmed(colour: RGBA) -> RGBA:
    r, g, b, a = colour
    return round(r * 0.84), round(g * 0.85), round(b * 0.94), a


DAMP_PALETTE: dict[str, RGBA] = {
    key: _wet(colour) if key in PLUMAGE else colour for key, colour in PALETTE.items()
}

# --- The scarf ---------------------------------------------------------------------
# Red wool, ribbed here and there, round the base of his neck, its loose end
# hanging down his chest (or his back, from behind). It belongs to his body, not
# his head: drawn over the body and wings but under the head, so his head moves
# above it (nodding, preening, singing) as it would over a real scarf, and it
# stays inside his outline so he's never drawn in two pieces. Each scarf is
# placed for its body drawn where that body's art says; moved with the body.

_SIDE_SCARF = Layer.parse(
    """
    rRRrRRrRR
    .rRRrRRrR
    ......Rr.
    ......rR.
    .......r.
    """,
    x=31,
    y=16,
)

_FLYING_SCARF = Layer.parse(
    """
    rRRr.....
    ...rRRrR.
    .......Rr
    .......rR
    .......Rr
    .......rR
    .......Rr
    """,
    x=24,
    y=16,
)
"""Flying, his head leads the level body: a band round the neck behind it, and the
loose end streaming back over his shoulders."""

_DIP_SCARF = Layer.parse(
    """
    rR..
    Rr..
    rR..
    Rr..
    .rR.
    ..Rr
    ..r.
    """,
    x=33,
    y=15,
)
_LOW_SCARF = Layer.parse(
    """
    rR..
    Rr..
    rR..
    .Rr.
    .rR.
    ..Rr
    """,
    x=34,
    y=17,
)
"""Bent over pecking: the neck reaches forward and down, the scarf round it."""

_FRONT_SCARF = Layer.parse(
    """
    rRRrRRrRr
    .rRRrRRr.
    .....Rr..
    .....rR..
    ......r..
    """,
    x=26,
    y=16,
)
_BACK_SCARF = Layer.parse(
    """
    rRRrRRrRr
    .rRRrRRr.
    ...Rr....
    ...rR....
    ...r.....
    """,
    x=26,
    y=16,
)

_SCARVES = (
    (art.BODY, _SIDE_SCARF),
    (art.FLIGHT_BODY, _FLYING_SCARF),
    (art.BENT_BODY_DIP, _DIP_SCARF),
    (art.BENT_BODY, _LOW_SCARF),
    (art.FRONT_BODY, _FRONT_SCARF),
    (art.BACK_BODY, _BACK_SCARF),
    (art.FRONT_FLY_BODY, _FRONT_SCARF.shifted(0, 5)),
)
"""Each body, and its scarf as placed for that body where its art puts it."""

_HEADS = frozenset(
    layer.rows
    for layer in (
        art.HEAD, art.HEAD_DOWN, art.HEAD_UP, art.HEAD_COCKED, art.HEAD_TURNED,
        art.HEAD_AWAY, art.FRONT_HEAD, art.FRONT_HEAD_DOWN, art.FRONT_HEAD_TURN,
        art.FRONT_HEAD_BOWED, art.BACK_HEAD, art.CREST, art.CREST_RAISED, art.CREST_FLAT,
        art.FRONT_CREST, art.FRONT_CREST_RAISED, art.FRONT_CREST_FLAT,
    )
)  # fmt: skip
"""Heads and crests, as drawn: the scarf goes under the first of them."""

_MIDLINE = ANCHOR_COLUMN - PADDING
"""Art column the front view is symmetric about."""


def _same_art(layer: Layer, other: Layer) -> bool:
    return layer.rows == other.rows


def _is_head(layer: Layer) -> bool:
    if layer.rows in _HEADS:
        return True
    mirrored = layer.mirrored(_MIDLINE).rows
    return mirrored in _HEADS


def _scarf_for(layers: tuple[Layer, ...]) -> Layer | None:
    """The scarf for the body in ``layers``, placed where that body is."""
    for layer in layers:
        for body, scarf in _SCARVES:
            if _same_art(layer, body):
                return scarf.shifted(layer.x - body.x, layer.y - body.y)
    return None


_SLICKED = (
    (art.CREST, art.CREST_FLAT),
    (art.CREST_RAISED, art.CREST_FLAT),
    (art.FRONT_CREST, art.FRONT_CREST_FLAT),
    (art.FRONT_CREST_RAISED, art.FRONT_CREST_FLAT),
)


def _slicked(layer: Layer) -> Layer:
    """A crest laid flat by the wet, in the same place; anything else as it is."""
    for crest, flat in _SLICKED:
        for up, down in ((crest, flat), (crest.mirrored(_MIDLINE), flat.mirrored(_MIDLINE))):
            if _same_art(layer, up):
                # Keep the flat crest where the raised one's base was.
                return down.shifted(layer.x - up.x, layer.y - up.y)
    return layer


def layers_with(layers: tuple[Layer, ...], look: Look) -> tuple[Layer, ...]:
    """A pose's layers, with a slicked crest when damp and a scarf when wrapped up."""
    out = [_slicked(layer) for layer in layers] if look.damp else list(layers)
    scarf = _scarf_for(layers) if look.scarf else None
    if scarf is not None:
        # Over the body and wings, under his head (and crest), wherever they are.
        heads = [i for i, layer in enumerate(layers) if _is_head(layer)]
        out.insert(heads[0] if heads else len(out), scarf)
    return tuple(out)


def recoloured(frame: Frame, change: Mapping[RGBA, RGBA]) -> Frame:
    return Frame(
        frame.width, frame.height, tuple(change.get(p, p) if p else p for p in frame.pixels)
    )  # type: ignore[arg-type]


_WET_COLOURS: dict[RGBA, RGBA] = {}
for _key in PLUMAGE:
    _WET_COLOURS[PALETTE[_key]] = DAMP_PALETTE[_key]
    _WET_COLOURS[outline_for(PALETTE[_key])] = outline_for(DAMP_PALETTE[_key])


def dimmed(frame: Frame) -> Frame:
    return Frame(
        frame.width, frame.height, tuple(None if p is None else _dimmed(p) for p in frame.pixels)
    )


def frame_in(name: str, look: Look, frames: Mapping[str, Frame], custom: frozenset[str]) -> Frame:
    """Frame ``name`` with ``look`` on it. ``frames`` are the plain ones; ``custom``
    names those replaced from an Aseprite sheet."""
    if look == PLAIN:
        return frames[name]
    if (look.damp or look.scarf) and name in FRAME_LAYERS and name not in custom:
        frame = compose(
            (layer.shifted(PADDING, PADDING) for layer in layers_with(FRAME_LAYERS[name], look)),
            CANVAS_WIDTH,
            CANVAS_HEIGHT,
            DAMP_PALETTE if look.damp else PALETTE,
            outline_for,
        )
    elif look.damp:
        frame = recoloured(frames[name], _WET_COLOURS)
    else:
        frame = frames[name]
    return dimmed(frame) if look.dim else frame
