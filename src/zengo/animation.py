"""Frame timing, independent of how frames are drawn."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Clip:
    """A sequence of frame names, each held for its own duration in seconds."""

    frames: tuple[str, ...]
    durations: tuple[float, ...]
    loop: bool = True

    def __post_init__(self) -> None:
        if not self.frames or len(self.frames) != len(self.durations):
            raise ValueError("a clip needs one duration per frame, and at least one frame")
        if any(d <= 0 for d in self.durations):
            raise ValueError("frame durations must be positive")

    @classmethod
    def even(cls, *frames: str, fps: float, loop: bool = True) -> Clip:
        return cls(frames, (1 / fps,) * len(frames), loop)

    @property
    def length(self) -> float:
        return sum(self.durations)


class Animator:
    """Plays one clip at a time from a fixed catalogue."""

    def __init__(self, clips: Mapping[str, Clip], initial: str) -> None:
        self._clips = clips
        self._name = initial
        self._time = 0.0

    @property
    def clip_name(self) -> str:
        return self._name

    def play(self, name: str, *, restart: bool = False) -> None:
        """Switch clips. Re-playing the current clip continues it unless ``restart``."""
        if name not in self._clips:
            raise KeyError(f"no clip named {name!r}")
        if restart or name != self._name:
            self._name = name
            self._time = 0.0

    def update(self, dt: float) -> None:
        self._time += dt

    @property
    def finished(self) -> bool:
        """True once a non-looping clip has played through. Looping clips never finish."""
        clip = self._clips[self._name]
        return not clip.loop and self._time >= clip.length

    @property
    def frame(self) -> str:
        clip = self._clips[self._name]
        t = self._time % clip.length if clip.loop else min(self._time, clip.length)
        for name, duration in zip(clip.frames, clip.durations, strict=True):
            if t < duration:
                return name
            t -= duration
        return clip.frames[-1]
