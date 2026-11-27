"""Named frames assembled from art layers, plus the canvas geometry they share."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from zengo.sprites import art
from zengo.sprites.compose import Frame, Layer, compose
from zengo.sprites.palette import PALETTE, RGBA, outline_for

ART_WIDTH = 52
ART_HEIGHT = 40
"""Size of the grid the art in :mod:`zengo.sprites.art` is drawn on."""

PADDING = 1
"""Clear border around the art so the generated outline is never clipped."""

CANVAS_WIDTH = ART_WIDTH + 2 * PADDING
CANVAS_HEIGHT = ART_HEIGHT + 2 * PADDING

GROUND_ROW = 28 + PADDING
"""Lowest row of the feet when perched. Rows below it only hold the flight downstroke."""

ANCHOR_COLUMN = 30 + PADDING
"""Column between the feet. The pet's x position refers to this column."""


def _shifted(dx: int, dy: int, *layers: Layer) -> tuple[Layer, ...]:
    return tuple(layer.shifted(dx, dy) for layer in layers)


_UPPER = (art.TAIL, art.BODY, art.WING_FOLDED, art.HEAD, art.CREST)
_FLYING_HEAD = _shifted(0, 9, art.CREST_FLAT, art.HEAD)
"""Head lowered to lead the level flying body, crest laid back in the airflow."""
_STARTLED_HEAD = _shifted(0, 9, art.CREST_RAISED, art.HEAD)

_PECKING_BODY = (art.LEGS, art.TAIL, art.BODY, art.WING_FOLDED)
_SITTING = _PECKING_BODY
_PUFFED = (art.LEGS, art.TAIL, art.BODY, art.PUFF, art.WING_FOLDED)
_HELD_BODY = (art.TAIL_HANGING, art.BODY, art.WING_FOLDED)
_HELD_HEAD = (art.HEAD, art.CREST_RAISED)

