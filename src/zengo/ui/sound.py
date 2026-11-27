"""Playing Zengo's sounds."""

from __future__ import annotations

import shutil
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

from zengo import sounds


class SoundPlayer:
    """Plays sounds by name. The sounds are synthesized once at start-up into a
    temporary folder (Qt plays files) and removed when the player is closed.
    A sound you've replaced with a WAV file plays that file instead; one that
    can't be found plays his own, after a note on stderr.

    If Qt's multimedia support is missing, or there's no audio device, it simply
    stays quiet.
    """

    def __init__(self, volume: float, replaced: Mapping[str, Path] | None = None) -> None:
        self._effects: dict[str, object] = {}
        self._folder: Path | None = None
        self._volume = volume
        try:
            from PySide6.QtMultimedia import QSoundEffect  # noqa: F401
        except ImportError:
            return
        self._folder = Path(tempfile.mkdtemp(prefix="zengo-sounds-"))
        for name in sounds.names():
            (self._folder / f"{name}.wav").write_bytes(sounds.wav(sounds.sound(name)))
        self.use(replaced or {})

    def use(self, replaced: Mapping[str, Path]) -> None:
        """Play these files in place of his own sounds (and his own for the rest)."""
        if self._folder is None:
            return
        from PySide6.QtCore import QUrl
        from PySide6.QtMultimedia import QSoundEffect

        for effect in self._effects.values():
            effect.stop()  # type: ignore[attr-defined]
        self._effects.clear()
        for name in sounds.names():
            path = replaced.get(name)
            if path is not None and not path.is_file():
                print(f"zengo: can't find {path}; using his own {name}", file=sys.stderr)
                path = None
            effect = QSoundEffect()
            effect.setSource(QUrl.fromLocalFile(str(path or self._folder / f"{name}.wav")))
            effect.setVolume(self._volume)
            self._effects[name] = effect

    def preview(self, path: Path) -> None:
        """Play a file once, at his volume (trying out a recording)."""
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QSoundEffect
        except ImportError:
            return
        effect = QSoundEffect()
        effect.setSource(QUrl.fromLocalFile(str(path)))
        effect.setVolume(self._volume)
        effect.play()
        self._effects["_preview"] = effect  # kept alive while it plays

    def set_volume(self, volume: float) -> None:
        self._volume = volume
        for effect in self._effects.values():
            effect.setVolume(volume)  # type: ignore[attr-defined]

    def play(self, name: str) -> None:
        effect = self._effects.get(name)
        if effect is not None:
            effect.play()  # type: ignore[attr-defined]

    def close(self) -> None:
        for effect in self._effects.values():
            effect.stop()  # type: ignore[attr-defined]
        self._effects.clear()
        if self._folder is not None:
            shutil.rmtree(self._folder, ignore_errors=True)
            self._folder = None
