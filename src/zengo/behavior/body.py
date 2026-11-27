"""The pet's physical state on the desktop."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Facing(IntEnum):
    """Horizontal direction; the value doubles as the sign of forward motion."""

    LEFT = -1
    RIGHT = 1


@dataclass
class Body:
    """Position in screen pixels.

    ``x`` is the point between the feet and ``y`` the bottom of the feet, so a
    grounded pet simply has ``y == ground``.
    """

    x: float
    y: float
    facing: Facing = Facing.RIGHT
    vx: float = 0.0
    vy: float = 0.0

    def face_towards(self, x: float) -> None:
        if x != self.x:
            self.facing = Facing.RIGHT if x > self.x else Facing.LEFT
