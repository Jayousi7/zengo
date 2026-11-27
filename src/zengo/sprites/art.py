"""Zengo's pixel art, facing right, on a 42x34 grid.

Proportions follow a real cockatiel in side view: a small white-faced head with
a tall crest, a slim body sloping back, and a tail as long as the rest of him.
Rows below the ground row are left free for the wing's downstroke in flight.

Every perched pose is the base drawing plus small overlays: a shifted head, a
different crest, closed eyes. Flight has its own level body, with the head
moved forward and one of four wing positions on top. Layers are written in
grid coordinates. Outlines are generated (see
:func:`zengo.sprites.palette.outline_for`), so only fill colours are drawn here.

Palette keys: W face, P wing patch, L/B/S fawn light to shadow, C/D cinnamon,
T/t tail, K eye, Q/q beak, F feet. ``.`` keeps, ``_`` erases.
"""

from zengo.sprites.compose import Layer


def _layer(art: str, x: int, y: int) -> Layer:
    return Layer.parse(art, x, y)


# --- Base pose -------------------------------------------------------------

HEAD = _layer(
    """
    ....LWWWW
    ...LLWWWWW
    ..BLWWWWWW
    ..BLLWWWWW
    ..BLLWWKWW
    ..BBLWWWWQQ
    .SBBLWWWWQq
    SBBBLLWWW.q
    """,
    x=30,
    y=8,
)

BODY = _layer(
    """
    .............................SCCBBBLLWWW
    ...........................SCCCBBBBLLLLL
    .........................SCCCCBBBBBLLLLL
    .......................SCCCCCBBBBBBLLLLL
    .....................SCCCCCCBBBBBBBLLLLL
    ..............TTTTTTTSCCCBBBBBBBBBLLLLL
    ......ttTTTTTTTTTTTTSSCBBBBBBBBBBBLLLL
    ttttttTTTTTTTTTTTTTTSSBBBBBBBBBBBLLL
    ....ttttttttttttttttSSSBBBBBBBBBBBBB
    ............tttttttttSSSSSBBBBBBBB
    ..........................SSSSSSS
    """,
    x=0,
    y=16,
)

# The white covert patch shows as a stripe along the lower edge of the folded wing.
WING_FOLDED = _layer(
    """
    ................SC
    ..............SCCCC
    ............SDCCCCCC
    ..........SDDCCCCCCC
    ........SDDDCCCCCCCC
    ......SDDDDCCCCCPPPP
    ....SDDDDDDPPPPPPPS
    ..SDDDDDDSSSSSSS
    DDDDDD
    """,
    x=13,
    y=15,
)

LEGS = _layer(
    """
    .F..F
    FF.FF
    """,
    x=28,
    y=27,
)

# --- Head and crest variants ----------------------------------------------

# Relaxed: three strands curling forward.
CREST = _layer(
    """
    ......B
    ...B.B
    .B.B.L
    B.L.L
    L.L.L
    LLLLL
    LLLLL
    """,
    x=34,
    y=1,
)

# Alert: strands fanned up and out.
CREST_RAISED = _layer(
    """
    ....B...B
    B...B...B
    .B..B..B
    .L..L..L
    ..L.L.L
    ..L.L.L
    ..LLLLL
    ..LLLLL
    """,
    x=32,
    y=0,
)

# Laid back along the head, as when asleep or in flight.
CREST_FLAT = _layer(
    """
    BBLLLL
    ..LLL
    """,
    x=29,
    y=7,
)

EYE_CLOSED = _layer(
    """
    DD
    """,
    x=36,
    y=12,
)

# --- Walking ---------------------------------------------------------------
# The body bobs up a pixel on each step, so these legs are one row taller.

LEGS_STEP_BACK = _layer(
    """
    ..F..F
    FF...F
    ....FF
    """,
    x=27,
    y=26,
)

LEGS_STEP_FRONT = _layer(
    """
    .F..F
    .F...FF
    FF
    """,
    x=28,
    y=26,
)

