"""Zengo's pixel art, facing right, on a 52x34 grid.

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
    .....................SCCCBBBBBBBBBLLLLL
    ....................SSCBBBBBBBBBBBLLLL
    ....................SSBBBBBBBBBBBLLL
    ....................SSSBBBBBBBBBBBBB
    .....................SSSSSBBBBBBBB
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

# The tail is its own layer so it can hang differently by pose. Standing, it
# carries on the line of the back with a gentle droop, held clear of the ground.

TAIL = _layer(
    """
    ...................TT
    ................TTTTT
    ............TTTTTTTTT
    .........TTTTTTTTTttt
    .....TTTTTTTttttttttt
    ..tttTttttttttttttttt
    tttttttttt
    """,
    x=0,
    y=20,
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

# Whistling: the beak a little open.
BEAK_OPEN = _layer(
    """
    K.
    Qq
    """,
    x=39,
    y=14,
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

# Held: the tail hangs down under its own weight.

TAIL_HANGING = _layer(
    """
    ...........T
    .........TTTT
    ........TTTTt
    .......TTTTttt
    ......TTTTtttt
    .....TTTtttt
    ....TTTtttt
    ...TTTttt
    ..TTttt
    .tTtt
    ttt
    t
    """,
    x=8,
    y=21,
)


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


# --- Turning in the air ------------------------------------------------------
# Banking round, he shows his front for a moment with both wings spread. Drawn
# symmetric about the anchor column, so it looks the same facing either way and
# bridges the side views without a jump.

# Face, tucked feet and the tail tip showing below.
FRONT_FLY_BODY = _layer(
    """
    ...B.B
    ..LLLLL
    .LWWWWWL
    .WWWWWWW
    .WKWWWKW
    .WWWQWWW
    .LWQQqWL
    .BLWqWLB
    SBLLLLLBS
    SBLLLLLBS
    SBBLLLBBS
    .SBBLBBS
    .SSBBBSS
    ..tTTTt
    ...F.F
    ...F.F
    """,
    x=26,
    y=13,
)


# Both wings raised in a V.
TURN_WINGS_UP = _layer(
    """
    D.....................................D
    DDD.................................DDD
    .DDD...............................DDD
    ..DDDD...........................DDDD
    ...DDDD.........................DDDD
    ....S.CCC.....................CCC.S
    .....SCCCCC.................CCCCCS
    .....SSCCCPP...............PPCCCSS
    ......SSCCPPPP...........PPPPCCSS
    .......SSCCPPPP.........PPPPCCSS
    ........SSCCCPPPP.....PPPPCCCSS
    ..........SCBBPPPP...PPPPBBCS
    ...........SBBBPP.....PPBBBS
    ............SBBB.......BBBS
    .............SB.........BS
    """,
    x=11,
    y=8,
)


# Both wings swept down.
TURN_WINGS_DOWN = _layer(
    """
    ...........PP.........PP
    ..........PPPP.......PPPP
    .........PPPPB.......BPPPP
    ........PPPBBBB.....BBBBPPP
    .......CPPCCBBSS...SSBBCCPPC
    .....CCCCCCCSS.......SSCCCCCCC
    ....CCCCCCSS...........SSCCCCCC
    ...DDCCCSS...............SSCCCDD
    ..DDD.SS...................SS.DDD
    .DDD.S.......................S.DDD
    D.S.............................S.D
    SS...............................SS
    """,
    x=13,
    y=19,
)


# --- Front view --------------------------------------------------------------
# Facing you, drawn symmetric about the anchor column so it is the same either
# way he was facing. Used sitting on the branch and now and then on the ground.

# Crest from the front: a fan of strands, the middle one tallest.
FRONT_CREST = _layer(
    """
    ...B
    ...B
    B..B..B
    .B.L.B
    .L.L.L
    ..LLL
    .LLLLL
    LLLLLLL
    """,
    x=27,
    y=0,
)


# Startled: the strands flare up and out.
FRONT_CREST_RAISED = _layer(
    """
    B...B...B
    B...B...B
    .B..B..B
    .L..L..L
    ..L.L.L
    ...LLL
    ..LLLLL
    .LLLLLLL
    """,
    x=26,
    y=0,
)


# Asleep: only a tuft shows.
FRONT_CREST_FLAT = _layer(
    """
    ..B.B
    LLLLLLL
    """,
    x=27,
    y=6,
)


# White face, an eye on each side, beak in the middle.
FRONT_HEAD = _layer(
    """
    .LWWWWWL
    LWWWWWWWL
    WWWWWWWWW
    WKWWWWWKW
    WWWWQWWWW
    LWWQQqWWL
    .LWWqWWL
    .BLWWWLB
    """,
    x=26,
    y=8,
)


FRONT_EYES_CLOSED = _layer(
    """
    WDD...DDW
    """,
    x=26,
    y=11,
)


# Chest, and the folded wings at the sides with the white patch showing.
FRONT_BODY = _layer(
    """
    .CBLLLLLLLBC
    SCBLLLLLLLBCS
    SCPBLLLLLBPCS
    SCPBLLLLLBPCS
    SDCPBLLLBPCDS
    SDCCBLLLBCCDS
    SDDCBBLBBCDDS
    .SDDBBBBBDDS
    .SDDSBBBSDDS
    ..SDSBBBSDS
    ...SSBBBSS
    """,
    x=24,
    y=16,
)


# Feathers fluffed out by a pixel each side.
FRONT_PUFF = _layer(
    """
    S.............S
    S.............S
    S.............S
    S.............S
    S.............S
    S.............S
    .S...........S
    .S...........S
    """,
    x=23,
    y=17,
)


FRONT_FEET = _layer(
    """
    .F...F
    FFF.FFF
    """,
    x=27,
    y=27,
)


# Seen from the front on the branch, the tail hangs down behind it.
FRONT_TAIL = _layer(
    """
    tTt
    tTt
    tTt
    tTt
    tTt
    .t
    """,
    x=29,
    y=27,
)


FRONT_BEAK_OPEN = _layer(
    """
    QKq
    .q
    """,
    x=29,
    y=13,
)
