"""Composition root: builds the pieces, wires them together, runs the frame loop."""

from __future__ import annotations

import argparse
import random
import signal
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import QApplication

from zengo.animation import Animator
from zengo.behavior.body import Body, Facing
from zengo.behavior.context import Context
from zengo.behavior.machine import Brain
from zengo.config import Config
from zengo.sprites.clips import CLIPS
from zengo.sprites.compose import Frame
from zengo.sprites.frames import ANCHOR_COLUMN, CANVAS_WIDTH, GROUND_ROW, build_frames
from zengo.ui.branch_window import BranchWindow
from zengo.ui.qt_world import QtWorld
from zengo.ui.sheet_loader import SheetError, load_sheet
from zengo.ui.sprites import SpriteSheet
from zengo.ui.window import PetWindow

MAX_FRAME_DT = 0.1
"""Cap on simulated time per tick, so a suspended laptop doesn't fling Zengo off-screen."""


class Pet:
    def __init__(
        self,
        config: Config,
        frames: Mapping[str, Frame],
        rng: random.Random | None = None,
        *,
        branch_now: bool = False,
    ) -> None:
        self._config = config
        self._world = QtWorld()

        area = self._world.area_at(*self._world.cursor())
        body = Body(x=(area.left + area.right) / 2, y=area.bottom)
        animator = Animator(CLIPS, initial="idle")
        self._brain = Brain(Context(body, self._world, animator, config, rng or random.Random()))
        if branch_now:
            self._brain.ctx.scenery.grow(self._brain.ctx)

        self._sheet = SpriteSheet(frames, config.scale)
        self._window = PetWindow(config.drag_threshold)
        self._window.clicked.connect(self._brain.click)
        self._window.grabbed.connect(self._brain.grab)
        self._window.dragged.connect(self._brain.drag)
        self._window.released.connect(self._brain.release)
        self._branch = BranchWindow(config)
        self._window.released.connect(self._branch.keep_in_front)
        self._window.quit_requested.connect(QApplication.quit)

        self._timer = QTimer(timerType=Qt.TimerType.PreciseTimer, interval=1000 // config.fps)
        self._timer.timeout.connect(self._tick)
        self._last_tick = time.monotonic()

    def start(self) -> None:
        self._render()
        self._window.show()
        self._last_tick = time.monotonic()
        self._timer.start()

    def _tick(self) -> None:
        now = time.monotonic()
        dt = min(now - self._last_tick, MAX_FRAME_DT)
        self._last_tick = now
        self._world.sample()
        self._brain.tick(dt)
        self._render()

    def _render(self) -> None:
        ctx = self._brain.ctx
        body = ctx.body
        sprite = self._sheet.get(ctx.animator.frame, body.facing)
        # Mirroring flips the anchor column too; +0.5 centres on the column.
        anchor = ANCHOR_COLUMN if body.facing is Facing.RIGHT else CANVAS_WIDTH - 1 - ANCHOR_COLUMN
        left = body.x - self._config.px(anchor + 0.5)
        top = body.y - self._config.px(GROUND_ROW + 1)
        self._window.show_sprite(sprite, QPoint(round(left), round(top)))
        self._branch.show_branch(ctx.scenery.branch)


@dataclass(frozen=True)
class Options:
    config: Config
    sprites: Path | None
    """Aseprite JSON export whose frames replace the built-in ones by name."""
    branch_now: bool = False
    """Grow a branch straight away instead of waiting for one."""


def parse_args(argv: list[str]) -> Options:
    parser = argparse.ArgumentParser(prog="zengo", description="Zengo the desktop cockatiel.")
    parser.add_argument(
        "--scale", type=int, default=Config.scale, help="screen pixels per art pixel"
    )
    parser.add_argument("--fps", type=int, default=Config.fps)
    parser.add_argument(
        "--sprites",
        type=Path,
        metavar="SHEET.json",
        help="Aseprite JSON export overriding built-in frames by name",
    )
    parser.add_argument(
        "--branch-now",
        action="store_true",
        help="grow a branch for Zengo straight away instead of waiting for one",
    )
    args = parser.parse_args(argv)
    if args.scale < 1 or args.fps < 1:
        parser.error("--scale and --fps must be positive")
    return Options(Config(scale=args.scale, fps=args.fps), args.sprites, args.branch_now)


def main(argv: list[str] | None = None) -> int:
    options = parse_args(sys.argv[1:] if argv is None else argv)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Zengo")

    frames = build_frames()
    if options.sprites is not None:
        try:
            frames.update(load_sheet(options.sprites, frames.keys()))
        except (OSError, KeyError, SheetError) as error:
            print(f"zengo: cannot load sprites from {options.sprites}: {error}", file=sys.stderr)
            return 2

    # Let Ctrl+C in a terminal quit cleanly; the frame timer gives Python a chance to run it.
    signal.signal(signal.SIGINT, lambda *_: app.quit())

    pet = Pet(options.config, frames, branch_now=options.branch_now)
    pet.start()
    return app.exec()
