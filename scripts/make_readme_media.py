"""Make the README's animation from his own art: Zengo saying hello, strolling,
singing, being petted and taking a bath (``docs/zengo.gif``).

python scripts/make_readme_media.py

Qt can't write GIFs, so there's a small GIF encoder here (one palette, LZW).
"""

import math
import os
import random
import struct

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QImage, QPainter

from zengo.behavior.effects import Effects
from zengo.sprites.bath import DISH_HEIGHT, DISH_WIDTH, build_dish
from zengo.sprites.clips import CLIPS
from zengo.sprites.effects import build_particles, particle_name
from zengo.sprites.frames import ANCHOR_COLUMN, CANVAS_WIDTH, GROUND_ROW, build_frames
from zengo.sprites.looks import Look, frame_in
from zengo.ui.sprites import frame_to_image, mirror

OUT = Path(__file__).resolve().parent.parent / "docs"


# --- A small GIF encoder ------------------------------------------------------------


def _lzw(indices: bytes, min_size: int = 8) -> bytes:
    clear, end = 1 << min_size, (1 << min_size) + 1
    table = {bytes([i]): i for i in range(clear)}
    size, next_code = min_size + 1, end + 1
    bits = count = 0
    out = bytearray()

    def emit(code: int) -> None:
        nonlocal bits, count
        bits |= code << count
        count += size
        while count >= 8:
            out.append(bits & 0xFF)
            bits >>= 8
            count -= 8

    emit(clear)
    run = b""
    for i in indices:
        grown = run + bytes([i])
        if grown in table:
            run = grown
            continue
        emit(table[run])
        if next_code < 4096:
            table[grown] = next_code
            next_code += 1
            if next_code > (1 << size) and size < 12:
                size += 1
        else:
            emit(clear)
            table = {bytes([i]): i for i in range(clear)}
            size, next_code = min_size + 1, end + 1
        run = bytes([i])
    if run:
        emit(table[run])
    emit(end)
    if count:
        out.append(bits & 0xFF)
    return bytes(out)


