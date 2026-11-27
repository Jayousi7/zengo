"""Little things in the air around him: water droplets, snowflakes, falling leaves.

Each is a particle: a few art pixels moving under simple rules of its own kind.
Droplets fly out and fall fast; snowflakes and leaves drift down, swaying side to
side, and fade a moment after landing. They're only for looking at: nothing
touches them, and the app draws them all in one click-through window.

Pure Python: no Qt.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

KINDS = ("drop", "snow", "leaf")

MAX_PARTICLES = 80

GRAVITY = {"drop": 420.0, "snow": 0.0, "leaf": 0.0}
"""Art px/s² pulling each kind down. Snow and leaves fall at a steady drift instead."""

DRIFT = {"drop": 0.0, "snow": 14.0, "leaf": 22.0}
"""Art px/s they settle at, falling."""

SWAY = {"drop": 0.0, "snow": 6.0, "leaf": 14.0}
"""Art px either side they swing as they fall."""

LIFE = {"drop": 0.9, "snow": 30.0, "leaf": 30.0}
"""Seconds at most before one is gone, landed or not."""

FADE = 0.6
"""Seconds a landed particle takes to fade."""


@dataclass
class Particle:
    kind: str
    x: float
    y: float
    """Screen position."""
    vx: float = 0.0
    vy: float = 0.0
    """Screen px/s."""
    ground: float = math.inf
    """Screen y where it lands."""
    age: float = 0.0
    phase: float = 0.0
    """Where in its sway it starts."""
    landed: float | None = None
    """Seconds since it landed."""

    @property
    def alpha(self) -> float:
        """How solid it's drawn, 0 to 1: fading after landing, or at the end of its life."""
        if self.landed is not None:
            return max(0.0, 1.0 - self.landed / FADE)
        left = LIFE[self.kind] - self.age
        return max(0.0, min(1.0, left / FADE))

    @property
    def tilt(self) -> int:
        """For a leaf, which way it's tipped as it sways: -1, 0 or 1."""
        swing = math.cos(self.age * 2.4 + self.phase)
        return -1 if swing < -0.35 else 1 if swing > 0.35 else 0


@dataclass
class Effects:
    particles: list[Particle] = field(default_factory=list)

    def add(self, particle: Particle) -> None:
        if len(self.particles) >= MAX_PARTICLES:
            self.particles.pop(0)  # the oldest makes way
        self.particles.append(particle)

    def update(self, dt: float, scale: float) -> None:
        """Move each particle on by ``dt``; ``scale`` is screen px per art px."""
        kept = []
        for p in self.particles:
            p.age += dt
            if p.landed is not None:
                p.landed += dt
            else:
                p.vy += GRAVITY[p.kind] * scale * dt
                if DRIFT[p.kind]:
                    p.vy = DRIFT[p.kind] * scale
                    # Swaying: side to side about a slow drift of its own.
                    sway = SWAY[p.kind] * scale * math.cos(p.age * 2.4 + p.phase) * 2.4
                    p.x += (p.vx + sway) * dt
                else:
                    p.x += p.vx * dt
                p.y += p.vy * dt
                if p.y >= p.ground:
                    p.y, p.landed = p.ground, 0.0
            if p.alpha > 0 and p.age < LIFE[p.kind] + FADE:
                kept.append(p)
        self.particles = kept

    def clear(self) -> None:
        self.particles.clear()

    # --- Making them ---------------------------------------------------------------

    def splash(
        self, x: float, y: float, ground: float, rng: random.Random, scale: float, count: int = 6
    ) -> None:
        """Droplets thrown up and out from ``(x, y)``, falling to ``ground``."""
        for _ in range(count):
            angle = rng.uniform(-2.6, -0.5)  # upwards, either side
            speed = rng.uniform(40.0, 95.0) * scale
            self.add(
                Particle(
                    "drop", x, y, math.cos(angle) * speed, math.sin(angle) * speed, ground,
                    phase=rng.uniform(0, math.tau),
                )
            )  # fmt: skip

    def falling(
        self, kind: str, x: float, y: float, ground: float, rng: random.Random, drift: float = 0.0
    ) -> None:
        """A snowflake or leaf starting to fall from ``(x, y)``, drifting sideways at
        ``drift`` screen px/s."""
        self.add(Particle(kind, x, y, drift, 0.0, ground, phase=rng.uniform(0, math.tau)))
