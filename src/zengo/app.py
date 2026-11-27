"""Composition root: builds the pieces, wires them together, runs the frame loop."""

from __future__ import annotations

import argparse
import os
import random
import signal
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRect, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMenu, QWidgetAction

from zengo.animation import Animator
from zengo.behavior.body import Body, Facing
from zengo.behavior.context import Context
from zengo.behavior.machine import Brain
from zengo.behavior.memory import restore, snapshot
from zengo.config import Config
from zengo.settings import Flags, Settings, build_config, migrated
from zengo.sprites.cage import CAGE_WIDTH, FLOOR
from zengo.sprites.clips import CLIPS
from zengo.sprites.compose import Frame
from zengo.sprites.food import MAX_STACKS
from zengo.sprites.frames import ANCHOR_COLUMN, CANVAS_WIDTH, GROUND_ROW, build_frames
from zengo.ui.autostart import Autostart
from zengo.ui.branch_window import BranchWindow
from zengo.ui.bubble_window import BubbleWindow
from zengo.ui.cage_window import CageWindow, MountWindow
from zengo.ui.catch_overlay import CatchOverlay
from zengo.ui.food_window import FoodWindow
from zengo.ui.qt_world import QtWorld
from zengo.ui.settings_window import SettingsWindow
from zengo.ui.sheet_loader import SheetError, load_sheet
from zengo.ui.sound import SoundPlayer
from zengo.ui.sprites import SpriteSheet
from zengo.ui.state_file import StateFile
from zengo.ui.status_panel import StatusPanel
from zengo.ui.window import PetWindow

MAX_FRAME_DT = 0.1
"""Cap on simulated time per tick, so a suspended laptop doesn't fling Zengo off-screen."""

SPEECH_HEIGHT = 32
"""Art px above his feet where a speech cloud's tail points: just over his crest
at its tallest, so no pose of his pokes into the cloud."""

MENU_STYLE = """
QMenu { background: #231c1f; color: #f1e6da; border: 1px solid #3a3034; padding: 4px 0; }
QMenu::item { padding: 6px 22px; background: transparent; }
QMenu::item:selected { background: #3a3034; }
QMenu::item:disabled { color: #6e6064; }
QMenu::separator { height: 1px; background: #3a3034; margin: 4px 8px; }
"""
"""Dark, to match the needs panel at its top."""

RESTACK_EVERY = 1.0
"""Seconds between checks that the windows are in their proper order."""

SAVE_EVERY_MS = 15_000
"""How often what he remembers is written down, besides when he quits."""

SPEECH_GLIDE = 0.3
"""Share of the way a speech cloud moves towards where it belongs each frame."""


def _open_menus() -> list[QMenu]:
    return [w for w in QApplication.topLevelWidgets() if isinstance(w, QMenu) and w.isVisible()]


def _menu_open() -> bool:
    return bool(_open_menus())