FRAME_LAYERS: Mapping[str, tuple[Layer, ...]] = {
    "perch": (art.LEGS, *_UPPER),
    "blink": (art.LEGS, *_UPPER, art.EYE_CLOSED),
    "alert": (art.LEGS, art.TAIL, art.BODY, art.WING_FOLDED, art.HEAD, art.CREST_RAISED),
    "step_back": (art.LEGS_STEP_BACK, *_shifted(0, -1, *_UPPER)),
    "step_front": (art.LEGS_STEP_FRONT, *_shifted(0, -1, *_UPPER)),
    # Head dips down and back towards the wing, eyes shutting on the nibble.
    "preen_a": (
        art.LEGS,
        art.TAIL,
        art.BODY,
        art.WING_FOLDED,
        *_shifted(-1, 2, art.CREST, art.HEAD),
    ),
    "preen_b": (
        art.LEGS,
        art.TAIL,
        art.BODY,
        art.WING_FOLDED,
        *_shifted(-3, 3, art.CREST, art.HEAD, art.EYE_CLOSED),
    ),
    "sleep": (
        art.LEGS,
        art.TAIL,
        art.BODY,
        art.PUFF,
        art.WING_FOLDED,
        *_shifted(-1, 2, art.CREST_FLAT, art.HEAD, art.EYE_CLOSED),
    ),
    # Held: hanging with wings folded, crest up. He kicks, blinks, looks down at
    # the ground and now and then flicks a wing.
    "held": (art.LEGS_DANGLE, *_HELD_BODY, *_HELD_HEAD),
    "held_blink": (art.LEGS_DANGLE, *_HELD_BODY, *_HELD_HEAD, art.EYE_CLOSED),
    "held_kick_a": (art.LEGS_KICK_FRONT, *_HELD_BODY, *_HELD_HEAD),
    "held_kick_b": (art.LEGS_KICK_BACK, *_HELD_BODY, *_HELD_HEAD),
    "held_look": (art.LEGS_DANGLE, *_HELD_BODY, art.HEAD_DOWN, art.CREST_RAISED.shifted(1, 1)),
    "held_flick": (art.LEGS_DANGLE, art.TAIL_HANGING, art.BODY, art.WING_HALF, *_HELD_HEAD),
    # Feathers puffed and the head shaken: turned towards you, back, and away.
    "shake_a": (*_PUFFED, art.HEAD_TURNED, art.CREST_RAISED),
    "shake_mid": (*_PUFFED, art.HEAD, art.CREST_RAISED),
    "shake_b": (*_PUFFED, art.HEAD_AWAY, art.CREST_RAISED.shifted(-1, 0)),
    # Petted: fluffed up, eyes shut, crest relaxed, tilting his head into the hand.
    "petted_a": (*_PUFFED, art.CREST_FLAT, art.HEAD, art.EYE_CLOSED),
    "petted_b": (*_PUFFED, art.CREST_FLAT.shifted(1, 1), art.HEAD_DOWN, art.EYE_CLOSED),
    # Bobbing his head along to your typing: it tips down, then dips a little.
    "bob_fwd": (*_SITTING, art.HEAD_DOWN, art.CREST.shifted(1, 1)),
    "bob": (*_SITTING, art.HEAD_DOWN.shifted(0, 1), art.CREST.shifted(1, 2)),
    # Keeping his balance on a moving window: crest up, leaning back, a wing out.
    "grip": (
        art.LEGS,
        art.TAIL,
        art.BODY,
        art.WING_HALF,
        *_shifted(-1, 1, art.CREST_RAISED, art.HEAD),
    ),
    # Whistling: crest up, head tipped back to sing with the beak open.
    "whistle_a": (*_SITTING, art.HEAD_UP, art.BEAK_OPEN_UP, art.CREST_RAISED.shifted(-1, 0)),
    "whistle_b": (*_SITTING, art.HEAD_UP, art.CREST_RAISED.shifted(-1, 0)),
    # Eating seeds off the ground: tipping forward, the beak reaching down to the
    # seeds, then back upright to crack one open, beak working, head level.
    "peck_down": (
        art.LEGS,
        art.BENT_BODY_DIP,
        art.HEAD_DOWN.shifted(3, 5),
        art.CREST_FLAT.shifted(4, 6),
    ),
    "peck_low": (
        art.LEGS,
        art.BENT_BODY,
        art.HEAD_DOWN.shifted(5, 11),
        art.CREST_FLAT.shifted(6, 12),
    ),
    "chew_a": (*_PECKING_BODY, art.HEAD, art.BEAK_OPEN, art.CREST),
    "chew_b": (*_PECKING_BODY, art.HEAD, art.CREST),
    # The downstroke lifts the body a pixel.
    "wings_up": (art.FLIGHT_BODY, art.WING_UP, *_FLYING_HEAD),
    "wings_level": (art.FLIGHT_BODY, art.WING_LEVEL, *_FLYING_HEAD),
    "wings_down": _shifted(0, -1, art.FLIGHT_BODY, art.WING_DOWN, *_FLYING_HEAD),
    "wings_recover": (art.FLIGHT_BODY, art.WING_RECOVER, *_FLYING_HEAD),
    # Startled off a perch: the same wingbeats with the crest shot up.
    "startle_up": (art.FLIGHT_BODY, art.WING_UP, *_STARTLED_HEAD),
    "startle_level": (art.FLIGHT_BODY, art.WING_LEVEL, *_STARTLED_HEAD),
    "startle_down": _shifted(0, -1, art.FLIGHT_BODY, art.WING_DOWN, *_STARTLED_HEAD),
    "startle_recover": (art.FLIGHT_BODY, art.WING_RECOVER, *_STARTLED_HEAD),
    "turn_up": (art.TURN_WINGS_UP, art.FRONT_FLY_BODY),
    "turn_down": (art.TURN_WINGS_DOWN, art.FRONT_FLY_BODY),
}


_MIDLINE = ANCHOR_COLUMN - PADDING
"""Art column the front view is symmetric about."""

_FRONT_UP = (art.FRONT_CREST, art.FRONT_HEAD)
_FRONT_SITTING = (art.FRONT_FEET, art.FRONT_BODY)
_FRONT_TURN_L = (art.FRONT_HEAD_TURN.mirrored(_MIDLINE),)
# Preening from the front: the head turns to a shoulder in profile, beak in the wing.
_PREEN_TO_SIDE = _shifted(-6, 5, art.CREST_FLAT, art.HEAD, art.EYE_CLOSED)

