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

from PySide6.QtCore import QPoint, QPointF, QRect, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMenu

from zengo.animation import Animator
from zengo.behavior.body import Body, Facing
from zengo.behavior.context import Context
from zengo.behavior.machine import Brain
from zengo.behavior.memory import restore, snapshot
from zengo.config import Config, quick
from zengo.sprites.cage import CAGE_WIDTH, FLOOR
from zengo.sprites.clips import CLIPS
from zengo.sprites.compose import Frame
from zengo.sprites.food import MAX_STACKS
from zengo.sprites.frames import ANCHOR_COLUMN, CANVAS_WIDTH, GROUND_ROW, build_frames
from zengo.ui.branch_window import BranchWindow
from zengo.ui.bubble_window import BubbleWindow
from zengo.ui.cage_window import CageWindow, MountWindow
from zengo.ui.catch_overlay import CatchOverlay
from zengo.ui.food_window import FoodWindow
from zengo.ui.qt_world import QtWorld
from zengo.ui.sheet_loader import SheetError, load_sheet
from zengo.ui.sprites import SpriteSheet
from zengo.ui.state_file import StateFile
from zengo.ui.window import PetWindow

MAX_FRAME_DT = 0.1
"""Cap on simulated time per tick, so a suspended laptop doesn't fling Zengo off-screen."""

SPEECH_HEIGHT = 32
"""Art px above his feet where a speech cloud's tail points: just over his crest
at its tallest, so no pose of his pokes into the cloud."""

SAVE_EVERY_MS = 15_000
"""How often what he remembers is written down, besides when he quits."""

SPEECH_GLIDE = 0.3
"""Share of the way a speech cloud moves towards where it belongs each frame."""


