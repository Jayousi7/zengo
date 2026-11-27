"""A little panel at the top of Zengo's menu showing his needs, live."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from zengo.behavior.status import Status
from zengo.sprites.food import MAX_STACKS

# Dark theme: a warm near-black panel, light words, a dark track for the bars.
INK = QColor("#f1e6da")
QUIET = QColor("#a8978c")
PAPER = QColor("#231c1f")
TRACK = QColor("#3a3034")
CARD = QColor("#2e2629")
GOOD = QColor("#8dbb74")
FAIR = QColor("#e0bc6e")
POOR = QColor("#e07a5f")
SEED = QColor("#b08d74")
ESCAPE = QColor("#c9a45a")
HEART = QColor("#e58fa3")


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

    @property
    def value(self) -> str:
        return f"{self.headline} · {self.note}"


def clock(seconds: float) -> str:
    seconds = max(0, round(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def rows(status: Status) -> list[Row]:
    """What the panel shows: one card each for how close he feels to you, his
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
        Row("Bond ♥", f"{status.bond:.0%}", status.bond_mood, status.bond, HEART),
        Row(
            "Fullness",
            f"{full:.0%}",
            hunger,
            full,
            POOR if status.hungry or full < 0.3 else FAIR if full < 0.7 else GOOD,
        ),
        Row(
            "Dish" if status.caged else "Seeds",
            f"{status.food_stacks}/{MAX_STACKS}",
            "stacks",
            status.food_stacks / MAX_STACKS,
            SEED,
        ),
        Row("Escape", *escape, escape_share, ESCAPE),
    ]


class StatusPanel(QWidget):
    """Shows :func:`rows` for the status ``read`` returns as a grid of small cards,
    two to a row, refreshed while open."""

    COLUMNS = 2
    CARD_WIDTH = 148
    CARD_HEIGHT = 58
    GAP = 6
    PAD = 8

    def __init__(self, read: Callable[[], Status], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._read = read
        self._rows = rows(read())
        self._timer = QTimer(self, interval=250)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()
        self.setMinimumSize(self.sizeHint())

    def sizeHint(self) -> QSize:
        lines = -(-len(self._rows) // self.COLUMNS)
        return QSize(
            2 * self.PAD + self.COLUMNS * self.CARD_WIDTH + (self.COLUMNS - 1) * self.GAP,
            2 * self.PAD + lines * self.CARD_HEIGHT + (lines - 1) * self.GAP,
        )

    def _refresh(self) -> None:
        self._rows = rows(self._read())
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), PAPER)
        base = self.font().pointSizeF()
        title_font, headline_font, note_font = (
            QFont(self.font()),
            QFont(self.font()),
            QFont(self.font()),
        )
        title_font.setPointSizeF(max(7.0, base * 0.85))
        headline_font.setPointSizeF(base * 1.35)
        headline_font.setBold(True)
        note_font.setPointSizeF(max(7.0, base * 0.8))
        width = (self.width() - 2 * self.PAD - (self.COLUMNS - 1) * self.GAP) / self.COLUMNS
        left_align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        for i, row in enumerate(self._rows):
            col, line = i % self.COLUMNS, i // self.COLUMNS
            x = self.PAD + col * (width + self.GAP)
            y = self.PAD + line * (self.CARD_HEIGHT + self.GAP)
            card = QRectF(x, y, width, self.CARD_HEIGHT)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(CARD)
            p.drawRoundedRect(card, 7, 7)
            inner = card.adjusted(9, 6, -9, -8)
            p.setFont(title_font)
            p.setPen(QUIET)
            p.drawText(QRectF(inner.left(), inner.top(), inner.width(), 14), left_align, row.title)
            p.setFont(headline_font)
            p.setPen(row.colour)
            p.drawText(
                QRectF(inner.left(), inner.top() + 14, inner.width(), 22), left_align, row.headline
            )
            used = p.fontMetrics().horizontalAdvance(row.headline) + 6
            p.setFont(note_font)
            p.setPen(INK)
            note = p.fontMetrics().elidedText(
                row.note, Qt.TextElideMode.ElideRight, int(inner.width() - used)
            )
            p.drawText(
                QRectF(inner.left() + used, inner.top() + 14, inner.width() - used, 22),
                left_align,
                note,
            )
            bar = QRectF(inner.left(), inner.bottom() - 4, inner.width(), 4)
            p.setBrush(TRACK)
            p.drawRoundedRect(bar, 2, 2)
            share = min(max(row.share, 0.0), 1.0)
            if share > 0:
                p.setBrush(row.colour)
                p.drawRoundedRect(
                    QRectF(bar.left(), bar.top(), bar.width() * share, bar.height()), 2, 2
                )
        p.end()
