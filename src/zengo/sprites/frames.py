"""Named frames assembled from art layers, plus the canvas geometry they share."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from zengo.sprites import art
from zengo.sprites.compose import Frame, Layer, compose
from zengo.sprites.palette import PALETTE, RGBA, outline_for

ART_WIDTH = 26
ART_HEIGHT = 28
"""Size of the grid the art in :mod:`zengo.sprites.art` is drawn on."""

PADDING = 1
"""Clear border around the art so the generated outline is never clipped."""

CANVAS_WIDTH = ART_WIDTH + 2 * PADDING
CANVAS_HEIGHT = ART_HEIGHT + 2 * PADDING

GROUND_ROW = art.ORIGIN_Y + 22 + PADDING
"""Lowest row of the feet when perched. The tail may hang below it, over the panel edge."""

ANCHOR_COLUMN = art.ORIGIN_X + 10 + PADDING
"""Column between the feet. The pet's x position refers to this column."""


def _shifted(dy: int, *layers: Layer) -> tuple[Layer, ...]:
    return tuple(layer.shifted(0, dy) for layer in layers)


_HEAD = (art.CREST, art.HEAD)
_UPPER = (art.BODY, *_HEAD)
_FLYING_HEAD = (art.CREST_FLAT, art.HEAD)  # crest laid back in the airflow
_FLIGHT_DROP = 3

FRAME_LAYERS: Mapping[str, tuple[Layer, ...]] = {
    "perch": (art.LEGS, *_UPPER),
    "blink": (art.LEGS, *_UPPER, art.EYE_CLOSED),
    "alert": (art.LEGS, art.BODY, art.CREST_RAISED, art.HEAD),
    "step_back": (art.LEGS_STEP_BACK, *_shifted(-1, *_UPPER)),
    "step_front": (art.LEGS_STEP_FRONT, *_shifted(-1, *_UPPER)),
    # Head dips towards the chest feathers, eyes shutting on the nibble.
    "preen_a": (art.LEGS, art.BODY, *_shifted(1, *_HEAD)),
    "preen_b": (art.LEGS, art.BODY, *_shifted(2, *_HEAD, art.EYE_CLOSED)),
    "sleep": (art.LEGS, art.BODY, art.PUFF, *_shifted(1, art.CREST_FLAT, art.HEAD, art.EYE_CLOSED)),
    # Flight art is lowered so the tucked feet sit on the ground row: takeoff and
    # landing don't jump. The downstroke lifts the body a pixel; the far wing
    # shows only on the upstroke.
    "wings_up": _shifted(
        _FLIGHT_DROP, art.WING_UP_FAR, art.FLIGHT_BODY, art.WING_UP, *_FLYING_HEAD
    ),
    "wings_level": _shifted(_FLIGHT_DROP, art.FLIGHT_BODY, art.WING_LEVEL, *_FLYING_HEAD),
    "wings_down": _shifted(_FLIGHT_DROP - 1, art.FLIGHT_BODY, art.WING_DOWN, *_FLYING_HEAD),
    "wings_recover": _shifted(_FLIGHT_DROP, art.FLIGHT_BODY, art.WING_RECOVER, *_FLYING_HEAD),
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