def write_gif(path: Path, frames: list[QImage], delay_cs: int) -> None:
    """``frames`` (all one size, few colours) as a looping GIF."""
    colours: dict[int, int] = {}
    indexed = []
    for image in frames:
        row = bytearray()
        for y in range(image.height()):
            for x in range(image.width()):
                rgb = image.pixel(x, y) & 0xFFFFFF
                if rgb not in colours:
                    if len(colours) >= 256:
                        raise ValueError("more than 256 colours")
                    colours[rgb] = len(colours)
                row.append(colours[rgb])
        indexed.append(bytes(row))
    palette = bytearray()
    for rgb in colours:
        palette += bytes(((rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF))
    palette += bytes(3 * (256 - len(colours)))
    w, h = frames[0].width(), frames[0].height()
    out = bytearray(b"GIF89a" + struct.pack("<HHBBB", w, h, 0xF7, 0, 0) + palette)
    out += b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"  # loop for ever
    for data in indexed:
        out += b"\x21\xf9\x04\x00" + struct.pack("<H", delay_cs) + b"\x00\x00"
        out += b"\x2c" + struct.pack("<HHHHB", 0, 0, w, h, 0) + b"\x08"
        encoded = _lzw(data)
        for i in range(0, len(encoded), 255):
            chunk = encoded[i : i + 255]
            out += bytes([len(chunk)]) + chunk
        out += b"\x00"
    out += b"\x3b"
    path.write_bytes(bytes(out))


# --- The animation ------------------------------------------------------------

W, H, GROUND, SC, STEP = 520, 260, 222, 3, 0.05
SKY, FLOOR, LINE = QColor("#f6efe6"), QColor("#e7d9c8"), QColor("#d9c7b2")
INK, PAPER, HEART = QColor("#3a2a30"), QColor("#fcf7ef"), QColor("#d9576b")
DISH_X = 300
STAND = (DISH_WIDTH / 2 + 7) * SC  # where he hops in from


def clip_frame(name: str, t: float) -> str:
    clip = CLIPS[name]
    total = sum(clip.durations)
    t = t % total if clip.loop else min(t, total - 1e-6)
    for frame, d in zip(clip.frames, clip.durations, strict=True):
        if t < d:
            return frame
        t -= d
    return clip.frames[-1]


def bubble(p: QPainter, text: str, x: float, y: float, colour: QColor) -> None:
    s = SC
    font = QFont()
    font.setPixelSize(7 * s)
    font.setBold(True)
    font.setStyleStrategy(QFont.StyleStrategy.NoAntialias)  # few colours, for the GIF
    m = QFontMetrics(font)
    bw = m.horizontalAdvance(text) + 8 * s
    bh = m.height() + 6 * s
    bw += -bw % s
    bh += -bh % s
    left, top = round(x - 4 * s), round(y - bh - 3 * s)
    p.fillRect(left + s, top, bw - 2 * s, bh, INK)
    p.fillRect(left, top + s, bw, bh - 2 * s, INK)
    p.fillRect(left + 2 * s, top + s, bw - 4 * s, bh - 2 * s, PAPER)
    p.fillRect(left + s, top + 2 * s, bw - 2 * s, bh - 4 * s, PAPER)
    for row in range(3):
        width = (3 - row) * s
        tx = left + 4 * s + s // 2 - s - (width - 2 * s) // 2
        p.fillRect(tx, top + bh - s + row * s, width + 2 * s, s, INK)
        if row < 2:
            p.fillRect(tx + s, top + bh - s + row * s, width, s, PAPER)
    p.setFont(font)
    p.setPen(colour)
    p.drawText(QRect(left, top, bw, bh), Qt.AlignmentFlag.AlignCenter, text)


def animation() -> list[QImage]:
    """Hello, a stroll, a song, a cuddle, a bath, and fresh as anything."""
    frames = build_frames()
    particles = {n: frame_to_image(f, SC) for n, f in build_particles().items()}
    dish = frame_to_image(build_dish(0), SC)
    dish_splash = frame_to_image(build_dish(0, True), SC)
    rng = random.Random(4)
    effects = Effects()
    # (clip, seconds, speed px/s, facing, cloud, cloud colour, look, extra)
    scenes = [
        ("idle", 1.4, 0, 1, "hi! ♪", INK, Look(), None),
        ("walk", 1.8, 40, 1, None, INK, Look(), None),
        ("whistle", 1.6, 0, 1, "pretty bird! ♫", INK, Look(), None),
        ("petted", 1.8, 0, 1, "♥", HEART, Look(), None),
        ("walk", 2.0, 50, 1, None, INK, Look(), None),
        ("bath_hop", 0.45, 0, 1, None, INK, Look(), "hop_in"),
        ("bath_dip", 1.4, 0, 1, None, INK, Look(), "in"),
        ("bath_splash", 1.8, 0, 1, None, INK, Look(), "splash"),
        ("bath_hop", 0.45, 0, 1, None, INK, Look(damp=True), "hop_out"),
        ("shake", 1.0, 0, 1, None, INK, Look(damp=True), "shake"),
        ("front_idle", 1.8, 0, 1, "ahh, fresh! ♪", INK, Look(damp=True), None),
    ]
    x, out = 70.0, []
    for index, (clip, seconds, speed, facing, cloud, colour, look, extra) in enumerate(scenes):
        start_x = x
        n = round(seconds / STEP)
        for i in range(n):
            t = i * STEP
            y_off = 0.0
            if extra == "hop_in":
                x = start_x + (DISH_X - start_x) * (i + 1) / n
                y_off = -9 * SC * math.sin(math.pi * (i + 1) / n)
            elif extra == "hop_out":
                x = DISH_X + STAND * (i + 1) / n
                y_off = -9 * SC * math.sin(math.pi * (i + 1) / n)
            else:
                x += speed * STEP
            if extra == "splash" and i % 2 == 0:
                effects.splash(x + rng.uniform(-10, 30), GROUND - 18, GROUND, rng, SC, 2)
            if extra == "shake" and i == 0:
                effects.splash(x, GROUND - 42, GROUND, rng, SC, 12)
            effects.update(STEP, SC)
            name = clip_frame(clip, t)
            sprite = frame_to_image(frame_in(name, look, frames, frozenset()), SC)
            anchor = ANCHOR_COLUMN
            if facing < 0:
                sprite, anchor = mirror(sprite), CANVAS_WIDTH - 1 - ANCHOR_COLUMN
            image = QImage(W, H, QImage.Format.Format_RGB32)
            image.fill(SKY)
            p = QPainter(image)
            p.fillRect(0, GROUND, W, H - GROUND, FLOOR)
            p.fillRect(0, GROUND, W, SC, LINE)
            p.drawImage(
                round(x - (anchor + 0.5) * SC),
                round(GROUND - (GROUND_ROW + 1) * SC + y_off),
                sprite,
            )
            if index >= 4:  # his bath, put out as he sets off for it
                pic = dish_splash if extra == "splash" else dish
                p.drawImage(
                    round(DISH_X - (DISH_WIDTH + 2) / 2 * SC), GROUND - (DISH_HEIGHT + 1) * SC, pic
                )
            for part in effects.particles:
                img = particles[particle_name(part.kind, part.tilt)]
                p.drawImage(round(part.x - img.width() / 2), round(part.y - img.height() / 2), img)
            if cloud and i < n - 2:
                bubble(p, cloud, x, GROUND - 33 * SC, colour)
            p.end()
            out.append(image)
    return out


def main() -> None:
    _app = QGuiApplication([])
    OUT.mkdir(exist_ok=True)
    write_gif(OUT / "zengo.gif", animation(), round(STEP * 100))
    print(f"wrote {OUT / 'zengo.gif'}")


if __name__ == "__main__":
    main()