class Pet:
    def __init__(
        self,
        config: Config,
        frames: Mapping[str, Frame],
        rng: random.Random | None = None,
        *,
        branch_now: bool = False,
        memory: StateFile | None = None,
        settings: Settings | None = None,
        settings_file: StateFile | None = None,
        flags: Flags | None = None,
        autostart: Autostart | None = None,
    ) -> None:
        self._config = config
        self._frames = frames
        self._settings = settings or Settings(scale=config.scale)
        self._settings_file = settings_file
        self._flags = flags or Flags()
        self._autostart = autostart or Autostart(None)
        self._settings_window: SettingsWindow | None = None
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
            self._brain.resume()
            self._save_timer = QTimer(interval=SAVE_EVERY_MS)
            self._save_timer.timeout.connect(self.save)
            app = QApplication.instance()
            if app is not None:
                app.aboutToQuit.connect(self.save)

        self._brain.ctx.sound_on = self._settings.sound
        self._window = PetWindow(config.drag_threshold)
        self._window.clicked.connect(self._brain.click)
        self._window.double_clicked.connect(self._brain.double_click)
        self._window.grabbed.connect(self._brain.grab)
        self._window.dragged.connect(self._brain.drag)
        self._window.released.connect(self._brain.release)
        # Windows that must stay in front of him are made his window's transients:
        # the window manager then keeps them above it whatever it's asked or clicked.
        # (Asking it to raise them doesn't work: it refuses, to stop windows that
        # never take focus from pushing in front of others.)
        self._branch = BranchWindow(config, in_front_of=self._window)
        # A click or drag makes the window manager raise his window over the
        # branch and cage: put the stacking right again straight away.
        for gesture in (self._window.clicked, self._window.double_clicked, self._window.released):
            gesture.connect(self.restack)
        self._window.grabbed.connect(lambda *_: self.restack())
        self._window.menu_requested.connect(self._show_menu)
        self._build_windows()
        self._sound = SoundPlayer(self._settings.volume)
        if (app := QApplication.instance()) is not None:
            app.aboutToQuit.connect(self._sound.close)  # tidy away the sound files
        self._overlay: CatchOverlay | None = None
        self._door_was_open = False
        self._restacked = -RESTACK_EVERY
        self._showing: tuple[bool, ...] = ()
        self._speech_at: QPointF | None = None
        self._speech_of: object = None

        self._timer = QTimer(timerType=Qt.TimerType.PreciseTimer, interval=1000 // config.fps)
        self._timer.timeout.connect(self._tick)
        self._last_tick = time.monotonic()

    def _build_windows(self) -> None:
        """Make the windows drawn at his size: everything but his own window,
        which simply takes whatever sprite it's given."""
        config = self._config
        self._sheet = SpriteSheet(self._frames, config.scale)
        self._branch = BranchWindow(config, in_front_of=self._window)
        self._bubble = BubbleWindow(config.scale, in_front_of=self._window)
        self._cage = CageWindow(config, config.drag_threshold, in_front_of=self._window)
        self._cage.grabbed.connect(self._brain.cage_grab)
        self._cage.dragged.connect(self._brain.cage_drag)
        self._cage.released.connect(self._brain.cage_release)
        self._cage.menu_requested.connect(self._show_menu)
        self._mount = MountWindow(config)
        self._food = FoodWindow(config)
        self._dish = FoodWindow(config, in_front_of=self._window)

    def _resize(self) -> None:
        """He's changed size: redraw everything at the new scale and put him and
        his cage where they belong at it."""
        for window in (self._branch, self._bubble, self._cage, self._mount, self._food, self._dish):
            window.hide()
            window.deleteLater()
        self._build_windows()
        self._speech_at = None
        ctx = self._brain.ctx
        area = ctx.area()
        ctx.body.x = area.clamp_x(ctx.body.x, ctx.margin)
        cage = ctx.cage
        if cage is not None and cage.mount in ("chain", "shelf"):
            cage.grab(cage.x, cage.y)  # hang it again, or shelve it, at the new size
            cage.release(ctx)
            cage.sway_speed = 0.0
            cage.events.clear()
        self._showing = ()
        self._render()

    def start(self) -> None:
        self._render()
        self._window.show()
        self.restack()  # windows restored from memory came up before his
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
        else:
            self._dish.show_pile(cage.dish, cage.shown_x, cage.y)
        self._show_cage()
        self._show_speech()
        self._play_sounds()
        showing = tuple(w.isVisible() for w in self._layers())
        if _menu_open():
            pass  # leave the order alone while his menu is up: it stays on top
        elif showing != self._showing or time.monotonic() - self._restacked >= RESTACK_EVERY:
            self._showing = showing  # one has just come or gone: order them at once
            self.restack()

    def _layers(self) -> list:
        return [
            self._mount,
            self._food,
            self._window,
            self._branch,
            self._dish,
            self._cage,
            self._bubble,
        ]

    def restack(self) -> None:
        """Put the windows in their proper order, back to front.

        Behind Zengo: the chain or shelf and the seed pile. In front of him: the
        branch (so his tail hangs behind it), the dish and the cage (so he's behind
        the bars; once the door's open he comes out in front), and the speech cloud.
        Window managers reorder windows on clicks and when new ones appear, so this
        is done at start, after any click or drag on him, and every so often.
        """
        self._restacked = time.monotonic()
        cage = self._brain.ctx.cage
        door_open = cage is not None and cage.door_open
        back_to_front = self._layers()
        if door_open:
            back_to_front.remove(self._window)
            back_to_front.insert(back_to_front.index(self._cage) + 1, self._window)
        for window in back_to_front:
            if window.isVisible():
                window.raise_()
        for menu in _open_menus():  # his menu, if it's open, above them all
            menu.raise_()

    def _play_sounds(self) -> None:
        ctx = self._brain.ctx
        for name in ctx.sounds:
            if ctx.sound_on:
                self._sound.play(name)
        ctx.sounds.clear()

    def _show_cage(self) -> None:
        cage = self._brain.ctx.cage
        self._mount.show_mount(cage)
        self._cage.show_cage(cage, QGuiApplication.primaryScreen().virtualGeometry())
        door_open = cage is not None and cage.door_open
        if door_open != self._door_was_open:
            self.restack()  # out through the door, in front of the bars
        self._door_was_open = door_open

    # --- Menu and catching -------------------------------------------------------

    def _show_menu(self, where: QPoint) -> None:
        menu = QMenu()
        menu.setStyleSheet(MENU_STYLE)
        panel = QWidgetAction(menu)
        panel.setDefaultWidget(StatusPanel(self._brain.status))
        menu.addAction(panel)
        menu.addSeparator()
        stacks = self._brain.food_stacks
        feed = menu.addAction(f"Feed Zengo ({stacks}/{MAX_STACKS})", self._brain.feed)
        feed.setEnabled(stacks < MAX_STACKS)
        if self._brain.caged:
            menu.addAction("Let Zengo out", self._brain.let_out)
        else:
            menu.addAction("Catch Zengo", self._start_catching)
        sound = menu.addAction("Sounds", self._toggle_sound)
        sound.setCheckable(True)
        sound.setChecked(self._brain.ctx.sound_on)
        if (login := self._autostart.enabled()) is not None:
            start = menu.addAction("Start at login", lambda: self.set_autostart(not login))
            start.setCheckable(True)
            start.setChecked(login)
        menu.addAction("Settings…", self.open_settings)
        menu.addSeparator()
        menu.addAction("Quit Zengo", QApplication.quit)
        menu.aboutToShow.connect(menu.raise_)
        menu.exec(where)

    def _toggle_sound(self) -> None:
        ctx = self._brain.ctx
        ctx.sound_on = not ctx.sound_on
        self.change_settings(replace(self._settings, sound=ctx.sound_on))
        if ctx.sound_on:
            ctx.play("chirp_a")  # a little hello, so you know it's on

    @property
    def settings(self) -> Settings:
        return self._settings

    def change_settings(self, settings: Settings, *, keep: bool = True) -> None:
        """Take up new settings at once, and keep them unless ``keep`` is false
        (a volume slider still being dragged)."""
        if settings != self._settings:
            old_scale = self._config.scale
            self._settings = settings
            self._config = build_config(settings, self._flags)
            self._brain.ctx.config = self._config
            self._brain.ctx.sound_on = settings.sound
            self._sound.set_volume(settings.volume)
            if self._config.scale != old_scale:
                self._resize()
        if keep and self._settings_file is not None:
            self._settings_file.save(settings.to_json())
        if self._settings_window is not None:
            self._settings_window.show_settings(settings, self._settings_window_autostart())

    def _settings_window_autostart(self) -> bool | None:
        return self._autostart.enabled()

    def set_autostart(self, on: bool) -> None:
        self._autostart.set(on)
        if self._settings_window is not None:
            self._settings_window.show_settings(self._settings, self._autostart.enabled())

    def open_settings(self) -> None:
        """Show the settings window: one, reused, brought to the front."""
        if self._settings_window is None:
            window = SettingsWindow(self._settings, scale_locked=self._flags.scale is not None)
            window.changed.connect(self.change_settings)
            window.previewed.connect(lambda s: self.change_settings(s, keep=False))
            window.reset_confirmed.connect(self.reset)
            window.autostart_changed.connect(self.set_autostart)
            self._settings_window = window
        self._settings_window.show_settings(self._settings, self._settings_window_autostart())
        self._settings_window.show()
        self._settings_window.raise_()
        self._settings_window.activateWindow()

    def reset(self) -> None:
        """Start over: he forgets everything he remembers (your settings stay)."""
        self._brain.forget()
        self.save()
        self._render()

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
    flags: Flags
    """What the command line says, to be laid over your settings."""
    sprites: Path | None
    """Aseprite JSON export whose frames replace the built-in ones by name."""
    branch_now: bool = False
    """Grow a branch straight away instead of waiting for one."""


def parse_args(argv: list[str]) -> Options:
    parser = argparse.ArgumentParser(prog="zengo", description="Zengo the desktop cockatiel.")
    parser.add_argument(
        "--scale", type=int, help="screen pixels per art pixel (overrides your settings)"
    )
    parser.add_argument("--fps", type=int, help=f"frames per second (default {Config.fps})")
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
    if (args.scale is not None and args.scale < 1) or (args.fps is not None and args.fps < 1):
        parser.error("--scale and --fps must be positive")
    flags = Flags(scale=args.scale, fps=args.fps, quick=args.quick)
    return Options(flags, args.sprites, args.branch_now)


def quiet_bundled_libraries() -> None:
    """In the standalone Linux build, keep the desktop's own add-ons out.

    The binary carries older GTK and GLib than most desktops. At start-up Qt's GTK
    theme would load the desktop's GTK modules (Linux Mint's xapp module) and GLib
    its gvfs modules, which don't fit the older libraries and print warnings. Zengo
    needs neither: his menu is styled by hand and he opens no files over the
    network. ``setdefault`` leaves any value the user set alone.
    """
    # Qt's sound support announces its FFmpeg version on every start; he needn't.
    os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.ffmpeg*=false")
    if getattr(sys, "frozen", False) and sys.platform.startswith("linux"):
        os.environ.setdefault("QT_QPA_PLATFORMTHEME", "generic")
        os.environ.setdefault("GIO_MODULE_DIR", "/nonexistent")


def main(argv: list[str] | None = None) -> int:
    options = parse_args(sys.argv[1:] if argv is None else argv)
    quiet_bundled_libraries()
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

    memory = StateFile.default()
    settings_file = StateFile(memory.path.with_name("settings.json"))
    settings_data = settings_file.load()
    settings = Settings.from_json(settings_data)
    if (carried := migrated(settings_data, memory.load())) is not None:
        settings = carried
        settings_file.save(settings.to_json())  # sound on/off moved over from the state file
    config = build_config(settings, options.flags)
    autostart = Autostart.for_this_system()
    autostart.refresh()
    pet = Pet(
        config,
        frames,
        branch_now=options.branch_now,
        memory=memory,
        settings=settings,
        settings_file=settings_file,
        flags=options.flags,
        autostart=autostart,
    )
    pet.start()
    return app.exec()
