"""Make the pictures in the README from his own art: an animated GIF of him going
about (``docs/zengo.gif``) and a sheet of poses and looks (``docs/poses.png``).

python scripts/make_readme_media.py

Qt can't write GIFs, so there's a small GIF encoder here (one palette, LZW).
"""

import os
import struct

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter

from zengo.sprites.clips import CLIPS
from zengo.sprites.frames import build_frames
from zengo.sprites.looks import Look, frame_in
from zengo.ui.sprites import frame_to_image, mirror

OUT = Path(__file__).resolve().parent.parent / "docs"
BACKGROUND = QColor("#f4efe8")
SCALE = 4
STEP = 0.06
"""Seconds per GIF frame."""


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


# --- The pictures ---------------------------------------------------------------------


def _clip_frames(name: str, seconds: float) -> list[str]:
    clip = CLIPS[name]
    names, t = [], 0.0
    while t < seconds:
        elapsed, i = t % sum(clip.durations) if clip.loop else min(t, sum(clip.durations) - 1e-6), 0
        while elapsed >= clip.durations[i]:
            elapsed -= clip.durations[i]
            i += 1
        names.append(clip.frames[i])
        t += STEP
    return names


def animation() -> list[QImage]:
    frames = build_frames()
    width, height, ground = 300, 150, 128
    scenes = [
        ("idle", 1.4, 0.0, 1),
        ("walk", 2.0, 30.0, 1),
        ("whistle", 1.2, 0.0, 1),
        ("preen", 2.0, 0.0, 1),
        ("bob", 1.2, 0.0, -1),
        ("walk", 2.0, -30.0, -1),
        ("alert", 1.0, 0.0, -1),
    ]
    x, out = 110.0, []
    for clip, seconds, speed, facing in scenes:
        for name in _clip_frames(clip, seconds):
            x += speed * STEP
            sprite = frame_to_image(frames[name], SCALE)
            if facing < 0:
                sprite = mirror(sprite)
            image = QImage(width, height, QImage.Format.Format_RGB32)
            image.fill(BACKGROUND)
            painter = QPainter(image)
            painter.fillRect(0, ground, width, height - ground, QColor("#e3d8ca"))
            painter.drawImage(round(x - 31 * SCALE), ground - 30 * SCALE, sprite)
            painter.end()
            out.append(image)
    return out


def poses() -> QImage:
    frames = build_frames()
    picks = [
        ("perch", Look()),
        ("front_perch", Look()),
        ("wings_up", Look()),
        ("petted_a", Look()),
        ("perch", Look(scarf=True)),
        ("shake_mid", Look(damp=True)),
        ("crouch", Look()),
        ("sulk", Look()),
    ]
    cell = 56 * SCALE
    sheet = QImage(cell * len(picks), 46 * SCALE, QImage.Format.Format_ARGB32)
    sheet.fill(BACKGROUND)
    painter = QPainter(sheet)
    for i, (name, look) in enumerate(picks):
        painter.drawImage(
            i * cell, SCALE, frame_to_image(frame_in(name, look, frames, frozenset()), SCALE)
        )
    painter.end()
    return sheet


def main() -> None:
    _app = QGuiApplication([])
    OUT.mkdir(exist_ok=True)
    write_gif(OUT / "zengo.gif", animation(), round(STEP * 100))
    poses().save(str(OUT / "poses.png"))
    print(f"wrote {OUT / 'zengo.gif'} and {OUT / 'poses.png'}")


if __name__ == "__main__":
    main()
