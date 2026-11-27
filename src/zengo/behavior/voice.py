"""What Zengo says and how he sounds, from two plain files you can edit.

- ``phrases.toml``: a list of phrases for each moment (see :data:`MOMENTS`). He
  picks one at random when the moment comes.
- ``sounds.toml``: for each of his sounds (see :data:`CUES`), ``"built-in"`` for
  his own synthesized one, or the path of a WAV file to play instead.

Both live in his data folder, beside the state file. The built-ins are written
out as the files' first contents, and only when a file is missing: a file you've
edited is never overwritten at start-up. A broken file is reported once and the
built-ins are used, like the state file; a bad entry in a good file falls back
on its own.

Python reads TOML but can't write it, so the files are written here in a fixed
layout (a header, then one key per line). Saving from the settings window
rewrites them that way: comments you added by hand are lost then.

Pure Python: no Qt.
"""

from __future__ import annotations

import json
import sys
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from zengo.sounds import WHISTLE_TUNES

BUILT_IN = "built-in"

MOMENTS: dict[str, str] = {
    "random": "now and then, pottering about",
    "whistle": "when you double-click him (each line has its own tune, in order)",
    "greeting": "when you come back after being away",
    "hungry": "asking you for food",
    "fed": "after a meal",
    "bathed": "after a bath, shaking himself dry",
    "toy": "chatting to his mirror",
    "break": "calling you to a break after a focus session",
    "back": "the break's over: asking if you're ready for the next session",
    "nudge": "suggesting a break after a long stretch at the computer",
    "petted": "while you pet him",
    "caged": "complaining in the cage",
    "freed": "out of the cage by his own wits",
}
"""Each moment he speaks at, and when that is."""

DEFAULT_PHRASES: dict[str, tuple[str, ...]] = {
    "random": ("♪",),
    "whistle": (
        "♪ fweet-fweet! ♪",
        "♫ twee-dee! ♫",
        "♪ tu-tu-tweeet ♪",
        "Zengo! ♪",
        "pretty bird! ♫",
        "♪ ♫ ♪",
    ),
    "greeting": ("you're back! ♪",),
    "hungry": ("feed me!!", "seeds pls? ♥", "hungryyy...", "*stares*"),
    "fed": ("yum! ♥",),
    "bathed": ("ahh, fresh! ♪", "splish splash ♪"),
    "toy": ("pretty bird! ♪", "who's that? ♪", "hello you! ♥", "♪ ♫ ♪"),
    "break": ("break! ♪", "break time! ♪", "stretch time! ♪"),
    "back": ("back to it? ♪", "ready? ♪"),
    "nudge": ("stretch? ♪", "water? ♪", "a little break? ♥"),
    "petted": ("♥",),
    "caged": ("HEY!!", "let me out!", "hmph!!", "rude.", ">:(", "not cool!"),
    "freed": ("freedom!! ♪",),
}

CUES: dict[str, str] = {
    "chirp_a": "a little chirp",
    "chirp_b": "another chirp",
    "chirp_c": "a double chirp",
    **{f"whistle_{i}": f"whistle tune {i + 1}" for i in range(WHISTLE_TUNES)},
    "ask": "asking for food",
    "greeting": "greeting you",
    "trill": "content: a meal, freedom",
    "ting": "his bell",
    "break": "break time, after a focus session",
}
"""Each sound he makes, and what it's for."""

MAX_PHRASE = 40
"""Characters; longer won't fit his cloud."""


@dataclass(frozen=True)
class Voice:
    phrases: Mapping[str, tuple[str, ...]] = field(default_factory=lambda: dict(DEFAULT_PHRASES))
    sounds: Mapping[str, Path] = field(default_factory=dict)
    """Sounds replaced by a WAV file; the others are his built-in ones."""

    def lines(self, moment: str) -> tuple[str, ...]:
        return self.phrases.get(moment) or DEFAULT_PHRASES[moment]


# --- Reading -----------------------------------------------------------------


