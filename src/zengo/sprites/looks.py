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
    ART_HEIGHT,
    ART_WIDTH,
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
# Red wool round his neck: a band across his throat, lighter along the top and
# darker underneath so it reads as rolled wool, and the loose end trailing back
# over his wing (or hanging down, from the front). It goes with his head, as a
# scarf on a neck does, and is only ever drawn where he is already drawn: it
# never changes his outline, so he never looks cut in two and his chest never
# pokes out, whatever his head is doing.

_SIDE_SCARF = Layer.parse(
    """
    .RRRRRRRR
    ..rrrrrrrr
    RR
    rR
    .r
    """,
    x=30,
    y=15,
)
"""For a side-on head where :data:`art.HEAD` is drawn."""

_FLYING_SCARF = Layer.parse(
    """
    ......RR
    rRRRRRrR
    .rrrr.Rr
    ......rR
    ......Rr
    ......rr
    """,
    x=24,
    y=18,
)
"""Flying, his head leads the level body: the band rings the neck behind it, the
loose end streaming back along his shoulders. For the head lowered to fly."""

_FRONT_SCARF = Layer.parse(
    """
    .RRRRRRR
    rrrrrrrrr
    .....Rr
    .....rR
    ......r
    """,
    x=26,
    y=15,
)
"""Facing you (or turned away): across the bottom of the face, the end down his chest."""

_BENT_SCARVES = (
    (
        art.BENT_BODY_DIP,
        Layer.parse(
            """
            ....R
            ...Rr
            ..Rr.
            .Rr..
            Rr...
            """,
            x=31,
            y=15,
        ),
    ),
    (
        art.BENT_BODY,
        Layer.parse(
            """
            ....R
            ...Rr
            ..Rr.
            .Rr..
            Rr...
            """,
            x=33,
            y=18,
        ),
    ),
)
"""Bent over pecking, his neck reaches down and forward to his head: the scarf
goes across it there (placed for each bent body where its art puts it)."""

_SIDE_HEADS = (
    art.HEAD, art.HEAD_DOWN, art.HEAD_UP, art.HEAD_COCKED, art.HEAD_TURNED, art.HEAD_AWAY,
)  # fmt: skip
_FRONT_HEADS = (
    art.FRONT_HEAD, art.FRONT_HEAD_DOWN, art.FRONT_HEAD_TURN, art.BACK_HEAD,
    art.FRONT_HEAD_BOWED.shifted(0, -3),  # drawn three rows lower: its neck is too
)  # fmt: skip
_FLYING_LOWERED = 9
"""Rows the head is lowered to lead the flying body (see ``frames._FLYING_HEAD``)."""
_MIDLINE = ANCHOR_COLUMN - PADDING
"""Art column the front view is symmetric about."""


def _same_art(layer: Layer, other: Layer) -> bool:
    return layer.rows == other.rows


def _scarf_for(layer: Layer, flying: bool) -> Layer | None:
    """The scarf round the neck of ``layer``, if it's a head (or the front-on
    flying body, whose head is part of it), placed with it."""
    if flying and _same_art(layer, art.HEAD):
        lowered = layer.y - art.HEAD.y
        if lowered in (_FLYING_LOWERED - 1, _FLYING_LOWERED):  # (the downstroke lifts it)
            return _FLYING_SCARF.shifted(layer.x - art.HEAD.x, lowered - _FLYING_LOWERED)
    for heads, scarf in ((_SIDE_HEADS, _SIDE_SCARF), (_FRONT_HEADS, _FRONT_SCARF)):
        for head in heads:
            for candidate, wrap in (
                (head, scarf),
                (head.mirrored(_MIDLINE), scarf.mirrored(_MIDLINE)),
            ):
                if _same_art(layer, candidate):
                    return wrap.shifted(layer.x - candidate.x, layer.y - candidate.y)
    if _same_art(layer, art.FRONT_FLY_BODY):
        fly = art.FRONT_FLY_BODY
        return _FRONT_SCARF.shifted(layer.x - fly.x, layer.y - fly.y + 5)
    return None


def _within(scarf: Layer, layers: tuple[Layer, ...]) -> Layer:
    """``scarf`` with every pixel that would fall outside him left out."""
    drawn = compose(layers, ART_WIDTH, ART_HEIGHT, PALETTE)
    rows = []
    for r, row in enumerate(scarf.rows):
        y = scarf.y + r
        rows.append(
            "".join(
                key
                if key != "." and 0 <= (x := scarf.x + i) < ART_WIDTH and 0 <= y < ART_HEIGHT
                and drawn.pixel(x, y) is not None
                else "."
                for i, key in enumerate(row)
            )
        )  # fmt: skip
    return Layer(tuple(rows), scarf.x, scarf.y)


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
    if look.scarf:
        flying = any(_same_art(layer, art.FLIGHT_BODY) for layer in layers)
        placed = [(i, s) for i, layer in enumerate(layers) if (s := _scarf_for(layer, flying))]
        for body, scarf in _BENT_SCARVES:
            for layer in layers:
                if _same_art(layer, body) and placed:
                    bent = scarf.shifted(layer.x - body.x, layer.y - body.y)
                    placed = [(placed[-1][0], bent)]
        if placed:
            index, scarf = placed[-1]
            # Over his head's lower edge, under anything drawn on it after (an
            # open beak, closed eyes), and never outside him.
            out.insert(index + 1, _within(scarf, tuple(out)))
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
