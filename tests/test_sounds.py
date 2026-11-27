"""His chirps, whistles, squawks and trills."""

import io
import wave
from dataclasses import replace

from zengo import sounds
from zengo.behavior.machine import Brain
from zengo.behavior.memory import restore, snapshot
from zengo.behavior.states import Fly, Idle
from zengo.sounds import CHIRPS

DT = 1 / 30


def test_every_sound_is_short_soft_and_a_real_wav():
    for name in sounds.names():
        samples = sounds.sound(name)
        assert 0.05 < len(samples) / sounds.RATE < 1.0  # short
        assert max(abs(s) for s in samples) <= 1.0
        with wave.open(io.BytesIO(sounds.wav(samples))) as w:
            assert (w.getnchannels(), w.getframerate()) == (1, sounds.RATE)


def test_each_whistle_phrase_has_its_own_tune(ctx):
    tunes = {sounds.whistle_for(i) for i in range(len(ctx.config.whistles))}
    assert len(tunes) == len(ctx.config.whistles)
    assert all(t in sounds.names() for t in tunes)


def test_a_whistle_plays_its_tune(ctx):
    brain = Brain(ctx, Idle())
    brain.double_click()
    phrase = ctx.config.whistles.index(ctx.speech.text)
    assert ctx.sounds == [sounds.whistle_for(phrase)]


def test_caged_he_squawks_and_freed_by_his_own_wits_he_trills(ctx):
    from zengo.config import quick

    ctx.config = quick(ctx.config)
    brain = Brain(ctx, Idle())
    brain.catch_in(ctx.body.x - 40, ctx.body.y - 80, ctx.body.x + 40, ctx.body.y + 5)
    assert "squawk" in ctx.sounds
    for _ in range(round(10 / DT)):
        brain.tick(DT)
    assert "trill" in ctx.sounds


def test_pottering_about_he_chirps_now_and_then_but_not_mid_flight(ctx):
    ctx.config = replace(ctx.config, chirp_every=2.0)
    brain = Brain(ctx, Idle())
    for _ in range(round(10 / DT)):
        brain.tick(DT)
        if isinstance(brain.state, Fly):
            brain.transition(Idle())
    assert any(s in CHIRPS for s in ctx.sounds)
    ctx.sounds.clear()
    brain.transition(Fly.tour(ctx))
    for _ in range(round(5 / DT)):
        brain.tick(DT)
    assert not any(s in CHIRPS for s in ctx.sounds)


def test_sound_on_or_off_is_remembered(ctx):
    ctx.sound_on = False
    data = snapshot(ctx)
    ctx.sound_on = True
    restore(ctx, data)
    assert ctx.sound_on is False


def test_the_player_makes_its_files_and_tidies_them_away():
    from zengo.ui.sound import SoundPlayer

    player = SoundPlayer()
    folder = player._folder
    assert folder is not None and len(list(folder.glob("*.wav"))) == len(sounds.names())
    player.play("no such sound")  # ignored
    player.close()
    assert not folder.exists()
