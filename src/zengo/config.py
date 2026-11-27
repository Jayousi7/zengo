"""Tunables. Distances and speeds are in art pixels so they hold at any scale."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    scale: int = 2
    """Screen pixels per art pixel."""

    fps: int = 30

    walk_speed: float = 10.0
    """Average art pixels per second; a slow cockatiel waddle of about 2.5 px per step."""

    fly_speed: float = 110.0
    gravity: float = 500.0
    max_fall_speed: float = 140.0
    """Fluttering caps the fall speed; Zengo never drops like a stone."""

    idle_seconds: tuple[float, float] = (3.0, 9.0)
    """How long Zengo idles before choosing something else to do."""

    watch_radius: float = 140.0
    """Within this horizontal distance of the cursor, Zengo turns to look at it."""

    sleep_after: float = 300.0
    """Seconds of user inactivity after which Zengo becomes sleepy."""

    night: tuple[int, int] = (23, 6)
    """Local hours [start, end) during which Zengo naps readily, wrapping midnight."""

    edge_margin: float = 11.0
    """Art pixels kept between the anchor and a screen edge; the tail reaches this far back."""

    drag_threshold: int = 4
    """Screen pixels the mouse must move while pressed before a click becomes a drag."""

    def px(self, art_pixels: float) -> float:
        return art_pixels * self.scale

    def is_night(self, hour: int) -> bool:
        start, end = self.night
        return start <= hour or hour < end if start > end else start <= hour < end