# --- Sleeping --------------------------------------------------------------

# Feathers fluffed out by a pixel around the chest and back.
PUFF = _layer(
    """
    ........S...........L
    ......S.............L
    ....S...............L
    ..S.................L
    S...................L
    ...................L
    ..................L
    ................L
    ................B
    ..............BB
    """,
    x=20,
    y=16,
)


# --- Held and shaking -----------------------------------------------------
# Picked up: legs hang free and kick now and then; the near wing flicks half open.

LEGS_DANGLE = _layer(
    """
    .F..F
    .F..F
    .FF.FF
    """,
    x=28,
    y=27,
)

LEGS_KICK_FRONT = _layer(
    """
    .F..F
    .F...F
    .FF...FF
    """,
    x=28,
    y=27,
)

LEGS_KICK_BACK = _layer(
    """
    .F..F
    F...F
    FF..FF
    """,
    x=27,
    y=27,
)

WING_HALF = _layer(
    """
    D.D
    SDDD
    .SDDDD
    ..SDDDDD
    ...SDDDDCC
    .....SDDCCCCP
    .......SDCCCCPPP
    .........SCCCCPPPP
    ...........SSCCCPPP
    ..............SSCPP
    """,
    x=13,
    y=8,
)

# --- Flying ----------------------------------------------------------------
# Stretched level with the legs hanging, so the feet are on the ground row at
# takeoff and landing. The wing is long, joins just behind the head and ends in
# fanned primaries; the white patch shows by the shoulder. Only the near wing
# is drawn: from the side the far one is hidden behind the body.

FLIGHT_BODY = _layer(
    """
    .....................SCCCCCCCCC
    ...............ttTTSSCCCCCCCCCCCB
    .....tttTTTTTTTTTTSSCCCCCCCCBBBBB
    tttttTTTTTTTTTTTTTSSBBBBBBBBBBBBBB
    ....tttttttttttTTTTSSBBBBBBBBBBBBBLL
    ............tttttttSSSBBBBBBBBBBBLLLLL
    ....................SSBBBBBBBBBLLLL
    ........................SSSSBBBBBB
    .............................F
    ............................FF
    """,
    x=0,
    y=19,
)

WING_UP = _layer(
    """
    ......D
    .....DD
    ....DDD..D
    ...SDDD.DD
    ..SDDDDDDD
    ...DDDDDDD
    ..SDDDDDDDC
    .SDDDDDDDCC
    ..DDDDDDCCC
    .SDDDDDCCCCP
    SDDDDDCCCCCP
    .SDDDCCCCCCPP
    ..SDCCCCCCCPP
    .SSCCCCCCCCPP
    ..SCCCCCCCPPP
    ...SCCCCCCPPP
    ....SCCCCCPPPP
    .....SCCCCPPPP
    .......SCCPPPP
    """,
    x=18,
    y=1,
)

WING_LEVEL = _layer(
    """
    DD
    .DDDDDDCCCCCCCPPPPPP
    ..SDSDDDCCCCCCCCCPPP
    ....S.SDSDCCCCCCCCCCP
    ..........SSSSCCCCCC
    """,
    x=13,
    y=17,
)

WING_DOWN = _layer(
    """
    ........SCCCPPPP
    .......SCCCPPPPP
    ......SCCCCPPPPC
    ......SCCCCPPCC
    .....SCCCCCCCCC
    .....SDCCCCCCD
    ....SDDCCCCCDD
    ....SDDDCCCDD
    ...SDDDDDDDD
    ..SDDDDDDD.D
    .SDDDDDD.D
    .SDD.DD.D
    SD.D..D
    D..D
    """,
    x=17,
    y=20,
)

WING_RECOVER = _layer(
    """
    D
    SDD
    .SDDD.D
    ..SDDDDD
    ...SDDDDCC
    ....SDDCCCCP
    .....SSCCCCPPP
    .......SSCCCPPPP
    .........SSCCPPP
    """,
    x=16,
    y=11,
)