FRONT_LAYERS: Mapping[str, tuple[Layer, ...]] = {
    "front_perch": (*_FRONT_SITTING, *_FRONT_UP),
    "front_blink": (*_FRONT_SITTING, *_FRONT_UP, art.FRONT_EYES_CLOSED),
    "front_look_l": (*_FRONT_SITTING, *_FRONT_TURN_L, art.FRONT_CREST.shifted(-1, 0)),
    "front_look_r": (*_FRONT_SITTING, art.FRONT_HEAD_TURN, art.FRONT_CREST.shifted(1, 0)),
    "front_alert": (*_FRONT_SITTING, art.FRONT_CREST_RAISED, art.FRONT_HEAD),
    "front_preen_a": (*_FRONT_SITTING, *_PREEN_TO_SIDE),
    "front_preen_b": (*_FRONT_SITTING, *(layer.mirrored(_MIDLINE) for layer in _PREEN_TO_SIDE)),
    # A ruffle from the front: puffed up, the head turned one way, then the other.
    "front_fluff_a": (
        *_FRONT_SITTING,
        art.FRONT_PUFF,
        *_FRONT_TURN_L,
        art.FRONT_CREST_RAISED.shifted(-1, 0),
    ),
    "front_fluff_b": (
        *_FRONT_SITTING,
        art.FRONT_PUFF,
        art.FRONT_HEAD_TURN,
        art.FRONT_CREST_RAISED.shifted(1, 0),
    ),
    # Petted: eyes shut, crest relaxed, tilting his head down into the hand.
    "front_petted_a": (
        *_FRONT_SITTING,
        art.FRONT_PUFF,
        art.FRONT_CREST_FLAT,
        art.FRONT_HEAD,
        art.FRONT_EYES_CLOSED,
    ),
    "front_petted_b": (
        *_FRONT_SITTING,
        art.FRONT_PUFF,
        art.FRONT_CREST_FLAT.shifted(0, 1),
        art.FRONT_HEAD_DOWN,
        art.FRONT_EYES_CLOSED.shifted(0, 1),
    ),
    "front_bob": (*_FRONT_SITTING, art.FRONT_HEAD_DOWN, art.FRONT_CREST.shifted(0, 1)),
    "front_whistle_a": (
        *_FRONT_SITTING,
        art.FRONT_CREST_RAISED,
        art.FRONT_HEAD,
        art.FRONT_BEAK_OPEN,
    ),
    # Bowing his head to the dish (or the cage latch): the crown towards you.
    "front_peck": (*_FRONT_SITTING, art.FRONT_CREST_FLAT.shifted(0, 4), art.FRONT_HEAD_BOWED),
    # Cracking a seed: head level, beak working.
    "front_chew": (*_FRONT_SITTING, *_FRONT_UP, art.FRONT_BEAK_OPEN),
    "front_sleep": (
        *_FRONT_SITTING,
        art.FRONT_PUFF,
        *_shifted(0, 2, art.FRONT_CREST_FLAT, art.FRONT_HEAD, art.FRONT_EYES_CLOSED),
    ),
}
"""Facing you. On the ground the tail is hidden behind him."""

_BACK = (art.FRONT_FEET, art.BACK_BODY, art.BACK_TAIL)
BACK_LAYERS: Mapping[str, tuple[Layer, ...]] = {
    # Sulking with his back to you, now and then glancing over a shoulder.
    "sulk": (*_BACK, art.FRONT_CREST, art.BACK_HEAD),
    "sulk_peek": (*_BACK, *_shifted(-1, 0, art.FRONT_CREST, art.BACK_HEAD, art.BACK_PEEK)),
    "sulk_huff": (*_BACK, art.FRONT_PUFF, art.FRONT_CREST_RAISED, art.BACK_HEAD),
}

BRANCH_LAYERS: Mapping[str, tuple[Layer, ...]] = {
    name.replace("front_", "branch_"): (art.FRONT_TAIL, *layers)
    for name, layers in FRONT_LAYERS.items()
}
"""The same poses sitting on the branch, the tail hanging down behind it."""

LEDGE_FRAMES = frozenset(
    {
        *("perch", "blink", "alert", "sleep", "grip", "whistle_a", "whistle_b"),
        *("preen_a", "preen_b", "shake_a", "shake_mid", "shake_b"),
        *("petted_a", "petted_b", "bob_fwd", "bob"),
    }
)
"""The side-on poses he takes up sitting on something thin."""

LEDGE_LAYERS: Mapping[str, tuple[Layer, ...]] = {
    f"ledge_{name}": tuple(art.TAIL_PERCHED if layer is art.TAIL else layer for layer in layers)
    for name, layers in FRAME_LAYERS.items()
    if name in LEDGE_FRAMES
}
"""Side-on poses sitting on something thin (your pointer, a window's top edge), the
tail angled down past the perch instead of held out level."""

FRAME_LAYERS = {
    **FRAME_LAYERS,
    **FRONT_LAYERS,
    **BRANCH_LAYERS,
    **BACK_LAYERS,
    **LEDGE_LAYERS,
}


def build_frames(
    palette: Mapping[str, RGBA] = PALETTE,
    outline: Callable[[RGBA], RGBA] | None = outline_for,
) -> dict[str, Frame]:
    """Render every frame in :data:`FRAME_LAYERS`."""
    return {
        name: compose(
            (layer.shifted(PADDING, PADDING) for layer in layers),
            CANVAS_WIDTH,
            CANVAS_HEIGHT,
            palette,
            outline,
        )
        for name, layers in FRAME_LAYERS.items()
    }
