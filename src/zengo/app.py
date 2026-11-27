"""Composition root: builds the pieces, wires them together, runs the frame loop."""

from __future__ import annotations

import argparse
import os
import random
import signal
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRect, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMenu, QWidgetAction

from zengo.animation import Animator
from zengo.behavior.body import Body, Facing
from zengo.behavior.context import Context
from zengo.behavior.machine import Brain
from zengo.behavior.memory import restore, snapshot
from zengo.behavior.moult import MAX_FEATHERS
from zengo.behavior.seasons import SEASONS, hemisphere_of
from zengo.behavior.states import Away
from zengo.behavior.vocabulary import Lesson
from zengo.behavior.voice import Voice, VoiceFiles
from zengo.config import Config
from zengo.settings import Flags, Settings, build_config, migrated
from zengo.sprites.cage import CAGE_WIDTH, FLOOR
from zengo.sprites.clips import CLIPS
from zengo.sprites.compose import Frame
from zengo.sprites.food import MAX_STACKS
from zengo.sprites.frames import ANCHOR_COLUMN, CANVAS_WIDTH, GROUND_ROW, build_frames
from zengo.ui.autostart import Autostart
from zengo.ui.bath_window import BathWindow
from zengo.ui.branch_window import BranchWindow
from zengo.ui.bubble_window import BubbleWindow
from zengo.ui.cage_window import CageWindow, MountWindow
from zengo.ui.catch_overlay import CatchOverlay
from zengo.ui.effects_window import EffectsWindow
from zengo.ui.feather_window import FeatherWindow
from zengo.ui.focus_tab import describe
from zengo.ui.food_window import FoodWindow
from zengo.ui.qt_world import QtWorld, time_zone
from zengo.ui.recorder import RecorderBox, microphone
from zengo.ui.settings_window import SettingsWindow
from zengo.ui.sheet_loader import SheetError, load_sheet
from zengo.ui.sound import SoundPlayer
from zengo.ui.sprites import SpriteSheet
from zengo.ui.start_button import StartButton
from zengo.ui.state_file import StateFile
from zengo.ui.status_panel import StatusPanel
from zengo.ui.teach_box import TeachBox
from zengo.ui.toy_window import BellWindow, MirrorWindow
from zengo.ui.tray import Tray
from zengo.ui.voice_tabs import SoundsTab, WordsTab, voice_with
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
        bath_now: bool = False,
        memory: StateFile | None = None,
        settings: Settings | None = None,
        settings_file: StateFile | None = None,
        flags: Flags | None = None,
        autostart: Autostart | None = None,
        voice_files: VoiceFiles | None = None,
        custom: frozenset[str] = frozenset(),
    ) -> None:
        self._config = config
        self._frames = frames
        self._custom = custom
        """Frames replaced from an Aseprite sheet."""
        self._settings = settings or Settings(scale=config.scale)
        self._settings_file = settings_file
        self._flags = flags or Flags()
        self._autostart = autostart or Autostart(None)
        self._voice_files = voice_files
        self._settings_window: SettingsWindow | None = None
        self._teach_box: TeachBox | None = None
        self._words_tab: WordsTab | None = None
        self._sounds_tab: SoundsTab | None = None
        self._recorder: RecorderBox | None = None
        self._world = QtWorld()

        area = self._world.area_at(*self._world.cursor())
        body = Body(x=(area.left + area.right) / 2, y=area.bottom)
        animator = Animator(CLIPS, initial="idle")
        self._brain = Brain(Context(body, self._world, animator, config, rng or random.Random()))
        if voice_files is not None:
            self._brain.ctx.voice = voice_files.load()
        if branch_now:
            self._brain.ctx.scenery.grow(self._brain.ctx)
        if bath_now:
            self._brain.ctx.bath.fill(self._brain.ctx)
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
        self._brain.ctx.seasons.zone_hemisphere = hemisphere_of(time_zone())
        self._brain.ctx.seasons.forced = self._flags.season
        self._apply_life()
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
        self._sound = SoundPlayer(self._settings.volume, self._brain.ctx.voice.sounds)
        if (app := QApplication.instance()) is not None:
            app.aboutToQuit.connect(self._sound.close)  # tidy away the sound files
        self._overlay: CatchOverlay | None = None
        self._door_was_open = False
        self._restacked = -RESTACK_EVERY
        self._showing: tuple[bool, ...] = ()
        self._speech_at: QPointF | None = None
        self._speech_of: object = None

        self._tray: Tray | None = None
        if Tray.available():
            self._tray = Tray(
                frames,
                {
                    "summon": self._brain.summon,
                    "show": self._brain.show,
                    "hide": self._brain.hide,
                    "feed": self._brain.feed,
                    "focus": lambda: self.open_settings("Focus"),
                    "pause": self.pause_focus,
                    "stop": self.stop_focus,
                    "settings": self.open_settings,
                    "quit": QApplication.quit,
                },
                MENU_STYLE,
            )

        self._timer = QTimer(timerType=Qt.TimerType.PreciseTimer, interval=1000 // config.fps)
        self._timer.timeout.connect(self._tick)
        self._last_tick = time.monotonic()

    def _build_windows(self) -> None:
        """Make the windows drawn at his size: everything but his own window,
        which simply takes whatever sprite it's given."""
        config = self._config
        self._sheet = SpriteSheet(self._frames, config.scale, self._custom)
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
        self._effects = EffectsWindow(config.scale, in_front_of=self._window)
        self._bath = BathWindow(config, in_front_of=self._window)
        self._bell = BellWindow(config, in_front_of=self._window)
        self._mirror = MirrorWindow(config, in_front_of=self._window)
        self._start_button = StartButton(config.scale)
        self._start_button.clicked.connect(self.start_focus)
        # One more than can lie about: the oldest fades as a new one falls.
        self._feathers = [FeatherWindow(config.scale) for _ in range(MAX_FEATHERS + 1)]
        for index, feather in enumerate(self._feathers):
            feather.clicked.connect(lambda i=index: self._brain.pick_feather(i))

    def _scaled_windows(self) -> list:
        """The windows drawn at his size, made again when it changes."""
        return [
            self._branch,
            self._bubble,
            self._cage,
            self._mount,
            self._food,
            self._dish,
            self._effects,
            self._bath,
            self._bell,
            self._mirror,
            *self._feathers,
            self._start_button,
        ]

    def _resize(self) -> None:
        """He's changed size: redraw everything at the new scale and put him and
        his cage where they belong at it."""
        for window in self._scaled_windows():
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
        if not self._brain.away:
            self._window.show()
        if self._tray is not None:
            self._tray.show()
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
        self._update_tray()
        body = ctx.body
        sprite = self._sheet.get(ctx.animator.frame, body.facing, self._brain.look)
        # Mirroring flips the anchor column too; +0.5 centres on the column.
        anchor = ANCHOR_COLUMN if body.facing is Facing.RIGHT else CANVAS_WIDTH - 1 - ANCHOR_COLUMN
        left = body.x - self._config.px(anchor + 0.5)
        top = body.y - self._config.px(GROUND_ROW + 1)
        desktop = QGuiApplication.primaryScreen().virtualGeometry()
        if isinstance(self._brain.state, Away):
            self._window.hide()  # out of sight; the rest follows as it would
        else:
            at = QPoint(round(left), round(top))
            self._window.show_sprite(sprite, at, desktop, show=self._timer.isActive())
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
        self._bath.show_dish(ctx.bath.dish, time.monotonic())
        self._bell.show_bell(ctx.toys.bell)
        self._mirror.show_mirror(ctx.toys.mirror)
        feathers = ctx.moult.feathers
        for index, window in enumerate(self._feathers):
            window.show_feather(feathers[index] if index < len(feathers) else None)
        self._show_cage()
        self._effects.show_particles(ctx.effects.particles)
        self._show_speech()
        self._show_start_button()
        if self._settings_window is not None and self._settings_window.isVisible():
            self._show_timer()
        self._play_sounds()
        showing = tuple(w.isVisible() for w in self._layers())
        if _menu_open():
            pass  # leave the order alone while his menu is up: it stays on top
        elif showing != self._showing or time.monotonic() - self._restacked >= RESTACK_EVERY:
            self._showing = showing  # one has just come or gone: order them at once
            self.restack()

    def _update_tray(self) -> None:
        if self._tray is None:
            return
        brain = self._brain
        focus = brain.ctx.focus
        now = brain.ctx.clock()
        words = "" if focus.phase == "off" else describe(focus.phase, focus.left(now), focus.paused)
        self._tray.update(
            needs_you=brain.ctx.hunger.hungry or brain.caged,
            away=isinstance(brain.state, Away),
            can_hide=brain.can_hide(),
            can_feed=brain.food_stacks < MAX_STACKS,
            focus=(focus.phase, focus.fraction_left(now), focus.paused, words.rstrip(".")),
        )

    def _layers(self) -> list:
        return [
            self._mount,
            *self._feathers,
            self._food,
            self._window,
            self._bath,
            self._branch,
            self._bell,
            self._mirror,
            self._dish,
            self._cage,
            self._effects,
            self._bubble,
            self._start_button,
        ]

    def restack(self) -> None:
        """Put the windows in their proper order, back to front.

        Behind Zengo: the chain or shelf, feathers he's dropped and the seed
        pile. In front of him: his bath (so the rim hides his feet as he stands
        in it), the branch (so his tail hangs behind it), the dish and the cage
        (so he's behind the bars; once the door's open he comes out in front),
        his toys, the droplets and snow, and the speech cloud.
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
        menu.addAction("Settings…", self.open_settings)  # everything else lives there
        menu.addSeparator()
        menu.addAction("Quit Zengo", QApplication.quit)
        menu.aboutToShow.connect(menu.raise_)
        menu.exec(where)

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
            if settings.sound and not self._brain.ctx.sound_on:
                self._brain.ctx.play("chirp_a")  # a little hello, so you know it's on
            self._brain.ctx.sound_on = settings.sound
            self._sound.set_volume(settings.volume)
            self._apply_life()
            if self._config.scale != old_scale:
                self._resize()
        if keep and self._settings_file is not None:
            self._settings_file.save(settings.to_json())
        if keep and self._settings_window is not None:
            # (Not while the volume is being dragged: the window's own copy has to
            # stay as it was, so letting go is seen as a change and kept.)
            self._settings_window.show_settings(settings, self._settings_window_autostart())

    def _apply_life(self) -> None:
        """Seasons and toys, as your settings have them."""
        seasons = self._brain.ctx.seasons
        seasons.enabled, seasons.setting = self._settings.seasons, self._settings.hemisphere
        self._brain.ctx.toys.put_out(frozenset(self._settings.toys))

    def _settings_window_autostart(self) -> bool | None:
        return self._autostart.enabled()

    def set_autostart(self, on: bool) -> None:
        self._autostart.set(on)
        if self._settings_window is not None:
            self._settings_window.show_settings(self._settings, self._autostart.enabled())

    def open_settings(self, tab: str | None = None) -> None:
        """Show the settings window (at ``tab``, if given): one, reused, brought
        to the front."""
        if self._settings_window is None:
            window = SettingsWindow(
                self._settings,
                scale_locked=self._flags.scale is not None,
                hemisphere_found=self._brain.ctx.seasons.zone_hemisphere,
            )
            window.changed.connect(self.change_settings)
            window.previewed.connect(lambda s: self.change_settings(s, keep=False))
            window.reset_confirmed.connect(self.reset)
            window.autostart_changed.connect(self.set_autostart)
            window.focus_start.connect(self.start_focus)
            window.focus_pause.connect(self.pause_focus)
            window.focus_stop.connect(self.stop_focus)
            if self._voice_files is not None:
                self._add_voice_tabs(window)
            self._settings_window = window
        self._settings_window.show_settings(self._settings, self._settings_window_autostart())
        if tab is not None:
            self._settings_window.show_tab(tab)
        self._show_timer()
        self._settings_window.show()
        self._settings_window.raise_()
        self._settings_window.activateWindow()

    def _add_voice_tabs(self, window: SettingsWindow) -> None:
        voice = self._brain.ctx.voice
        self._words_tab = WordsTab()
        self._words_tab.show_phrases(voice.phrases)
        self._words_tab.edited.connect(lambda p: self.change_voice(voice_with(self.voice, p)))
        self._words_tab.forget.connect(self.forget_word)
        self._words_tab.teach.connect(self.open_teach_box)
        self._show_taught()
        self._sounds_tab = SoundsTab()
        self._sounds_tab.show_sounds(voice.sounds)
        self._sounds_tab.edited.connect(
            lambda s: self.change_voice(voice_with(self.voice, sounds=s))
        )
        self._sounds_tab.play.connect(self._sound.play)
        self._sounds_tab.record.connect(self.open_recorder)
        device, why_not = microphone()
        self._sounds_tab.set_recording(device is not None, why_not)
        window.add_tab(self._words_tab, "Words")
        window.add_tab(self._sounds_tab, "Sounds")

    def open_recorder(self, cue: str) -> None:
        """The recording box, for a sound to replace ``cue``."""
        if self._voice_files is None:
            return
        if self._recorder is not None:
            self._recorder.close()
        self._recorder = RecorderBox(
            self._voice_files.folder, self._keep_recording, self._sound.preview, cue
        )
        self._recorder.show()
        self._recorder.raise_()
        self._recorder.activateWindow()

    def _keep_recording(self, cue: str, path: Path) -> None:
        self.change_voice(voice_with(self.voice, sounds={**self.voice.sounds, cue: path}))
        if self._sounds_tab is not None:
            self._sounds_tab.show_sounds(self.voice.sounds)

    def open_teach_box(self) -> None:
        if self._teach_box is None:
            self._teach_box = TeachBox(self.teach, self._brain.can_learn)
        self._teach_box.show()
        self._teach_box.raise_()
        self._teach_box.activateWindow()

    def teach(self, text: str, moment: str) -> Lesson | None:
        lesson = self._brain.lesson(text, moment)
        if lesson is not None:
            self.save()
            self._show_taught()
        return lesson

    def forget_word(self, text: str) -> None:
        self._brain.ctx.vocabulary.forget(text)
        self.save()
        self._show_taught()

    def _show_taught(self) -> None:
        if self._words_tab is None:
            return
        ctx = self._brain.ctx
        needed = ctx.words_needed()
        self._words_tab.show_taught(
            [(w.text, w.moment, w.lessons, needed) for w in ctx.vocabulary.words]
        )

    @property
    def voice(self) -> Voice:
        return self._brain.ctx.voice

    def change_voice(self, voice: Voice) -> None:
        """New phrases or sounds: used at once, and saved to his voice files."""
        old = self._brain.ctx.voice
        self._brain.ctx.voice = voice
        if voice.sounds != old.sounds:
            self._sound.use(voice.sounds)
        if self._voice_files is not None:
            self._voice_files.save(voice)

    def reset(self) -> None:
        """Start over: he forgets everything he remembers (your settings stay)."""
        self._brain.forget()
        self.save()
        self._show_taught()
        self._render()

    # --- Focus ----------------------------------------------------------------------

    def start_focus(self) -> None:
        ctx = self._brain.ctx
        ctx.focus.plan = self._settings.focus_plan()
        ctx.focus.start(ctx.clock())
        self._focus_changed()

    def pause_focus(self) -> None:
        ctx = self._brain.ctx
        if ctx.focus.paused:
            ctx.focus.resume(ctx.clock())
        else:
            ctx.focus.pause(ctx.clock())
        self._focus_changed()

    def stop_focus(self) -> None:
        self._brain.ctx.focus.stop()
        self._focus_changed()

    def _focus_changed(self) -> None:
        self.save()
        self._render()

    def _show_timer(self) -> None:
        """Keep the Focus tab's time left up to date while the window's open."""
        window = self._settings_window
        if window is None or (not window.isVisible() and not self._timer.isActive()):
            return
        focus = self._brain.ctx.focus
        window.focus.show_timer(focus.phase, focus.left(self._brain.ctx.clock()), focus.paused)

    def _show_start_button(self) -> None:
        """By his head while he waits for you to start the next session."""
        ctx = self._brain.ctx
        if ctx.focus.phase != "waiting" or self._brain.away or not self._window.isVisible():
            self._start_button.show_beside(None, 1, QRect())
            return
        body, px = ctx.body, self._config.px
        side = int(body.facing)
        head = QPoint(round(body.x + side * px(14)), round(body.y - px(16)))
        screen = QGuiApplication.screenAt(head) or QGuiApplication.primaryScreen()
        self._start_button.show_beside(head, side, screen.availableGeometry())

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
    bath_now: bool = False
    """Put his bath out straight away."""


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
    parser.add_argument(
        "--bath-now",
        action="store_true",
        help="put Zengo's bath out straight away instead of waiting for it",
    )
    parser.add_argument(
        "--season",
        choices=SEASONS,
        help="show this season whatever the date, to try it out",
    )
    args = parser.parse_args(argv)
    if (args.scale is not None and args.scale < 1) or (args.fps is not None and args.fps < 1):
        parser.error("--scale and --fps must be positive")
    flags = Flags(scale=args.scale, fps=args.fps, quick=args.quick, season=args.season)
    return Options(flags, args.sprites, args.branch_now, args.bath_now)


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
    # Closing his settings (or the teach or record box) must not end him: he quits
    # only from his menu, the tray, or the session ending.
    app.setQuitOnLastWindowClosed(False)

    frames = build_frames()
    custom: frozenset[str] = frozenset()
    if options.sprites is not None:
        try:
            loaded = load_sheet(options.sprites, frames.keys())
            frames.update(loaded)
            custom = frozenset(loaded)
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
        bath_now=options.bath_now,
        memory=memory,
        settings=settings,
        settings_file=settings_file,
        flags=options.flags,
        autostart=autostart,
        voice_files=VoiceFiles(memory.path.parent),
        custom=custom,
    )
    pet.start()
    return app.exec()
