"""Recording a sound to replace one of his: your own cockatiel, or you whistling.

The microphone is opened only while the Record button is held down in this box,
for at most :data:`MAX_SECONDS`, and closed the moment it's let go. Nothing is
recorded anywhere else, ever. The clip is trimmed of silence at both ends, can
be played back, and is kept (in his data folder, under ``recordings``) only if
you say so.

Audio comes from Qt as raw samples in whatever format the microphone prefers;
it's turned into 16-bit mono here and written with the standard ``wave`` module.
"""

from __future__ import annotations

import array
import struct
import sys
import wave
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from zengo.behavior.voice import CUES
from zengo.ui.settings_window import STYLE

MAX_SECONDS = 3.0
SILENCE = 0.04
"""Share of full scale below which a stretch counts as silence when trimming."""
PAD = 0.03
"""Seconds of quiet kept either side of the sound, so it doesn't start abruptly."""


# --- Samples (no Qt) ------------------------------------------------------------


def to_mono16(raw: bytes, channels: int, sample_format: str) -> list[int]:
    """Raw interleaved samples (``"Int16"``, ``"Int32"``, ``"Float"`` or ``"UInt8"``)
    as 16-bit mono, the channels averaged."""
    if sample_format == "Int16":
        values = [v / 32768 for v in array.array("h", raw[: len(raw) // 2 * 2])]
    elif sample_format == "Int32":
        values = [v / 2147483648 for v in array.array("i", raw[: len(raw) // 4 * 4])]
    elif sample_format == "Float":
        values = list(array.array("f", raw[: len(raw) // 4 * 4]))
    elif sample_format == "UInt8":
        values = [(v - 128) / 128 for v in raw]
    else:
        raise ValueError(f"unsupported sample format {sample_format}")
    if sys.byteorder != "little" and sample_format != "UInt8":
        raise ValueError("big-endian audio isn't supported")
    channels = max(1, channels)
    frames = len(values) // channels
    mono = []
    for i in range(frames):
        frame = values[i * channels : (i + 1) * channels]
        mono.append(round(max(-1.0, min(1.0, sum(frame) / channels)) * 32767))
    return mono


def trim_silence(samples: list[int], rate: int) -> list[int]:
    """``samples`` without the quiet at either end (a short pad of it kept)."""
    threshold = SILENCE * 32767
    loud = [i for i, s in enumerate(samples) if abs(s) >= threshold]
    if not loud:
        return []
    pad = round(PAD * rate)
    return samples[max(0, loud[0] - pad) : loud[-1] + 1 + pad]


def write_wav(path: Path, samples: list[int], rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(struct.pack(f"<{len(samples)}h", *samples))


# --- The box --------------------------------------------------------------------


def microphone() -> tuple[object | None, str]:
    """The default microphone, or ``None`` and why there isn't one."""
    try:
        from PySide6.QtMultimedia import QMediaDevices
    except ImportError:
        return None, "sound support (Qt Multimedia) isn't available"
    device = QMediaDevices.defaultAudioInput()
    if device.isNull():
        return None, "no microphone found"
    return device, ""


class RecorderBox(QWidget):
    """Hold Record to record, let go to stop; then play it back, keep it as one of
    his sounds, or throw it away. ``keep(cue, path)`` takes a kept recording;
    ``preview(path)`` plays a file."""

    def __init__(
        self,
        folder: Path,
        keep: Callable[[str, Path], None],
        preview: Callable[[Path], None],
        cue: str = "chirp_a",
    ) -> None:
        super().__init__(None, Qt.WindowType.Window)
        self.setWindowTitle("Record a sound for Zengo")
        self.setStyleSheet(STYLE)
        self._folder, self._keep, self._preview = folder, keep, preview
        self._device, why_not = microphone()
        self._source: object | None = None
        self._buffer: QBuffer | None = None
        self._format: tuple[int, int, str] | None = None
        self.samples: list[int] = []
        self.rate = 0

        self.cue = QComboBox()
        for name, what in CUES.items():
            self.cue.addItem(what, name)
        self.cue.setCurrentIndex(max(0, self.cue.findData(cue)))
        self.record = QPushButton("Hold to record")
        self.play = QPushButton("▶ Play")
        self.save = QPushButton("Keep")
        self.discard = QPushButton("Discard")
        self.status = QLabel(
            "The microphone is on only while you hold the button, "
            f"for up to {MAX_SECONDS:g} seconds. It isn't used anywhere else."
        )
        self.status.setWordWrap(True)
        self.status.setObjectName("note")
        form = QFormLayout()
        form.addRow("Replaces", self.cue)
        buttons = QHBoxLayout()
        for button in (self.record, self.play, self.save, self.discard):
            buttons.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.status)
        self.resize(460, 170)

        self._limit = QTimer(self, singleShot=True, interval=round(MAX_SECONDS * 1000))
        self._limit.timeout.connect(self._stop)
        self.record.pressed.connect(self._start)
        self.record.released.connect(self._stop)
        self.play.clicked.connect(self._play)
        self.save.clicked.connect(self._save)
        self.discard.clicked.connect(self._discard)
        if self._device is None:
            self.record.setEnabled(False)
            self.status.setText(f"Recording isn't possible here: {why_not}.")
        self._show_take()

    @property
    def can_record(self) -> bool:
        return self._device is not None

    def set_take(self, samples: list[int], rate: int) -> None:
        """Use these samples as the recording (trimmed), as if just recorded."""
        self.samples, self.rate = trim_silence(samples, rate), rate
        if not self.samples:
            self.status.setText("Nothing heard: try again, a little closer.")
        else:
            seconds = len(self.samples) / rate
            self.status.setText(f"Recorded {seconds:.1f} s. Play it back, then keep or discard.")
        self._show_take()

    def _show_take(self) -> None:
        has = bool(self.samples)
        for button in (self.play, self.save, self.discard):
            button.setEnabled(has)

    def _start(self) -> None:
        if self._device is None or self._source is not None:
            return
        from PySide6.QtMultimedia import QAudioSource

        fmt = self._device.preferredFormat()  # type: ignore[attr-defined]
        self._format = (fmt.sampleRate(), fmt.channelCount(), fmt.sampleFormat().name)
        self._buffer = QBuffer()
        self._buffer.setData(QByteArray())
        self._buffer.open(QIODevice.OpenModeFlag.ReadWrite)
        self._source = QAudioSource(self._device, fmt)
        self._source.start(self._buffer)  # type: ignore[attr-defined]
        self._limit.start()
        self.record.setText("Recording… let go to stop")

    def _stop(self) -> None:
        source, buffer, fmt = self._source, self._buffer, self._format
        if source is None or buffer is None or fmt is None:
            return
        self._limit.stop()
        source.stop()  # type: ignore[attr-defined]  # the microphone closes here
        self._source = self._buffer = None
        self.record.setText("Hold to record")
        rate, channels, sample_format = fmt
        try:
            samples = to_mono16(bytes(buffer.data().data()), channels, sample_format)
        except ValueError as error:
            self.status.setText(f"Couldn't use that recording: {error}.")
            return
        self.set_take(samples[: round(MAX_SECONDS * rate)], rate)

    def _take_path(self) -> Path:
        return self._folder / "recordings" / f"{self.cue.currentData()}.wav"

    def _play(self) -> None:
        if self.samples:
            preview = self._folder / "recordings" / ".preview.wav"
            write_wav(preview, self.samples, self.rate)
            self._preview(preview)

    def _save(self) -> None:
        if not self.samples:
            return
        path = self._take_path()
        write_wav(path, self.samples, self.rate)
        self._keep(self.cue.currentData(), path)
        self.status.setText(f"Kept: he'll use it for “{self.cue.currentText()}”.")
        self.samples = []
        self._show_take()

    def _discard(self) -> None:
        self.samples = []
        self.status.setText("Thrown away.")
        self._show_take()

    def closeEvent(self, event: object) -> None:
        self._stop()  # never leave the microphone open
        super().closeEvent(event)  # type: ignore[arg-type]
