"""Food put out for Zengo: a pile of sunflower seeds, his favourite."""

from __future__ import annotations

from dataclasses import dataclass

from zengo.sprites.food import MAX_SEEDS

PECK_REACH = 16
"""Art px from his anchor to the tip of his beak when he pecks at the ground."""

SECONDS_PER_SEED = 1.04
"""One seed: peck it up, crack it, swallow (the length of the eating clips)."""


@dataclass
class Food:
    x: float
    """Screen x of the middle of the pile."""
    y: float
    """Screen y of what it rests on: the ground, or the cage's tray."""
    seeds: int = MAX_SEEDS
    in_cage: bool = False
