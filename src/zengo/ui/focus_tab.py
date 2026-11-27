"""The Focus tab of his settings: the focus timer's lengths, and starting,
pausing and stopping a session. (The tray menu has Pause and Stop too.)"""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QLocale, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from zengo.settings import (
    FOCUS_MINUTES,
    LONG_AFTER,
    LONG_BREAK_MINUTES,
    SHORT_BREAK_MINUTES,
    Settings,
)
from zengo.ui.status_panel import clock

REMINDERS = (0, 30, 45, 50, 60, 90, 120)
"""Minutes at the computer before a break reminder, offered in the list (0: off)."""


def _minutes(low: int, high: int) -> QSpinBox:
    box = QSpinBox()
    box.setRange(low, high)
    box.setSuffix(" min")
    box.setKeyboardTracking(False)  # typing "12" is one change, not "1" then "12"
    box.setLocale(QLocale.c())  # the same digits as the rest of his windows
    return box


def _note(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setObjectName("note")
    label.setWordWrap(True)
    return label


def describe(phase: str, left: float, paused: bool) -> str:
    """What the timer's doing, in words."""
    if phase == "off":
        return "Not running."
    if phase == "waiting":
        return "The break's over: he's waiting for you to start the next session."
    what = "of focus" if phase == "focus" else "of your break"
    return f"{clock(left)} left {what}" + (", paused." if paused else ".")


class FocusTab(QWidget):
    """Edits go out as settings through ``edited``; the buttons through ``start``,
    ``pause`` (or resume) and ``stop``."""

    edited = Signal()
    start = Signal()
    pause = Signal()
    stop = Signal()

    def __init__(self) -> None:
        super().__init__()
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        self.focus = _minutes(*FOCUS_MINUTES)
        self.short_break = _minutes(*SHORT_BREAK_MINUTES)
        self.long_break = _minutes(*LONG_BREAK_MINUTES)
        self.long_after = QComboBox()
        self.long_after.addItem("Never", 0)
        for n in range(LONG_AFTER[0], LONG_AFTER[1] + 1):
            self.long_after.addItem(f"After {n} sessions", n)
        self.next_session = QComboBox()
        self.next_session.addItem("Ask me", "ask")
        self.next_session.addItem("Automatically", "auto")
        self.reset = QPushButton("Reset to 25 / 5")
        form.addRow("Focus", self.focus)
        form.addRow("Short break", self.short_break)
        form.addRow("Long break", self.long_break)
        form.addRow("", self.long_after)
        form.addRow("Next session", self.next_session)
        form.addRow("", self.reset)
        form.addRow("", _note("New lengths take effect from the next session."))

        self.reminder = QComboBox()
        for minutes in REMINDERS:
            self.reminder.addItem("Off" if minutes == 0 else f"After {minutes} min", minutes)
        form.addRow("Break reminder", self.reminder)
        form.addRow(
            "",
            _note(
                "Not using the timer, he comes to suggest a break after a long "
                "stretch at the computer."
            ),
        )

        self.state = QLabel("Not running.")
        self.start_button = QPushButton("Start")
        self.pause_button = QPushButton("Pause")
        self.stop_button = QPushButton("Stop")
        buttons = QHBoxLayout()
        for button in (self.start_button, self.pause_button, self.stop_button):
            buttons.addWidget(button)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addStretch()
        layout.addWidget(self.state)
        layout.addLayout(buttons)

        for box in (self.focus, self.short_break, self.long_break):
            box.valueChanged.connect(lambda _: self.edited.emit())
        for combo in (self.long_after, self.next_session, self.reminder):
            combo.currentIndexChanged.connect(lambda _: self.edited.emit())
        self.reset.clicked.connect(self._reset)
        self.start_button.clicked.connect(self.start.emit)
        self.pause_button.clicked.connect(self.pause.emit)
        self.stop_button.clicked.connect(self.stop.emit)
        self.show_timer("off", 0.0, False)

    def show_settings(self, settings: Settings) -> None:
        self.focus.setValue(settings.focus_minutes)
        self.short_break.setValue(settings.short_break_minutes)
        self.long_break.setValue(settings.long_break_minutes)
        self.long_after.setCurrentIndex(self.long_after.findData(settings.long_after))
        self.next_session.setCurrentIndex(self.next_session.findData(settings.next_session))
        index = self.reminder.findData(settings.reminder_minutes)
        if index < 0:  # a value set by hand that isn't in the list
            self.reminder.addItem(
                f"After {settings.reminder_minutes} min", settings.reminder_minutes
            )
            index = self.reminder.count() - 1
        self.reminder.setCurrentIndex(index)

    def read(self, settings: Settings) -> Settings:
        return replace(
            settings,
            focus_minutes=self.focus.value(),
            short_break_minutes=self.short_break.value(),
            long_break_minutes=self.long_break.value(),
            long_after=self.long_after.currentData(),
            next_session=self.next_session.currentData(),
            reminder_minutes=self.reminder.currentData(),
        )

    def show_timer(self, phase: str, left: float, paused: bool) -> None:
        self.state.setText(describe(phase, left, paused))
        running = phase in ("focus", "break")
        self.start_button.setText("Start next" if phase == "waiting" else "Start")
        self.start_button.setEnabled(not running)
        self.pause_button.setEnabled(running)
        self.pause_button.setText("Resume" if paused else "Pause")
        self.stop_button.setEnabled(phase != "off")

    def _reset(self) -> None:
        default = Settings()
        self.focus.setValue(default.focus_minutes)
        self.short_break.setValue(default.short_break_minutes)
        self.long_break.setValue(default.long_break_minutes)
        self.long_after.setCurrentIndex(self.long_after.findData(default.long_after))