def phrases_from(data: object) -> dict[str, tuple[str, ...]]:
    """The phrases in ``data`` (parsed TOML), each unusable moment left at its default."""
    phrases = dict(DEFAULT_PHRASES)
    if not isinstance(data, dict):
        return phrases
    for moment in MOMENTS:
        lines = data.get(moment)
        if not isinstance(lines, list):
            continue
        kept = tuple(
            line.strip()[:MAX_PHRASE] for line in lines if isinstance(line, str) and line.strip()
        )
        if kept:
            phrases[moment] = kept
    return phrases


def sounds_from(data: object, folder: Path) -> dict[str, Path]:
    """The sounds in ``data`` replaced by files; relative paths are in ``folder``.
    Unknown names (an old ``squawk``) and anything else unusable are ignored."""
    sounds: dict[str, Path] = {}
    if not isinstance(data, dict):
        return sounds
    for cue in CUES:
        value = data.get(cue)
        if isinstance(value, str) and value.strip() and value.strip() != BUILT_IN:
            path = Path(value.strip()).expanduser()
            sounds[cue] = path if path.is_absolute() else folder / path
    return sounds


class VoiceFiles:
    """The two files in his data folder."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.phrases_path = folder / "phrases.toml"
        self.sounds_path = folder / "sounds.toml"
        self._reported: set[Path] = set()

    def load(self) -> Voice:
        """Read both files, writing out the built-ins where one is missing."""
        phrases = self._read(self.phrases_path, lambda: phrases_toml(DEFAULT_PHRASES))
        sounds = self._read(self.sounds_path, lambda: sounds_toml({}, self.folder))
        return Voice(phrases_from(phrases), sounds_from(sounds, self.folder))

    def save(self, voice: Voice) -> None:
        self._write(self.phrases_path, phrases_toml(voice.phrases))
        self._write(self.sounds_path, sounds_toml(voice.sounds, self.folder))

    def _read(self, path: Path, default: object) -> object:
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self._write(path, default())  # type: ignore[operator]
            return None
        except (OSError, ValueError) as error:
            self._report(path, error)
            return None
        try:
            return tomllib.loads(text)
        except tomllib.TOMLDecodeError as error:
            self._report(path, error)
            return None

    def _write(self, path: Path, text: str) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        except OSError as error:
            self._report(path, error)

    def _report(self, path: Path, error: Exception) -> None:
        if path not in self._reported:
            self._reported.add(path)
            print(f"zengo: using his built-in voice, can't use {path}: {error}", file=sys.stderr)


# --- Writing -------------------------------------------------------------------


def _string(text: str) -> str:
    """A TOML basic string (JSON's escapes are TOML's too)."""
    return json.dumps(text, ensure_ascii=False)


def phrases_toml(phrases: Mapping[str, tuple[str, ...]]) -> str:
    out = [
        "# What Zengo says. One list of phrases per moment; he picks one at random.",
        "# Edit, add or remove freely; an empty or missing list uses his built-in one.",
        f"# Keep each phrase short: up to {MAX_PHRASE} characters fit his cloud.",
        "# He has six whistle tunes: the first whistle phrase goes with the first",
        "# tune, and so on, starting over after the sixth.",
        "# Saving from his settings window rewrites this file: comments are lost.",
        "",
    ]
    for moment, when in MOMENTS.items():
        lines = phrases.get(moment) or DEFAULT_PHRASES[moment]
        out.append(f"# {when}")
        out.append(f"{moment} = [")
        out.extend(f"    {_string(line)}," for line in lines)
        out.append("]")
        out.append("")
    return "\n".join(out)


def _relative(path: Path, folder: Path) -> str:
    return path.name if path.parent == folder else str(path)


def sounds_toml(sounds: Mapping[str, Path], folder: Path) -> str:
    out = [
        '# Zengo\'s sounds. For each: "built-in" for his own, or the path of a WAV',
        "# file to play instead (a path without a folder is in this file's folder).",
        "# Saving from his settings window rewrites this file: comments are lost.",
        "",
    ]
    for cue, what in CUES.items():
        path = sounds.get(cue)
        value = BUILT_IN if path is None else _relative(path, folder)
        entry = f"{cue} = {_string(value)}"
        out.append(f"{entry:<30} # {what}")
    out.append("")
    return "\n".join(out)