class Pet:
    def __init__(
        self,
        config: Config,
        frames: Mapping[str, Frame],
        rng: random.Random | None = None,
        *,
        branch_now: bool = False,
        memory: StateFile | None = None,
    ) -> None:
        self._config = config
        self._world = QtWorld()

        area = self._world.area_at(*self._world.cursor())
        body = Body(x=(area.left + area.right) / 2, y=area.bottom)
        animator = Animator(CLIPS, initial="idle")
        self._brain = Brain(Context(body, self._world, animator, config, rng or random.Random()))
        if branch_now:
            self._brain.ctx.scenery.grow(self._brain.ctx)
        self._memory = memory
        if memory is not None:
            restore(self._brain.ctx, memory.load())
            self._save_timer = QTimer(interval=SAVE_EVERY_MS)
            self._save_timer.timeout.connect(self.save)
            app = QApplication.instance()
            if app is not None:
                app.aboutToQuit.connect(self.save)

        self._sheet = SpriteSheet(frames, config.scale)
        self._window = PetWindow(config.drag_threshold)
        self._window.clicked.connect(self._brain.click)
        self._window.double_clicked.connect(self._brain.double_click)
        self._window.grabbed.connect(self._brain.grab)
        self._window.dragged.connect(self._brain.drag)
        self._window.released.connect(self._brain.release)
        self._branch = BranchWindow(config)
        self._window.released.connect(self._branch.keep_in_front)
        self._bubble = BubbleWindow(config.scale)
        self._window.menu_requested.connect(self._show_menu)
        self._cage = CageWindow(config, config.drag_threshold)
        self._cage.grabbed.connect(self._brain.cage_grab)
        self._cage.dragged.connect(self._brain.cage_drag)
        self._cage.released.connect(self._brain.cage_release)
        self._cage.menu_requested.connect(self._show_menu)
        self._mount = MountWindow(config)
        self._food = FoodWindow(config)
        self._dish = FoodWindow(config)
        self._overlay: CatchOverlay | None = None
        self._door_was_open = False
        self._speech_at: QPointF | None = None
        self._speech_of: object = None

        self._timer = QTimer(timerType=Qt.TimerType.PreciseTimer, interval=1000 // config.fps)
        self._timer.timeout.connect(self._tick)
        self._last_tick = time.monotonic()

    def start(self) -> None:
        self._render()
        self._window.show()
        self._last_tick = time.monotonic()
        self._timer.start()
        if self._memory is not None:
            self._save_timer.start()

    def save(self) -> None:
        """Write down what he remembers: fullness, hunger, the seeds put out."""
        if self._memory is not None:
            self._memory.save(snapshot(self._brain.ctx))

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
        desktop = QGuiApplication.primaryScreen().virtualGeometry()
        self._window.show_sprite(sprite, QPoint(round(left), round(top)), desktop)
        self._branch.show_branch(ctx.scenery.branch)
        food = ctx.food
        if food is None:
            self._food.show_pile(None)
        else:
            self._food.show_pile(food.pile, food.x, food.y)
        cage = ctx.cage
        if cage is None or cage.door_open:
            self._dish.show_pile(None)
        elif self._dish.show_pile(cage.dish, cage.shown_x, cage.y):
            self._cage.raise_()  # the dish sits behind the bars
        self._show_cage()
        self._show_speech()

    def _show_cage(self) -> None:
        cage = self._brain.ctx.cage
        self._mount.show_mount(cage)
        self._cage.show_cage(cage, QGuiApplication.primaryScreen().virtualGeometry())
        door_open = cage is not None and cage.door_open
        if door_open and not self._door_was_open:
            self._window.raise_()  # out through the door, in front of the bars
        self._door_was_open = door_open

    # --- Menu and catching -------------------------------------------------------

    def _show_menu(self, where: QPoint) -> None:
        menu = QMenu()
        stacks = self._brain.food_stacks
        feed = menu.addAction(f"Feed Zengo ({stacks}/{MAX_STACKS})", self._brain.feed)
        feed.setEnabled(stacks < MAX_STACKS)
        if self._brain.caged:
            menu.addAction("Let Zengo out", self._brain.let_out)
        else:
            menu.addAction("Catch Zengo", self._start_catching)
        menu.addSeparator()
        menu.addAction("Quit Zengo", QApplication.quit)
        menu.exec(where)

    def _start_catching(self) -> None:
        body = self._brain.ctx.body
        here = QPoint(round(body.x), round(body.y) - 1)
        screen = QGuiApplication.screenAt(here) or QGuiApplication.primaryScreen()
        self._overlay = CatchOverlay(screen)
        self._overlay.selected.connect(
            lambda box: self._brain.catch_in(box.left(), box.top(), box.right(), box.bottom())
        )
        self._overlay.start()

    def _show_speech(self) -> None:
        """Put the cloud above him. One anchor whatever he's doing: centred over his
        anchor, just clear of his tallest pose (crest up), or above the cage he's in.
        It glides after him rather than snapping, so turning round, nodding or being
        swung about doesn't make it jump."""
        ctx = self._brain.ctx
        speech = ctx.speech
        if speech is None:
            self._bubble.say(None, QPoint(), QRect())
            self._speech_at = None
            return
        body, px = ctx.body, self._config.px
        target, keep_clear = QPointF(body.x, body.y - px(SPEECH_HEIGHT)), None
        cage = ctx.cage
        if cage is not None and not cage.door_open:
            target = QPointF(cage.shown_x, cage.y - px(FLOOR + 1))  # above the hook
            if cage.pivot is not None:  # hung: beside it, keeping the chain in view
                half = px(CAGE_WIDTH / 2)
                keep_clear = QRect(
                    round(cage.shown_x - half),
                    round(cage.pivot[1]),
                    round(2 * half),
                    round(cage.y - cage.pivot[1]),
                )
                target = QPointF(cage.shown_x, cage.y - px(20))
        if self._speech_at is None or speech is not self._speech_of:
            self._speech_at = target  # a new cloud appears right where it belongs
        else:
            self._speech_at += (target - self._speech_at) * SPEECH_GLIDE
        self._speech_of = speech
        head = self._speech_at.toPoint()
        screen = QGuiApplication.screenAt(head) or QGuiApplication.primaryScreen()
        self._bubble.say(speech.text, head, screen.availableGeometry(), speech.mood, keep_clear)


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
        "--quick",
        action="store_true",
        help="short timers for trying things out: escapes within seconds, hunger every 20 s",
    )
    parser.add_argument(
        "--branch-now",
        action="store_true",
        help="grow a branch for Zengo straight away instead of waiting for one",
    )
    args = parser.parse_args(argv)
    if args.scale < 1 or args.fps < 1:
        parser.error("--scale and --fps must be positive")
    config = Config(scale=args.scale, fps=args.fps)
    return Options(quick(config) if args.quick else config, args.sprites, args.branch_now)


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

    # Quit cleanly on Ctrl+C in a terminal, and when the session ends (logout and
    # shutdown send SIGTERM), so what he remembers gets saved. The frame timer gives
    # Python a chance to run the handlers.
    for stop in (signal.SIGINT, signal.SIGTERM):
        signal.signal(stop, lambda *_: app.quit())

    pet = Pet(options.config, frames, branch_now=options.branch_now, memory=StateFile.default())
    pet.start()
    return app.exec()
