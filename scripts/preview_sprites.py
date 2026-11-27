"""Render frames in a grid into a PNG, for reviewing art changes.

python scripts/preview_sprites.py [out.png] [--scale N] [--look damp,scarf,dim]
                                  [--only NAME ...] [--columns N]
"""

import argparse
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter

from zengo.sprites.frames import build_frames
from zengo.sprites.looks import Look, frame_in
from zengo.ui.sprites import frame_to_image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", nargs="?", default="sprites.png")
    parser.add_argument("--scale", type=int, default=6)
    parser.add_argument("--look", default="", help="comma-separated: damp, scarf, dim")
    parser.add_argument("--only", nargs="*", help="frame names (prefixes) to show")
    parser.add_argument("--columns", type=int, default=12)
    args = parser.parse_args()

    _app = QGuiApplication([])
    frames = build_frames()
    wanted = {part for part in args.look.split(",") if part}
    look = Look(damp="damp" in wanted, scarf="scarf" in wanted, dim="dim" in wanted)
    names = [n for n in frames if not args.only or n.startswith(tuple(args.only))]
    images = [frame_to_image(frame_in(n, look, frames, frozenset()), args.scale) for n in names]
    gap = 2 * args.scale
    cell_w = max(i.width() for i in images) + gap
    cell_h = max(i.height() for i in images) + 3 * gap
    columns = min(args.columns, len(images))
    rows = -(-len(images) // columns)

    sheet = QImage(cell_w * columns + gap, cell_h * rows + gap, QImage.Format.Format_ARGB32)
    sheet.fill(QColor("#4a5d70"))
    painter = QPainter(sheet)
    painter.setPen(Qt.GlobalColor.white)
    for index, (name, image) in enumerate(zip(names, images, strict=True)):
        x = gap + (index % columns) * cell_w
        y = gap + (index // columns) * cell_h
        painter.drawImage(x, y, image)
        painter.drawText(x, y + image.height() + 2 * gap, name)
    painter.end()
    sheet.save(args.out)
    print(f"wrote {args.out} ({len(images)} frames)")


if __name__ == "__main__":
    main()
