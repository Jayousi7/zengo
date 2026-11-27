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


# --- Catching overlay and cage window ------------------------------------------


def test_dragging_a_box_on_the_overlay_reports_it_in_screen_coordinates():
    from PySide6.QtGui import QGuiApplication

    from zengo.ui.catch_overlay import CatchOverlay

    overlay = CatchOverlay(QGuiApplication.primaryScreen())
    boxes = []
    overlay.selected.connect(boxes.append)
    overlay.start()
    origin = overlay.geometry().topLeft()
    QTest.mousePress(overlay, Qt.MouseButton.RightButton, pos=QPoint(100, 100))
    QTest.mouseMove(overlay, QPoint(220, 180))
    QTest.mouseRelease(overlay, Qt.MouseButton.RightButton, pos=QPoint(220, 180))
    assert len(boxes) == 1
    assert boxes[0].topLeft() == origin + QPoint(100, 100)
    assert boxes[0].width() >= 120 and boxes[0].height() >= 80


def test_escape_cancels_catching():
    from PySide6.QtGui import QGuiApplication

    from zengo.ui.catch_overlay import CatchOverlay

    overlay = CatchOverlay(QGuiApplication.primaryScreen())
    cancelled = []
    overlay.cancelled.connect(lambda: cancelled.append(True))
    overlay.start()
    QTest.keyClick(overlay, Qt.Key.Key_Escape)
    assert cancelled == [True]


def test_the_cage_window_reports_drags():
    from zengo.config import Config
    from zengo.ui.cage_window import CageWindow

    cage = CageWindow(Config(), drag_threshold=4)
    cage.show()
    events = []
    cage.grabbed.connect(lambda *_: events.append("grab"))
    cage.dragged.connect(lambda *_: events.append("drag"))
    cage.released.connect(lambda: events.append("release"))
    middle = QPoint(cage.width() // 2, cage.height() // 2)
    QTest.mousePress(cage, Qt.MouseButton.LeftButton, pos=middle)
    QTest.mouseMove(cage, middle + QPoint(30, -40))
    QTest.mouseRelease(cage, Qt.MouseButton.LeftButton, pos=middle + QPoint(30, -40))
    assert events[0] == "grab" and "drag" in events and events[-1] == "release"
    cage.close()
