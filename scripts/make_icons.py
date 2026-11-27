"""Make Zengo's app icon (his head, from his own pixel art) for the packages:
``packaging/icons/zengo.png`` (256 px, Linux) and ``zengo.ico`` (Windows).

python scripts/make_icons.py
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter

from zengo.sprites.frames import build_frames
from zengo.ui.tray import head_icon

OUT = Path(__file__).resolve().parent.parent / "packaging" / "icons"


def icon(size: int) -> QImage:
    """His head, centred, with a little room round it."""
    head = head_icon(build_frames()["perch"], round(size * 0.86)).toImage()
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.drawImage((size - head.width()) // 2, (size - head.height()) // 2, head)
    painter.end()
    return image


def main() -> None:
    _app = QGuiApplication([])
    OUT.mkdir(parents=True, exist_ok=True)
    icon(256).save(str(OUT / "zengo.png"))
    if not icon(256).save(str(OUT / "zengo.ico")):
        raise SystemExit("this Qt can't write .ico files")
    print(f"wrote {OUT / 'zengo.png'} and {OUT / 'zengo.ico'}")


if __name__ == "__main__":
    main()
