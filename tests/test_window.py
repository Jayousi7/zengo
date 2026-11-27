"""Mouse gestures on the pet window: clicks, double-clicks, drags."""

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPixmap, QRegion
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from zengo.ui.sprites import Sprite
from zengo.ui.window import PetWindow


@pytest.fixture
def window():
    pixmap = QPixmap(40, 40)
    pixmap.fill(Qt.GlobalColor.white)
    win = PetWindow(drag_threshold=4)
    win.show_sprite(Sprite(pixmap, QRegion(0, 0, 40, 40)), QPoint(0, 0))
    win.show()
    events = []
    win.clicked.connect(lambda: events.append("click"))
    win.double_clicked.connect(lambda: events.append("double"))
    win.grabbed.connect(lambda *_: events.append("grab"))
    win.released.connect(lambda: events.append("release"))
    yield win, events
    win.close()


def wait_out_double_click_interval():
    QTest.qWait(QApplication.styleHints().mouseDoubleClickInterval() + 80)


def test_a_single_click_is_a_poke_once_no_second_click_follows(window):
    win, events = window
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
    assert events == []  # held back: it might be the start of a double-click
    wait_out_double_click_interval()
    assert events == ["click"]


def test_a_double_click_is_not_also_a_poke(window):
    win, events = window
    QTest.mouseDClick(win, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
    wait_out_double_click_interval()
    assert events == ["double"]


def test_pressing_and_moving_is_a_drag_not_a_click(window):
    win, events = window
    QTest.mousePress(win, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
    QTest.mouseMove(win, QPoint(40, 30))
    QTest.mouseRelease(win, Qt.MouseButton.LeftButton, pos=QPoint(40, 30))
    wait_out_double_click_interval()
    assert events == ["grab", "release"]
