"""A slim strip at the top of Zengo's menu showing his needs, live."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QHelpEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QToolTip, QWidget

from zengo.behavior.status import Status
from zengo.sprites.food import MAX_STACKS

# Dark theme: a warm near-black strip, quiet icons, each number in its own colour.
INK = QColor("#f1e6da")
QUIET = QColor("#a8978c")
PAPER = QColor("#231c1f")
GOOD = QColor("#8dbb74")
FAIR = QColor("#e0bc6e")
POOR = QColor("#e07a5f")
SEED = QColor("#b08d74")
ESCAPE = QColor("#c9a45a")
HEART = QColor("#e58fa3")
FOCUS = QColor("#9db7d8")


@dataclass(frozen=True)
class Row:
    title: str
    headline: str
    """The number that matters, shown large."""
    note: str
    """A few words on it."""
    share: float
    """How much of the bar is filled, 0 to 1."""
    colour: QColor
    icon: str = ""
    """What stands for it in the strip."""

    @property
    def value(self) -> str:
        return f"{self.headline} · {self.note}"


def clock(seconds: float) -> str:
    seconds = max(0, round(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def rows(status: Status) -> list[Row]:
    """What the panel shows: one chip each for how close he feels to you, his
    hunger, his seeds and his escape."""
    full = status.fullness
    if status.hungry:
        hunger = "hungry now!"
    elif status.hunger_chance <= 0:
        hunger = "not peckish"
    else:
        hunger = f"{status.hunger_chance:.0%} hungry in {clock(status.hunger_check_in)}"
    paused = "" if status.caged else " (paused)"
    if status.escape_started:
        escape = (f"{status.escape_chance:.0%}", f"next try in {clock(status.escape_try_in)}")
        if not status.caged:
            escape = (escape[0], "next try (paused)")
        escape_share = status.escape_chance
    else:
        escape = (clock(status.escape_try_in), f"to first try{paused}")
        escape_share = status.escape_warmup
    return [
        Row("Bond ♥", f"{status.bond:.0%}", status.bond_mood, status.bond, HEART, "♥"),
        Row(
            "Fullness",
            f"{full:.0%}",
            hunger,
            full,
            POOR if status.hungry or full < 0.3 else FAIR if full < 0.7 else GOOD,
            "◐",
        ),
        Row(
            "Dish" if status.caged else "Seeds",
            f"{status.food_stacks}/{MAX_STACKS}",
            "stacks",
            status.food_stacks / MAX_STACKS,
            SEED,
            "∴",
        ),
        Row("Escape", *escape, escape_share, ESCAPE, "⇥"),
        *_focus_row(status),
    ]


def _focus_row(status: Status) -> list[Row]:
    """The focus timer's time left, while there's a session on."""
    phase = status.focus_phase
    if phase == "off":
        return []
    if phase == "waiting":
        return [Row("Focus", "▶", "break over: start the next session", 1.0, FOCUS, "◷")]
    what = "focus" if phase == "focus" else "break"
    note = f"{what} left" + (" (paused)" if status.focus_paused else "")
    colour = QUIET if status.focus_paused else FOCUS if phase == "focus" else GOOD
    return [Row("Focus", clock(status.focus_left), note, 1.0, colour, "◷")]


class StatusPanel(QWidget):
    """Shows :func:`rows` for the status ``read`` returns as one slim strip of
    coloured icon-and-number chips, refreshed while open. Hovering a chip tells
    you the rest: its name and the few words on it."""

    PAD_X = 12
    PAD_Y = 7
    GAP = 14
    ICON_GAP = 4

    def __init__(self, read: Callable[[], Status], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._read = read
        self._rows = rows(read())
        self._chips: list[QRectF] = []
        self.setMouseTracking(True)
        self._timer = QTimer(self, interval=250)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()
        self.setMinimumSize(self.sizeHint())

    def _number_font(self) -> QFont:
        font = QFont(self.font())
        font.setBold(True)
        return font

    def _chip_width(self, row: Row) -> float:
        icon = QFontMetricsF(self.font()).horizontalAdvance(row.icon)
        numbers = QFontMetricsF(self._number_font())
        widest = max(numbers.horizontalAdvance(n) for n in (row.headline, *_WIDEST))
        return icon + self.ICON_GAP + widest

    def sizeHint(self) -> QSize:
        chips = sum(self._chip_width(row) for row in self._rows)
        width = 2 * self.PAD_X + chips + self.GAP * (len(self._rows) - 1)
        height = 2 * self.PAD_Y + QFontMetricsF(self._number_font()).height()
        return QSize(math.ceil(width), math.ceil(height))

    def _refresh(self) -> None:
        self._rows = rows(self._read())
        self.update()

    def row_at(self, x: float) -> Row | None:
        """The chip nearest ``x``, as last painted: the whole strip is hoverable."""
        pairs = list(zip(self._chips, self._rows, strict=False))
        if not pairs:
            return None
        return min(pairs, key=lambda pair: abs(pair[0].center().x() - x))[1]

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.ToolTip:
            assert isinstance(event, QHelpEvent)
            row = self.row_at(event.pos().x())
            if row is None:
                QToolTip.hideText()
                event.ignore()
            else:
                QToolTip.showText(event.globalPos(), f"{row.title}: {row.value}", self)
            return True
        return super().event(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), PAPER)
        number_font = self._number_font()
        middle = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        x, height = float(self.PAD_X), float(self.height())
        self._chips = []
        for row in self._rows:
            width = self._chip_width(row)
            p.setFont(self.font())
            p.setPen(QUIET)
            icon_w = p.fontMetrics().horizontalAdvance(row.icon)
            p.drawText(QRectF(x, 0, icon_w + 1, height), middle, row.icon)
            p.setFont(number_font)
            p.setPen(row.colour)
            left = x + icon_w + self.ICON_GAP
            p.drawText(QRectF(left, 0, x + width - left + 1, height), middle, row.headline)
            self._chips.append(QRectF(x, 0, width, height))
            x += width + self.GAP
        p.end()


_WIDEST = ("100%", "00:00")
"""Room every chip keeps for its number, so the strip doesn't jiggle as they change."""
