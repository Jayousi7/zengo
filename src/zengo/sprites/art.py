"""Zengo's pixel art, facing right.

Every pose is the perched bird plus small overlays: a shifted head, a different
crest, a wing swapped in. Keeping one base drawing means every frame stays on
model; only the parts that move are drawn again.

Layers are written in the perched bird's local grid and placed on the shared
canvas by :func:`_layer`, which leaves headroom for the raised crest and wings.
Outlines are generated (see :func:`zengo.sprites.palette.outline_for`), so only
fill colours are drawn here.

Palette keys: W face, P wing patch, L/B/S fawn light to shadow, C/D cinnamon,
T/t tail, K eye, Q/q beak, F feet. ``.`` keeps, ``_`` erases.
"""

from zengo.sprites.compose import Layer

ORIGIN_X, ORIGIN_Y = 9, 2
"""Canvas position of the local grid's (0, 0)."""


def _layer(art: str, x: int, y: int) -> Layer:
    return Layer.parse(art, ORIGIN_X + x, ORIGIN_Y + y)


# --- Base pose -------------------------------------------------------------

HEAD = _layer(
    """
    ...LLLWW
    ..LLLWWWW
    .LLLWWWKWQ
    .LLLWWWKWQq
    .BLLWWWWWq
    SBLLLWWWW
    """,
    x=5,
    y=6,
)

BODY = _layer(
    """
    ....SCCBLLLLLL
    ....SCCPBLLLLL
    ...SCCCPBLLLLLL
    ...SDCCPBBLLLLL
    ...SDCCPBBLLLLL
    ...SDDCPBBLLLL
    ...SDDCSBBBLLL
    ...SDDSSBBBB
    ...tDDSSBBBB
    ..tTDSS
    ..tTD
    .tTt
    .tTt
    tTt
    """,
    x=0,
    y=12,
)

LEGS = _layer(
    """
    FF.
    F.F
    """,
    x=9,
    y=21,
)

# --- Head and crest variants ----------------------------------------------

CREST = _layer(
    """
    .LL
    P..L
    ...LL
    ....LL.P
    ....LBL
    ...LLLL
    """,
    x=7,
    y=0,
)

CREST_RAISED = _layer(
    """
    ...L
    ..LL..P
    ..L..L
    .P.L.L
    ...LLL
    ...LBL
    ...LLL
    ..LLLL
    """,
    x=8,
    y=-2,
)

# Lowered and swept back against the head, as when relaxed or asleep.
CREST_FLAT = _layer(
    """
    .LL
    ..LLLL
    ....LLLL
    """,
    x=3,
    y=4,
)

EYE_CLOSED = _layer(
    """
    WW
    DD
    """,
    x=11,
    y=8,
)

# --- Walking ---------------------------------------------------------------
# The body bobs up a pixel on each step, so these legs are one row taller.

LEGS_STEP_BACK = _layer(
    """
    FF.
    F..
    FF.
    """,
    x=9,
    y=20,
)

LEGS_STEP_FRONT = _layer(
    """
    FF.
    .F.
    .FF
    """,
    x=9,
    y=20,
)

# --- Sleeping --------------------------------------------------------------

# Feathers fluffed out by a pixel around the chest and back. No breathing frame:
# a one-pixel chest pulse reads as a twitch at this size.
PUFF = _layer(
    """
    ............L
    ............L
    .............L
    S............L
    S............L
    S...........L
    S...........L
    ..........B
    ..........B
    """,
    x=2,
    y=12,
)


# --- Flying ----------------------------------------------------------------
# Body leaning forward with the tail streaming behind; the head and the
# laid-back crest are the perched ones. The near wing beats through three
# positions; long pointed wings are what read as a parrot rather than an insect.

FLIGHT_BODY = _layer(
    """
    ..........SSBBBBBBLLLLLL
    ....tTTTSSSBBBBBBBLLLLLL
    .ttTTTTTTSSBBBBBBBLLLLLL
    tttTTTTTTTSBBBBBBBLLLLL
    ..ttttTTTTSSBBBBBBLLLL
    ............SBBBBBLL
    ..............BBBBB
    ................FF
    """,
    x=-9,
    y=12,
)

WING_UP = _layer(
    """
    ..D.DS
    .DSDDSS
    DSDDSDDS
    .DDSDDSCC
    .DSDDSCCSC
    .DDDSCCSCC
    ..DSCCSCCSP
    ...SCSCCSCCP
    ....SCCCCCCCP
    ....SCCCCCCCP
    .....SCCCCCCCP
    ......SCCCCCCCP
    .......SCCCCCCP
    """,
    x=-6,
    y=0,
)

WING_UP_FAR = _layer(
    """
    ..tDDD
    .tDDDDD
    tDDDDDDD
    .DDDDDDDD
    .tDDDDDDD
    ..tDDDDDDD
    ...tDDDDDDD
    ....tDDDDDD
    .....tDDDDDD
    ......tDDDDDD
    .......tDDDDDD
    ........tDD
    """,
    x=-9,
    y=2,
)

WING_LEVEL = _layer(
    """
    SSSSSSCC
    ..DDSDCSCCP
    ..DSDCSCCCCPPP
    ...DDSCCSCCCCCPPP
    .....SSSCCCCCCSSS
    ........SSSSSS
    """,
    x=-9,
    y=7,
)

WING_DOWN = _layer(
    """
    ....SCCCCCCP
    ....SCCCCCP
    ...SCCCCCCP
    ..SCCCCCCP
    ..SCSCCCP
    .SCSCCSCC
    .DSCCSCC
    DSDDSCC
    SDDSDDS
    DDSDDS
    .D.S
    """,
    x=-3,
    y=13,
)

WING_RECOVER = _layer(
    """
    .SSS
    SDSDCC
    DSDDSCP
    .DDSCCCPP
    .DSCCCCCCPP
    ..SCSCCCSSSP
    ...SSSSS
    """,
    x=-3,
    y=6,
)
