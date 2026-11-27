"""A little panel at the top of Zengo's menu showing his needs, live."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from zengo.behavior.status import Status
from zengo.sprites.food import MAX_STACKS

# Dark theme: a warm near-black panel, light words, a dark track for the bars.
INK = QColor("#f1e6da")
QUIET = QColor("#a8978c")
PAPER = QColor("#231c1f")
TRACK = QColor("#3a3034")
GOOD = QColor("#8dbb74")
FAIR = QColor("#e0bc6e")
POOR = QColor("#e07a5f")
SEED = QColor("#b08d74")
ESCAPE = QColor("#c9a45a")


@dataclass(frozen=True)
class Row:
    title: str
    value: str
    share: float
    """How much of the bar is filled, 0 to 1."""
    colour: QColor


def clock(seconds: float) -> str:
    seconds = max(0, round(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def rows(status: Status) -> list[Row]:
    """What the panel shows, line by line: one bar each for his hunger, his seeds
    and his escape."""
    full = status.fullness
    if status.hungry:
        hunger = "hungry now!"
    elif status.hunger_chance <= 0:
        hunger = "not peckish"
    else:
        hunger = f"{status.hunger_chance:.0%} hungry in {clock(status.hunger_check_in)}"
    where = "Dish" if status.caged else "Seeds"
    paused = "" if status.caged else " (paused)"
    if status.escape_started:
        escape = f"{status.escape_chance:.0%} at next try"
        escape += f" in {clock(status.escape_try_in)}" if status.caged else " (paused)"
        escape_share = status.escape_chance
    else:
        escape = f"tries after 5:00 caged · {clock(status.escape_try_in)} to go{paused}"
        escape_share = status.escape_warmup
    return [
        Row(
            "Fullness",
            f"{full:.0%} · {hunger}",
            full,
            POOR if status.hungry or full < 0.3 else FAIR if full < 0.7 else GOOD,
        ),
        Row(
            where,
            f"{status.food_stacks}/{MAX_STACKS} stacks",
            status.food_stacks / MAX_STACKS,
            SEED,
        ),
        Row("Escape", escape, escape_share, ESCAPE),
    ]


class StatusPanel(QWidget):
    """Shows :func:`rows` for the status ``read`` returns, refreshed while open."""

    ROW_HEIGHT = 34
    PAD = 10

    def __init__(self, read: Callable[[], Status], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._read = read
        self._rows = rows(read())
        self._timer = QTimer(self, interval=250)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()
        self.setMinimumWidth(290)

    def sizeHint(self) -> QSize:
        return QSize(290, self.PAD * 2 + self.ROW_HEIGHT * len(self._rows))

    def _refresh(self) -> None:
        fresh = rows(self._read())
        if len(fresh) != len(self._rows):
            self.updateGeometry()
        self._rows = fresh
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), PAPER)
        title_font, value_font = QFont(self.font()), QFont(self.font())
        title_font.setBold(True)
        value_font.setPointSizeF(max(7.0, self.font().pointSizeF() * 0.9))
        width = self.width() - 2 * self.PAD
        for i, row in enumerate(self._rows):
            top = self.PAD + i * self.ROW_HEIGHT
            text = QRect(self.PAD, top, width, 16)
            p.setFont(title_font)
            p.setPen(INK)
            p.drawText(text, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, row.title)
            p.setFont(value_font)
            p.setPen(QUIET)
            p.drawText(text, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, row.value)
            bar = QRectF(self.PAD, top + 20, width, 7)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(TRACK)
            p.drawRoundedRect(bar, 3.5, 3.5)
            share = min(max(row.share, 0.0), 1.0)
            if share > 0:
                p.setBrush(row.colour)
                p.drawRoundedRect(
                    QRectF(bar.left(), bar.top(), bar.width() * share, bar.height()), 3.5, 3.5
                )
