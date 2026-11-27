"""Named frames assembled from art layers, plus the canvas geometry they share."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from zengo.sprites import art
from zengo.sprites.compose import Frame, Layer, compose
from zengo.sprites.palette import PALETTE, RGBA, outline_for

ART_WIDTH = 52
ART_HEIGHT = 34
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

_PECKING_BODY = (art.LEGS, art.TAIL, art.BODY, art.WING_FOLDED)
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
    "held_look": (art.LEGS_DANGLE, *_HELD_BODY, *_shifted(1, 2, *_HELD_HEAD)),
    "held_flick": (art.LEGS_DANGLE, art.TAIL_HANGING, art.BODY, art.WING_HALF, *_HELD_HEAD),
    # Feathers puffed and the head shaken side to side, settling after a landing.
    "shake_a": (
        art.LEGS,
        art.TAIL,
        art.BODY,
        art.PUFF,
        art.WING_FOLDED,
        *_shifted(-1, 0, art.HEAD, art.CREST_RAISED),
    ),
    "shake_b": (
        art.LEGS,
        art.TAIL,
        art.BODY,
        art.PUFF,
        art.WING_FOLDED,
        *_shifted(1, 0, art.HEAD, art.CREST_RAISED),
    ),
    # Petted: fluffed up, eyes shut, crest relaxed, leaning into the hand.
    "petted_a": (
        art.LEGS,
        art.TAIL,
        art.BODY,
        art.PUFF,
        art.WING_FOLDED,
        *_shifted(0, 1, art.CREST_FLAT, art.HEAD, art.EYE_CLOSED),
    ),
    "petted_b": (
        art.LEGS,
        art.TAIL,
        art.BODY,
        art.PUFF,
        art.WING_FOLDED,
        *_shifted(-1, 2, art.CREST_FLAT, art.HEAD, art.EYE_CLOSED),
    ),
    # Bobbing his head along to your typing: a quick nod down and forward.
    "bob": (
        art.LEGS,
        art.TAIL,
        art.BODY,
        art.WING_FOLDED,
        *_shifted(1, 1, art.CREST, art.HEAD),
    ),
    # Whistling: crest up, nodding to the tune with the beak open. The head nods
    # down into the body, so no gap can open at the neck.
    "whistle_a": (
        art.LEGS,
        art.TAIL,
        art.BODY,
        art.WING_FOLDED,
        *_shifted(1, 1, art.CREST_RAISED, art.HEAD, art.BEAK_OPEN),
    ),
    # Eating seeds off the ground: the head dips to peck one up, then comes back up
    # to crack it, beak working.
    "peck_down": (*_PECKING_BODY, *_shifted(5, 9, art.CREST_FLAT, art.HEAD)),
    "peck_low": (*_PECKING_BODY, *_shifted(6, 11, art.CREST_FLAT, art.HEAD)),
    "chew_a": (*_PECKING_BODY, *_shifted(2, 3, art.CREST, art.HEAD, art.BEAK_OPEN)),
    "chew_b": (*_PECKING_BODY, *_shifted(2, 3, art.CREST, art.HEAD)),
    # The downstroke lifts the body a pixel.
    "wings_up": (art.FLIGHT_BODY, art.WING_UP, *_FLYING_HEAD),
    "wings_level": (art.FLIGHT_BODY, art.WING_LEVEL, *_FLYING_HEAD),
    "wings_down": _shifted(0, -1, art.FLIGHT_BODY, art.WING_DOWN, *_FLYING_HEAD),
    "wings_recover": (art.FLIGHT_BODY, art.WING_RECOVER, *_FLYING_HEAD),
    "turn_up": (art.TURN_WINGS_UP, art.FRONT_FLY_BODY),
    "turn_down": (art.TURN_WINGS_DOWN, art.FRONT_FLY_BODY),
}


_MIDLINE = ANCHOR_COLUMN - PADDING
"""Art column the front view is symmetric about."""

_FRONT_UP = (art.FRONT_CREST, art.FRONT_HEAD)
_FRONT_SITTING = (art.FRONT_FEET, art.FRONT_BODY)
# Preening from the front: the head turns to a shoulder in profile, beak in the wing.
_PREEN_TO_SIDE = _shifted(-6, 5, art.CREST_FLAT, art.HEAD, art.EYE_CLOSED)

FRONT_LAYERS: Mapping[str, tuple[Layer, ...]] = {
    "front_perch": (*_FRONT_SITTING, *_FRONT_UP),
    "front_blink": (*_FRONT_SITTING, *_FRONT_UP, art.FRONT_EYES_CLOSED),
    "front_look_l": (*_FRONT_SITTING, *_shifted(-1, 0, *_FRONT_UP)),
    "front_look_r": (*_FRONT_SITTING, *_shifted(1, 0, *_FRONT_UP)),
    "front_alert": (*_FRONT_SITTING, art.FRONT_CREST_RAISED, art.FRONT_HEAD),
    "front_preen_a": (*_FRONT_SITTING, *_PREEN_TO_SIDE),
    "front_preen_b": (*_FRONT_SITTING, *(layer.mirrored(_MIDLINE) for layer in _PREEN_TO_SIDE)),
    "front_fluff_a": (
        *_FRONT_SITTING,
        art.FRONT_PUFF,
        *_shifted(-1, 0, art.FRONT_CREST_RAISED, art.FRONT_HEAD),
    ),
    "front_fluff_b": (
        *_FRONT_SITTING,
        art.FRONT_PUFF,
        *_shifted(1, 0, art.FRONT_CREST_RAISED, art.FRONT_HEAD),
    ),
    "front_petted_a": (
        *_FRONT_SITTING,
        art.FRONT_PUFF,
        *_shifted(-1, 1, art.FRONT_CREST_FLAT, art.FRONT_HEAD, art.FRONT_EYES_CLOSED),
    ),
    "front_petted_b": (
        *_FRONT_SITTING,
        art.FRONT_PUFF,
        *_shifted(1, 1, art.FRONT_CREST_FLAT, art.FRONT_HEAD, art.FRONT_EYES_CLOSED),
    ),
    "front_bob": (*_FRONT_SITTING, *_shifted(0, 1, art.FRONT_CREST, art.FRONT_HEAD)),
    "front_whistle_a": (
        *_FRONT_SITTING,
        *_shifted(0, 1, art.FRONT_CREST_RAISED, art.FRONT_HEAD, art.FRONT_BEAK_OPEN),
    ),
    "front_peck": (*_FRONT_SITTING, *_shifted(0, 4, art.FRONT_CREST, art.FRONT_HEAD)),
    "front_chew": (
        *_FRONT_SITTING,
        *_shifted(0, 1, art.FRONT_CREST, art.FRONT_HEAD, art.FRONT_BEAK_OPEN),
    ),
    "front_sleep": (
        *_FRONT_SITTING,
        art.FRONT_PUFF,
        *_shifted(0, 2, art.FRONT_CREST_FLAT, art.FRONT_HEAD, art.FRONT_EYES_CLOSED),
    ),
}
"""Facing you. On the ground the tail is hidden behind him."""

BRANCH_LAYERS: Mapping[str, tuple[Layer, ...]] = {
    name.replace("front_", "branch_"): (art.FRONT_TAIL, *layers)
    for name, layers in FRONT_LAYERS.items()
}
"""The same poses sitting on the branch, the tail hanging down behind it."""

FRAME_LAYERS = {**FRAME_LAYERS, **FRONT_LAYERS, **BRANCH_LAYERS}


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
