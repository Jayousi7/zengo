"""Zengo's voice: chirps, whistles and trills, synthesized.

No recordings: each sound is a few pitch sweeps, shaped with a soft start and end
and a touch of overtone so they sound like a small bird rather than a test tone.
Cockatiels whistle around 2-4 kHz, in glides rather than steps. Plain Python, so
the sounds can be checked without any audio device; the app plays them.
"""

from __future__ import annotations

import io
import math
import struct
import wave
from collections.abc import Sequence

RATE = 22050
"""Samples a second: plenty for sounds that stay under 5 kHz."""

Note = tuple[float, float, float]
"""Seconds, starting pitch and ending pitch (Hz); a pitch of 0 is a rest."""


def _notes(notes: Sequence[Note], *, warble: float = 0.0) -> list[float]:
    """Render notes as samples in -1..1. ``warble`` adds a fast trill (Hz of wobble)."""
    out: list[float] = []
    phase = 0.0
    for seconds, start, end in notes:
        count = max(1, int(seconds * RATE))
        attack, release = int(0.008 * RATE), int(0.025 * RATE)
        for i in range(count):
            if start <= 0:
                out.append(0.0)
                continue
            t = i / count
            # Glide with a slight ease, as a bird's whistle bends rather than slides.
            freq = start + (end - start) * (t * t * (3 - 2 * t))
            if warble:
                freq += warble * math.sin(2 * math.pi * 24 * i / RATE)
            phase += 2 * math.pi * freq / RATE
            sample = math.sin(phase) + 0.25 * math.sin(2 * phase) + 0.08 * math.sin(3 * phase)
            envelope = min(1.0, i / attack if attack else 1.0, (count - i) / release)
            out.append(sample / 1.33 * envelope)
    return out


def _rest(seconds: float) -> Note:
    return (seconds, 0.0, 0.0)


SOUNDS: dict[str, list[float]] = {}
"""Every sound by name, rendered on first use (see :func:`sound`)."""

_RECIPES = {
    # Little contact chirps, now and then.
    "chirp_a": lambda: _notes([(0.09, 2800, 4200)]),
    "chirp_b": lambda: _notes([(0.06, 3400, 2700), (0.07, 2700, 3900)]),
    "chirp_c": lambda: _notes([(0.05, 3000, 3800), _rest(0.05), (0.06, 3000, 4000)]),
    # One tune per whistle phrase, in the order of his whistle phrases.
    "whistle_0": lambda: _notes(
        [(0.16, 1800, 3200), _rest(0.07), (0.18, 1800, 3400)]
    ),  # fweet-fweet
    "whistle_1": lambda: _notes([(0.12, 2600, 3200), _rest(0.04), (0.16, 2900, 3700)]),  # twee-dee
    "whistle_2": lambda: _notes(
        [(0.08, 2200, 2200), _rest(0.06), (0.08, 2200, 2200), _rest(0.06), (0.3, 2000, 3600)]
    ),  # tu-tu-tweeet
    "whistle_3": lambda: _notes([(0.18, 2700, 2600), (0.22, 2100, 1800)]),  # zen-go
    "whistle_4": lambda: _notes(
        [(0.12, 2400, 2500), (0.12, 2900, 2900), _rest(0.05), (0.12, 2400, 2400), (0.2, 2600, 3300)]
    ),  # pret-ty bird
    "whistle_5": lambda: _notes(
        [(0.14, 2000, 2050), (0.14, 2500, 2550), (0.2, 3000, 3100), (0.22, 2500, 2400)]
    ),  # a little tune
    # Asking for food: a pleading rise, twice.
    "ask": lambda: _notes([(0.12, 2300, 3300), _rest(0.08), (0.16, 2400, 3600)]),
    # Greeting you back: a bright two-note hello.
    "greeting": lambda: _notes([(0.1, 2600, 3400), _rest(0.05), (0.18, 2800, 3900)]),
    # Content (a meal, freedom): a quick trill.
    "trill": lambda: _notes([(0.32, 3000, 3300)], warble=320),
}
CHIRPS = ("chirp_a", "chirp_b", "chirp_c")
WHISTLE_TUNES = 6


def names() -> tuple[str, ...]:
    return tuple(_RECIPES)


def sound(name: str) -> list[float]:
    if name not in SOUNDS:
        SOUNDS[name] = _RECIPES[name]()
    return SOUNDS[name]


def whistle_for(phrase: int) -> str:
    """The tune that goes with the ``phrase``-th whistle in the config."""
    return f"whistle_{phrase % WHISTLE_TUNES}"


def wav(samples: Sequence[float]) -> bytes:
    """16-bit mono WAV of ``samples`` (in -1..1)."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(
            b"".join(struct.pack("<h", round(max(-1.0, min(1.0, s)) * 32000)) for s in samples)
        )
    return buffer.getvalue()
