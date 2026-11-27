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

    drag_stiffness: float = 140.0
    """Spring constant (1/s²) pulling a held Zengo towards the cursor. With gravity
    it lets him sag a few pixels and swing as he is moved."""

    drag_damping: float = 12.0
    """Damping (1/s) on that spring: low enough to swing, high enough to settle."""

    struggle_speed: float = 120.0
    """Moved faster than this while held, Zengo flaps in protest."""

    max_throw_speed: float = 400.0
    """Fastest a throw can send him; a wild fling of the mouse shouldn't turn him into a missile."""

    air_drag: float = 1.5
    """Rate (1/s) at which a thrown Zengo loses horizontal speed."""

    glide_speed: float = 90.0
    """Speed of the glide that brings him down after being dropped or thrown."""

    idle_seconds: tuple[float, float] = (3.0, 9.0)
    """How long Zengo idles before choosing something else to do."""

    watch_radius: float = 140.0
    """Within this horizontal distance of the cursor, Zengo turns to look at it."""

    cursor_rest: tuple[float, float] = (2.0, 90.0)
    """Seconds the mouse must have rested (at least, at most) before Zengo may fly
    up to perch on the pointer. Past the upper bound you've probably left the desk."""

    cursor_reach: float = 400.0
    """Art pixels: how far away a resting pointer can be for him to fly over to it."""

    branch_every: tuple[float, float] = (600.0, 1200.0)
    """Seconds between one branch withdrawing and the next growing out."""

    branch_stays: tuple[float, float] = (180.0, 300.0)
    """Seconds a branch stays out if Zengo leaves it alone."""

    branch_linger: tuple[float, float] = (20.0, 40.0)
    """Seconds it stays after he leaves it, at least."""

    branch_grow_seconds: float = 1.2
    """Time to grow out from the edge, and to withdraw."""

    branch_height: tuple[float, float] = (0.25, 0.6)
    """Where it grows, as a share of the screen height from the top."""

    branch_visit: tuple[float, float] = (40.0, 150.0)
    """Seconds Zengo sits on the branch before flying off."""

    whistles: tuple[str, ...] = (
        "♪ fweet-fweet! ♪",
        "♫ wheee-ooo! ♫",
        "♪ tu-tu-tweeet ♪",
        "Zengo! ♪",
        "pretty bird! ♫",
        "♪ ♫ ♪",
    )
    """What a double-click gets out of him, shown in a cloud above his head."""

    speech_seconds: float = 2.6
    """How long a whistle's cloud stays up."""

    sleep_after: float = 300.0
    """Seconds of user inactivity after which Zengo becomes sleepy."""

    night: tuple[int, int] = (23, 6)
    """Local hours [start, end) during which Zengo naps readily, wrapping midnight."""

    edge_margin: float = 31.0
    """Art pixels kept between the anchor and a screen edge; the tail reaches this far back."""

    drag_threshold: int = 4
    """Screen pixels the mouse must move while pressed before a click becomes a drag."""

    def px(self, art_pixels: float) -> float:
        return art_pixels * self.scale

    def is_night(self, hour: int) -> bool:
        start, end = self.night
        return start <= hour or hour < end if start > end else start <= hour < end
