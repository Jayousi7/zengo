"""The tray: Zengo's head in the system tray, and what it can ask of him."""

import pytest

from zengo.behavior.machine import Brain
from zengo.behavior.states import Away, Caged, Dragged, Fly, Idle

DT = 1 / 30


def run_until(brain, check, limit=20.0):
    for _ in range(round(limit / DT)):
        brain.tick(DT)
        if check():
            return
    raise AssertionError(f"never happened; stuck in {brain.state!r}")


def test_hidden_he_flies_off_the_nearer_side_and_comes_back_from_it(ctx):
    brain = Brain(ctx, Idle())
    area = ctx.world.area
    ctx.body.x = area.left + 300
    assert brain.hide()
    assert brain.away and not brain.can_hide()
    run_until(brain, lambda: isinstance(brain.state, Away))
    assert ctx.body.x < area.left  # off the left edge, out of sight
    brain.tick(5.0)
    assert isinstance(brain.state, Away)
    brain.show()
    assert not brain.away
    run_until(brain, lambda: isinstance(brain.state, Idle))
    assert area.left < ctx.body.x < area.left + ctx.config.px(300)
    assert ctx.body.y == area.bottom


def test_away_he_still_gets_hungry_but_doesnt_ask(ctx):
    brain = Brain(ctx, Idle())
    brain.hide()
    run_until(brain, lambda: isinstance(brain.state, Away))
    ctx.hunger.fullness, ctx.hunger.hungry = 0.0, True
    for _ in range(round(10 / DT)):
        brain.tick(DT)
    assert isinstance(brain.state, Away)


def test_clicking_the_icon_brings_him_to_the_middle(ctx):
    brain = Brain(ctx, Idle())
    area = ctx.world.area
    ctx.body.x = area.left + 200
    brain.summon()
    assert ctx.speech.text.startswith("here I am")
    assert isinstance(brain.state, Fly)
    run_until(brain, lambda: isinstance(brain.state, Idle))
    assert ctx.body.x == pytest.approx((area.left + area.right) / 2)


def test_clicking_the_icon_while_hidden_brings_him_back_to_the_middle(ctx):
    brain = Brain(ctx, Idle())
    brain.hide()
    run_until(brain, lambda: isinstance(brain.state, Away))
    brain.summon()
    run_until(brain, lambda: isinstance(brain.state, Idle))
    area = ctx.world.area
    assert ctx.body.x == pytest.approx((area.left + area.right) / 2)


def test_caged_or_carried_he_can_only_call(ctx):
    brain = Brain(ctx, Idle())
    assert brain.catch_in(ctx.body.x - 40, ctx.body.y - 80, ctx.body.x + 40, ctx.body.y + 10)
    assert not brain.can_hide() and not brain.hide()
    brain.summon()
    assert isinstance(brain.state, Caged) and ctx.speech.text.startswith("here I am")

    brain = Brain(ctx, Dragged((ctx.body.x, ctx.body.y)))
    assert not brain.hide()


def test_the_icon_is_his_head_with_a_dot_when_he_needs_you():
    from zengo.sprites.frames import build_frames
    from zengo.ui.tray import head_icon

    frame = build_frames()["perch"]
    plain, badged = head_icon(frame, 64), head_icon(frame, 64, badge=True)
    assert (plain.width(), plain.height()) == (64, 64)
    assert plain.toImage().pixelColor(5, 5).alpha() == 0  # the corner's empty...
    assert badged.toImage().pixelColor(8, 8).alpha() == 255  # ...but for the dot


def test_the_tray_menu_follows_him():
    from zengo.sprites.frames import build_frames
    from zengo.ui.tray import Tray

    called = []
    actions = {
        k: (lambda k=k: called.append(k))
        for k in ("summon", "show", "hide", "feed", "settings", "quit")
    }
    tray = Tray(build_frames(), actions, "")
    tray.update(needs_you=True, away=False, can_hide=True, can_feed=True)
    assert tray._show_hide.text() == "Hide Zengo" and tray._icon.toolTip() == "Zengo needs you"
    tray._show_hide.trigger()
    tray.update(needs_you=False, away=True, can_hide=False, can_feed=False)
    assert tray._show_hide.text() == "Show Zengo" and tray._show_hide.isEnabled()
    assert not tray._feed.isEnabled()
    tray._show_hide.trigger()
    from PySide6.QtWidgets import QSystemTrayIcon

    tray._activated(QSystemTrayIcon.ActivationReason.Trigger)
    assert called == ["hide", "show", "summon"]


def test_his_window_goes_while_hes_away_and_comes_back_with_him():
    import random

    from zengo.app import Pet
    from zengo.config import Config
    from zengo.sprites.frames import build_frames

    pet = Pet(Config(), build_frames(), random.Random(1))
    pet.start()
    brain = pet._brain

    def until(check):
        for _ in range(round(20 / DT)):
            brain.tick(DT)
            pet._render()
            if check():
                return
        raise AssertionError(brain.state)

    assert pet._window.isVisible()
    brain.hide()
    until(lambda: isinstance(brain.state, Away))
    assert not pet._window.isVisible()
    brain.show()
    until(lambda: isinstance(brain.state, Idle))
    assert pet._window.isVisible()
    pet._timer.stop()
    pet._window.close()
