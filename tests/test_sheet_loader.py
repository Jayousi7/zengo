import json

import pytest
from PySide6.QtGui import QColor, QImage

from zengo.sprites.frames import CANVAS_HEIGHT, CANVAS_WIDTH
from zengo.ui.sheet_loader import SheetError, load_sheet


def write_sheet(tmp_path, frames, layout="hash"):
    """Two frames side by side; the first has one red pixel at (3, 4)."""
    image = QImage(CANVAS_WIDTH * 2, CANVAS_HEIGHT, QImage.Format.Format_RGBA8888)
    image.fill(QColor(0, 0, 0, 0))
    image.setPixelColor(3, 4, QColor(255, 0, 0, 255))
    image.save(str(tmp_path / "sheet.png"))
    rects = {
        name: {"frame": {"x": i * CANVAS_WIDTH, "y": 0, "w": w, "h": h}}
        for i, (name, (w, h)) in enumerate(frames.items())
    }
    entries = rects if layout == "hash" else [{"filename": n, **r} for n, r in rects.items()]
    path = tmp_path / "sheet.json"
    path.write_text(json.dumps({"frames": entries, "meta": {"image": "sheet.png"}}))
    return path


@pytest.mark.parametrize("layout", ["hash", "array"])
def test_loads_named_frames(tmp_path, layout):
    size = (CANVAS_WIDTH, CANVAS_HEIGHT)
    path = write_sheet(tmp_path, {"perch": size, "blink": size}, layout)
    frames = load_sheet(path, {"perch", "blink"})
    assert frames.keys() == {"perch", "blink"}
    assert frames["perch"].pixel(3, 4) == (255, 0, 0, 255)
    assert frames["perch"].pixel(0, 0) is None
    assert frames["blink"].pixel(3, 4) is None


def test_rejects_unknown_frame(tmp_path):
    path = write_sheet(tmp_path, {"dance": (CANVAS_WIDTH, CANVAS_HEIGHT)})
    with pytest.raises(SheetError, match="unknown frame 'dance'"):
        load_sheet(path, {"perch"})


def test_rejects_wrong_size(tmp_path):
    path = write_sheet(tmp_path, {"perch": (CANVAS_WIDTH - 1, CANVAS_HEIGHT)})
    with pytest.raises(SheetError, match="expected"):
        load_sheet(path, {"perch"})
