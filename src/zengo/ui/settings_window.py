"""Zengo's settings: a small dark window opened from his menu (or the tray).

Changes take effect at once. The window only reports them: the app applies
them, saves them and keeps the window showing what's in force.
"""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from zengo.settings import APPETITE, BRANCH_EVERY, MAX_SCALE, MIN_SCALE, Settings

STYLE = """
QWidget { background: #231c1f; color: #f1e6da; }
QTabWidget::pane { border: 1px solid #3a3034; top: -1px; }
QTabBar::tab { background: #2e2629; padding: 6px 14px; border: 1px solid #3a3034; }
QTabBar::tab:selected { background: #3a3034; }
QComboBox, QPushButton, QLineEdit, QPlainTextEdit, QListWidget, QTableWidget {
    background: #2e2629; border: 1px solid #3a3034; padding: 4px 8px; border-radius: 4px;
}
QPushButton:hover, QComboBox:hover { background: #3a3034; }
QPushButton:disabled, QComboBox:disabled, QCheckBox:disabled, QSlider:disabled { color: #6e6064; }
QLabel#note { color: #a8978c; }
QHeaderView::section { background: #2e2629; color: #a8978c; border: none; padding: 4px; }
"""
"""Dark, like his menu."""

BRANCH_WORDS = {"rarely": "Rarely", "sometimes": "Sometimes", "often": "Often"}
APPETITE_WORDS = {"slow": "Slow", "normal": "Normal", "fast": "Fast"}


def _combo(words: dict[str, str]) -> QComboBox:
    combo = QComboBox()
    for key, word in words.items():
        combo.addItem(word, key)
    return combo


class GeneralTab(QWidget):
    """Size, sound, how often a branch grows, appetite, start at login, and the
    way to start over."""

    def __init__(self, scale_locked: bool) -> None:
        super().__init__()
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        self.size = QComboBox()
        for scale in range(MIN_SCALE, MAX_SCALE + 1):
            self.size.addItem(f"{scale}\u00d7", scale)
        size_row = QHBoxLayout()
        size_row.addWidget(self.size)
        if scale_locked:
            self.size.setEnabled(False)
            note = QLabel("set by --scale")
            note.setObjectName("note")
            size_row.addWidget(note)
        size_row.addStretch()
        form.addRow("Size", size_row)

        self.sound = QCheckBox("On")
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setFixedWidth(140)
        sound_row = QHBoxLayout()
        sound_row.addWidget(self.sound)
        sound_row.addSpacing(10)
        sound_row.addWidget(QLabel("Volume"))
        sound_row.addWidget(self.volume)
        sound_row.addStretch()
        form.addRow("Sound", sound_row)

        assert BRANCH_WORDS.keys() == BRANCH_EVERY.keys()
        assert APPETITE_WORDS.keys() == APPETITE.keys()
        self.branch = _combo(BRANCH_WORDS)
        form.addRow("A branch grows", self.branch)
        self.appetite = _combo(APPETITE_WORDS)
        form.addRow("Appetite", self.appetite)

        self.autostart = QCheckBox("Start Zengo when I log in")
        form.addRow("", self.autostart)

        self.reset = QPushButton("Reset Zengo…")
        reset_note = QLabel("Forget everything he remembers and start over.")
        reset_note.setObjectName("note")
        reset_row = QVBoxLayout()
        reset_row.addWidget(self.reset, alignment=Qt.AlignmentFlag.AlignLeft)
        reset_row.addWidget(reset_note)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addStretch()
        layout.addLayout(reset_row)

    def show_settings(self, settings: Settings, autostart: bool | None) -> None:
        self.size.setCurrentIndex(self.size.findData(settings.scale))
        self.sound.setChecked(settings.sound)
        self.volume.setValue(round(settings.volume * 100))
        self.volume.setEnabled(settings.sound)
        self.branch.setCurrentIndex(self.branch.findData(settings.branch))
        self.appetite.setCurrentIndex(self.appetite.findData(settings.appetite))
        self.autostart.setEnabled(autostart is not None)
        self.autostart.setChecked(bool(autostart))

    def read(self, settings: Settings) -> Settings:
        return replace(
            settings,
            scale=self.size.currentData() if self.size.isEnabled() else settings.scale,
            sound=self.sound.isChecked(),
            volume=self.volume.value() / 100,
            branch=self.branch.currentData(),
            appetite=self.appetite.currentData(),
        )


