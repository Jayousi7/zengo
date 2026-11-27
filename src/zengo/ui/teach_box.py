"""The "Teach Zengo…" box: type a word, choose when he'll say it, and teach."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from zengo.behavior.vocabulary import MAX_LENGTH, Lesson
from zengo.behavior.voice import MOMENTS
from zengo.ui.settings_window import STYLE

WHEN = {
    "random": "Any time",
    **{m: MOMENTS[m].capitalize() for m in MOMENTS if m not in ("random", "whistle")},
}
"""When a taught word can be said. Not as a whistle: those go with his tunes."""


def _minutes(seconds: float) -> str:
    minutes = max(1, round(seconds / 60))
    return "a minute" if minutes == 1 else f"{minutes} minutes"


def outcome(lesson: Lesson) -> str:
    """What to tell you after a lesson."""
    word = lesson.word
    lead = f"To make room, he forgot “{lesson.forgot}”. " if lesson.forgot else ""
    if lesson.learned:
        when = "now and then" if word.moment == "random" else MOMENTS[word.moment]
        if lesson.counted:
            return f"{lead}He's got it! He'll say “{word.text}” {when}."
        return f"{lead}He knows “{word.text}” already: he'll say it {when}."
    if lesson.counted:
        return (
            f"{lead}Lesson {word.lessons} of {lesson.needed}. Teach him again in an hour or more."
        )
    return (
        f"{lead}He listened, but it's too soon to count: "
        f"the next lesson counts in {_minutes(lesson.next_in)}."
    )


class TeachBox(QWidget):
    """``teach(text, moment)`` gives the lesson and returns how it went, or
    ``None``; ``why_not()`` says why he can't have one right now."""

    def __init__(
        self,
        teach: Callable[[str, str], Lesson | None],
        why_not: Callable[[], str | None],
    ) -> None:
        super().__init__(None, Qt.WindowType.Window)
        self.setWindowTitle("Teach Zengo")
        self.setStyleSheet(STYLE)
        self._teach, self._why_not = teach, why_not
        self.word = QLineEdit()
        self.word.setMaxLength(MAX_LENGTH)
        self.word.setPlaceholderText("a word or short phrase")
        self.when = QComboBox()
        for moment, words in WHEN.items():
            self.when.addItem(words, moment)
        self.button = QPushButton("Teach")
        self.button.setDefault(True)
        self.result = QLabel(
            "He learns by repetition: about five lessons, at least an hour apart. "
            "The closer he feels to you, the quicker he learns."
        )
        self.result.setWordWrap(True)
        self.result.setObjectName("note")

        form = QFormLayout()
        form.addRow("Word", self.word)
        form.addRow("Say it", self.when)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self.button)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(row)
        layout.addWidget(self.result)
        self.resize(440, 200)

        self.button.clicked.connect(self.give_lesson)
        self.word.returnPressed.connect(self.give_lesson)
        self.word.textChanged.connect(lambda t: self.button.setEnabled(bool(t.strip())))
        self.button.setEnabled(False)

    def give_lesson(self) -> None:
        reason = self._why_not()
        if reason is not None:
            self.result.setText(reason)
            return
        lesson = self._teach(self.word.text(), self.when.currentData())
        if lesson is not None:
            self.result.setText(outcome(lesson))
