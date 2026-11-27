"""Playing Zengo's sounds."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from zengo import sounds


class SoundPlayer:
    """Plays sounds by name. The sounds are synthesized once at start-up into a
    temporary folder (Qt plays files) and removed when the player is closed.

    If Qt's multimedia support is missing, or there's no audio device, it simply
    stays quiet.
    """

    def __init__(self, volume: float) -> None:
        self._effects: dict[str, object] = {}
        self._folder: Path | None = None
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QSoundEffect
        except ImportError:
            return
        self._folder = Path(tempfile.mkdtemp(prefix="zengo-sounds-"))
        for name in sounds.names():
            path = self._folder / f"{name}.wav"
            path.write_bytes(sounds.wav(sounds.sound(name)))
            effect = QSoundEffect()
            effect.setSource(QUrl.fromLocalFile(str(path)))
            effect.setVolume(volume)
            self._effects[name] = effect

    def set_volume(self, volume: float) -> None:
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