class SettingsWindow(QWidget):
    """Reports each change as it's made:

    - ``changed``: new settings to apply and keep;
    - ``previewed``: new settings to apply but not keep yet (the volume while its
      slider is being dragged; ``changed`` follows when it's let go);
    - ``autostart_changed``: the start-at-login box was ticked or unticked;
    - ``reset_confirmed``: you asked to reset him and said yes when asked again.
    """

    changed = Signal(object)
    previewed = Signal(object)
    autostart_changed = Signal(bool)
    reset_confirmed = Signal()

    def __init__(self, settings: Settings, *, scale_locked: bool = False) -> None:
        super().__init__(None, Qt.WindowType.Window)
        self.setWindowTitle("Zengo settings")
        self.setStyleSheet(STYLE)
        self._settings = settings
        self._autostart: bool | None = None
        self._showing = False
        self.tabs = QTabWidget()
        self.general = GeneralTab(scale_locked)
        self.tabs.addTab(self.general, "General")
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        self.resize(420, 400)
        self.show_settings(settings)

        g = self.general
        for combo in (g.size, g.branch, g.appetite):
            combo.currentIndexChanged.connect(self._edited)
        g.sound.toggled.connect(self._edited)
        g.volume.valueChanged.connect(self._volume_moved)
        g.volume.sliderReleased.connect(self._edited)
        g.autostart.toggled.connect(self._autostart_toggled)
        g.reset.clicked.connect(self._ask_reset)

    def add_tab(self, tab: QWidget, title: str) -> None:
        self.tabs.addTab(tab, title)

    def closeEvent(self, event: QCloseEvent) -> None:
        for i in range(self.tabs.count()):
            flush = getattr(self.tabs.widget(i), "flush", None)
            if flush is not None:
                flush()  # an edit still waiting for the pause in typing
        super().closeEvent(event)

    def show_settings(self, settings: Settings, autostart: bool | None = None) -> None:
        """Show what's in force (changed elsewhere too: the menu's Sounds toggle).
        ``autostart`` is ``None`` where starting at login isn't supported."""
        self._settings, self._autostart = settings, autostart
        self._showing = True
        try:
            self.general.show_settings(settings, autostart)
        finally:
            self._showing = False

    def _edited(self, *_: object) -> None:
        if self._showing:
            return
        settings = self.general.read(self._settings)
        self.general.volume.setEnabled(settings.sound)
        if settings != self._settings:
            self._settings = settings
            self.changed.emit(settings)

    def _volume_moved(self, value: int) -> None:
        if self._showing:
            return
        if self.general.volume.isSliderDown():
            self.previewed.emit(replace(self._settings, volume=value / 100))
        else:
            self._edited()  # keyboard or a click on the track: keep it at once

    def _autostart_toggled(self, on: bool) -> None:
        if not self._showing and on != self._autostart:
            self._autostart = on
            self.autostart_changed.emit(on)

    def _ask_reset(self) -> None:
        answer = QMessageBox.question(
            self,
            "Reset Zengo?",
            "Zengo will forget everything he remembers: his bond with you, his "
            "hunger, the seeds out, his cage and escape progress, and the words "
            "he's learned or is learning.\n\n"
            "Your settings, his phrase and sound files, and your recordings are kept.",
            QMessageBox.StandardButton.Reset | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Reset:
            self.reset_confirmed.emit()
