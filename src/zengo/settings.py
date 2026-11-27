"""Your choices for Zengo, kept in ``settings.json`` beside his state file.

Settings sit between the built-in defaults in :mod:`zengo.config` and the
command-line flags: the defaults give way to your settings, and a flag given
when starting him wins over both (handy for trying things out). ``--quick``
goes last of all, so its short timers win even over a slow appetite.

Reading is forgiving, like the state file: a missing or damaged file reads as
the defaults, and each value is checked on its own, so one bad value falls back
to its default without losing the rest. Unknown keys are ignored.

Pure Python: no Qt, so it is testable headless.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any

from zengo.behavior.seasons import HEMISPHERES, SEASONS
from zengo.behavior.toys import TOYS
from zengo.config import Config, quick

MIN_SCALE, MAX_SCALE = 2, 5

BRANCH_EVERY: dict[str, tuple[float, float]] = {
    "rarely": (1200.0, 2400.0),
    "sometimes": Config.branch_every,
    "often": (300.0, 600.0),
}
"""Seconds between one branch withdrawing and the next growing out."""

APPETITE: dict[str, float] = {"slow": 0.5, "normal": 1.0, "fast": 2.0}
"""How fast he gets hungry, as a multiple of the built-in rate."""


@dataclass(frozen=True)
class Settings:
    scale: int = Config.scale
    """Screen pixels per art pixel, ``MIN_SCALE`` to ``MAX_SCALE``."""
    sound: bool = True
    volume: float = 0.35
    """0 to 1. Soft by default: he's a pet on your desk, not an alarm."""
    branch: str = "sometimes"
    """How often a branch grows: a key of :data:`BRANCH_EVERY`."""
    appetite: str = "normal"
    """How fast he gets hungry: a key of :data:`APPETITE`."""
    seasons: bool = True
    """Seasonal outfits and effects: the scarf, snow, falling leaves."""
    hemisphere: str = "auto"
    """A key of :data:`zengo.behavior.seasons.HEMISPHERES`."""
    toys: tuple[str, ...] = ()
    """The toys you've put out for him: keys of :data:`zengo.behavior.toys.TOYS`."""

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["toys"] = list(self.toys)
        return data

    @classmethod
    def from_json(cls, data: object) -> Settings:
        """The settings in ``data``, each unusable value replaced by its default."""
        if not isinstance(data, dict):
            return cls()
        default = cls()
        scale = data.get("scale")
        volume = data.get("volume")
        sound = data.get("sound")
        branch = data.get("branch")
        appetite = data.get("appetite")
        seasons = data.get("seasons")
        hemisphere = data.get("hemisphere")
        toys = data.get("toys")
        return cls(
            scale=_whole(scale, MIN_SCALE, MAX_SCALE, default.scale),
            sound=sound if isinstance(sound, bool) else default.sound,
            volume=_fraction(volume, default.volume),
            branch=branch if branch in BRANCH_EVERY else default.branch,
            appetite=appetite if appetite in APPETITE else default.appetite,
            seasons=seasons if isinstance(seasons, bool) else default.seasons,
            hemisphere=hemisphere if hemisphere in HEMISPHERES else default.hemisphere,
            toys=tuple(t for t in TOYS if t in toys) if isinstance(toys, list) else default.toys,
        )


@dataclass(frozen=True)
class Flags:
    """What was given on the command line. ``None`` means not given."""

    scale: int | None = None
    fps: int | None = None
    quick: bool = False
    season: str | None = None
    """A season to show whatever the date (one of :data:`SEASONS`)."""

    def __post_init__(self) -> None:
        if self.season is not None and self.season not in SEASONS:
            raise ValueError(f"unknown season {self.season!r}")


def build_config(
    settings: Settings, flags: Flags | None = None, base: Config | None = None
) -> Config:
    """The config he runs with: ``base`` (the built-in defaults unless given),
    then your settings, then the flags."""
    flags, base = flags or Flags(), base or Config()
    config = replace(
        base,
        scale=settings.scale,
        branch_every=BRANCH_EVERY[settings.branch],
        hunger_drain=base.hunger_drain * APPETITE[settings.appetite],
    )
    if flags.scale is not None:
        config = replace(config, scale=flags.scale)
    if flags.fps is not None:
        config = replace(config, fps=flags.fps)
    return quick(config) if flags.quick else config


def _whole(value: object, low: int, high: int, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value if low <= value <= high else default


def _fraction(value: object, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    return min(max(float(value), 0.0), 1.0) if value == value else default


def migrated(settings_data: object, state_data: object) -> Settings | None:
    """Up to v0.4, sound on or off was kept in the state file. If ``settings.json``
    has no say on it yet but the state file does, the settings with that carried
    over, to be saved; otherwise ``None``, nothing to move."""
    if isinstance(settings_data, dict) and isinstance(settings_data.get("sound"), bool):
        return None
    old = state_data.get("settings") if isinstance(state_data, dict) else None
    if not isinstance(old, dict) or not isinstance(old.get("sound"), bool):
        return None
    return replace(Settings.from_json(settings_data), sound=old["sound"])
