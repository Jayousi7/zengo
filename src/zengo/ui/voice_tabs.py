"""The Words and Sounds tabs of his settings window.

They edit the same two files as a text editor would (phrases.toml, sounds.toml);
changes take effect at once and are saved a moment after you stop typing.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from zengo.behavior.voice import CUES, DEFAULT_PHRASES, MAX_PHRASE, MOMENTS, Voice

SAVE_AFTER_MS = 700
"""Typing pause before an edit is taken up and saved."""


def _note(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("note")
    label.setWordWrap(True)
    return label


class WordsTab(QWidget):
    """His phrases for each moment, one per line; below them, the words you've
    taught him (filled in by the teaching code)."""

    edited = Signal(object)
    """New phrases, a mapping of moment to lines."""

    def __init__(self) -> None:
        super().__init__()
        self._phrases: dict[str, tuple[str, ...]] = dict(DEFAULT_PHRASES)
        self._showing = False
        self._editing = next(iter(MOMENTS))
        """The moment whose phrases are in the editor."""
        self.moments = QListWidget()
        for moment in MOMENTS:
            self.moments.addItem(moment)
        self.moments.setFixedWidth(110)
        self.when = _note("")
        self.lines = QPlainTextEdit()
        self.lines.setPlaceholderText("One phrase per line. Empty: his built-in ones.")
        self.reset = QPushButton("Built-in phrases")
        self.taught = QVBoxLayout()

        editor = QVBoxLayout()
        editor.addWidget(self.when)
        editor.addWidget(self.lines)
        editor.addWidget(self.reset, alignment=Qt.AlignmentFlag.AlignRight)
        row = QHBoxLayout()
        row.addWidget(self.moments)
        row.addLayout(editor)
        layout = QVBoxLayout(self)
        layout.addLayout(row, 1)
        layout.addWidget(_note(f"Up to {MAX_PHRASE} characters each. Saved to phrases.toml."))
        layout.addLayout(self.taught)

        self._pause = QTimer(self, singleShot=True, interval=SAVE_AFTER_MS)
        self._pause.timeout.connect(self._take)
        self.moments.currentRowChanged.connect(self._pick)
        self.lines.textChanged.connect(self._typed)
        self.reset.clicked.connect(self._built_in)
        self.moments.setCurrentRow(0)

    @property
    def moment(self) -> str:
        return list(MOMENTS)[max(0, self.moments.currentRow())]

    def show_phrases(self, phrases: Mapping[str, tuple[str, ...]]) -> None:
        self._phrases = dict(phrases)
        self._pick()

    def flush(self) -> None:
        """Take up an edit still waiting for the typing pause (the window is closing)."""
        if self._pause.isActive():
            self._pause.stop()
            self._take()

    def _pick(self, *_: object) -> None:
        self.flush()
        self._editing = self.moment
        self.when.setText(f"Said {MOMENTS[self.moment]}.")
        self._showing = True
        try:
            self.lines.setPlainText("\n".join(self._phrases.get(self.moment, ())))
        finally:
            self._showing = False

    def _typed(self) -> None:
        if not self._showing:
            self._pause.start()

    def _take(self) -> None:
        lines = tuple(line.strip()[:MAX_PHRASE] for line in self.lines.toPlainText().splitlines())
        moment = self._editing
        lines = tuple(line for line in lines if line) or DEFAULT_PHRASES[moment]
        if lines != self._phrases.get(moment):
            self._phrases[moment] = lines
            self.edited.emit(dict(self._phrases))

    def _built_in(self) -> None:
        self._pause.stop()
        self._phrases[self.moment] = DEFAULT_PHRASES[self.moment]
        self._pick()
        self.edited.emit(dict(self._phrases))


class SoundsTab(QWidget):
    """Each of his sounds: play it, replace it with a WAV file (or a recording),
    or put his own back."""

    edited = Signal(object)
    """The sounds now replaced, a mapping of name to file."""
    play = Signal(str)
    record = Signal(str)
    """Record a replacement for this sound (shown only when recording works)."""

    def __init__(self, choose_file: Callable[[], Path | None] | None = None) -> None:
        super().__init__()
        self._sounds: dict[str, Path] = {}
        self._choose = choose_file or self._ask_for_file
        self.can_record = False
        self.table = QTableWidget(len(CUES), 3)
        self.table.setHorizontalHeaderLabels(["Sound", "Plays", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.buttons: dict[str, dict[str, QPushButton]] = {}
        for row, (cue, what) in enumerate(CUES.items()):
            name = QTableWidgetItem(what)
            name.setToolTip(cue)
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, QTableWidgetItem())
            cell = QWidget()
            buttons = QHBoxLayout(cell)
            buttons.setContentsMargins(2, 2, 2, 2)
            made = {}
            for key, label in (
                ("play", "▶"),
                ("file", "File…"),
                ("record", "Record…"),
                ("reset", "Built-in"),
            ):
                button = QPushButton(label)
                buttons.addWidget(button)
                made[key] = button
            made["play"].clicked.connect(lambda _=False, c=cue: self.play.emit(c))
            made["file"].clicked.connect(lambda _=False, c=cue: self._replace(c))
            made["record"].clicked.connect(lambda _=False, c=cue: self.record.emit(c))
            made["reset"].clicked.connect(lambda _=False, c=cue: self._built_in(c))
            self.buttons[cue] = made
            self.table.setCellWidget(row, 2, cell)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        self.record_note = _note("")
        layout.addWidget(self.record_note)
        layout.addWidget(_note("WAV files, a few seconds at most. Saved to sounds.toml."))
        self.show_sounds({})

    def set_recording(self, works: bool, why_not: str = "") -> None:
        self.can_record = works
        for made in self.buttons.values():
            made["record"].setEnabled(works)
            made["record"].setToolTip("" if works else why_not)
        self.record_note.setText("" if works else f"Recording: {why_not}")
        self.record_note.setVisible(not works)

    def show_sounds(self, sounds: Mapping[str, Path]) -> None:
        self._sounds = dict(sounds)
        for row, cue in enumerate(CUES):
            path = self._sounds.get(cue)
            item = self.table.item(row, 1)
            item.setText("his own" if path is None else path.name)
            item.setToolTip("" if path is None else str(path))
            self.buttons[cue]["reset"].setEnabled(path is not None)

    def _replace(self, cue: str) -> None:
        path = self._choose()
        if path is not None:
            self._sounds[cue] = path
            self.show_sounds(self._sounds)
            self.edited.emit(dict(self._sounds))

    def _built_in(self, cue: str) -> None:
        if self._sounds.pop(cue, None) is not None:
            self.show_sounds(self._sounds)
            self.edited.emit(dict(self._sounds))

    def _ask_for_file(self) -> Path | None:
        name, _ = QFileDialog.getOpenFileName(self, "A sound for Zengo", "", "WAV files (*.wav)")
        return Path(name) if name else None


def voice_with(
    voice: Voice,
    phrases: Mapping[str, tuple[str, ...]] | None = None,
    sounds: Mapping[str, Path] | None = None,
) -> Voice:
    return Voice(
        dict(voice.phrases) if phrases is None else dict(phrases),
        dict(voice.sounds) if sounds is None else dict(sounds),
    )
