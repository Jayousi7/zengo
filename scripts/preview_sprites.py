"""Render every frame side by side into a PNG, for reviewing art changes.

python scripts/preview_sprites.py [out.png] [--scale N]
"""

import argparse
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter

from zengo.sprites.frames import build_frames
from zengo.ui.sprites import frame_to_image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", nargs="?", default="sprites.png")
    parser.add_argument("--scale", type=int, default=6)
    args = parser.parse_args()

    _app = QGuiApplication([])
    frames = build_frames()
    images = [frame_to_image(f, args.scale) for f in frames.values()]
    gap = 2 * args.scale
    sheet_w = sum(i.width() for i in images) + gap * (len(images) + 1)
    sheet_h = max(i.height() for i in images) + 2 * gap

    sheet = QImage(sheet_w, sheet_h, QImage.Format.Format_ARGB32)
    sheet.fill(QColor("#4a5d70"))
    painter = QPainter(sheet)
    painter.setPen(Qt.GlobalColor.white)
    x = gap
    for name, image in zip(frames, images, strict=True):
        painter.drawImage(x, gap, image)
        painter.drawText(x, sheet_h - gap // 3, name)
        x += image.width() + gap
    painter.end()
    sheet.save(args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
