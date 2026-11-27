"""His phrases and sounds, from phrases.toml and sounds.toml."""

import tomllib
from pathlib import Path

from zengo.behavior.machine import Brain
from zengo.behavior.states import Idle
from zengo.behavior.voice import (
    DEFAULT_PHRASES,
    MOMENTS,
    Voice,
    VoiceFiles,
    phrases_from,
    phrases_toml,
    sounds_from,
    sounds_toml,
)
from zengo.sounds import names


def test_missing_files_are_written_out_with_the_built_ins(tmp_path):
    files = VoiceFiles(tmp_path)
    voice = files.load()
    assert voice == Voice()
    assert files.phrases_path.exists() and files.sounds_path.exists()
    assert phrases_from(tomllib.loads(files.phrases_path.read_text())) == DEFAULT_PHRASES
    assert sounds_from(tomllib.loads(files.sounds_path.read_text()), tmp_path) == {}


def test_your_phrases_are_used(tmp_path, ctx):
    (tmp_path / "phrases.toml").write_text('hungry = ["snacc?"]\nfreed = []\n')
    voice = VoiceFiles(tmp_path).load()
    assert voice.lines("hungry") == ("snacc?",)
    assert voice.lines("freed") == DEFAULT_PHRASES["freed"]  # empty: the built-in
    ctx.voice = voice
    assert ctx.phrase("hungry") == "snacc?"


def test_a_broken_file_is_reported_once_and_left_alone(tmp_path, capsys):
    broken = 'hungry = ["unclosed'
    (tmp_path / "phrases.toml").write_text(broken)
    files = VoiceFiles(tmp_path)
    assert files.load().phrases == DEFAULT_PHRASES
    files.load()
    assert capsys.readouterr().err.count("phrases.toml") == 1
    assert (tmp_path / "phrases.toml").read_text() == broken  # your edits survive


def test_bad_entries_fall_back_on_their_own():
    phrases = phrases_from({"hungry": "not a list", "fed": [1, "  ", "nom"], "nope": ["x"]})
    assert phrases["hungry"] == DEFAULT_PHRASES["hungry"]
    assert phrases["fed"] == ("nom",)
    assert "nope" not in phrases
    assert phrases_from({"fed": ["x" * 100]})["fed"] == ("x" * 40,)  # fits his cloud


def test_sounds_point_at_files_and_unknown_ones_are_ignored(tmp_path):
    sounds = sounds_from(
        {"trill": "mine.wav", "ask": "/abs/ask.wav", "chirp_a": "built-in", "squeak": "x.wav"},
        tmp_path,
    )
    assert sounds == {"trill": tmp_path / "mine.wav", "ask": Path("/abs/ask.wav")}


def test_the_files_round_trip_awkward_text(tmp_path):
    awkward = ('say "hi"', "back\\slash", "♪ ♫ 🐦", "tab\there", "new\nline")
    phrases = {**DEFAULT_PHRASES, "random": awkward}
    assert phrases_from(tomllib.loads(phrases_toml(phrases)))["random"] == awkward
    sounds = {"trill": tmp_path / "my trill.wav", "ask": Path('/x/a"b.wav')}
    assert sounds_from(tomllib.loads(sounds_toml(sounds, tmp_path)), tmp_path) == sounds


def test_saving_writes_both_files(tmp_path):
    files = VoiceFiles(tmp_path)
    voice = Voice({**DEFAULT_PHRASES, "fed": ("nom nom",)}, {"trill": tmp_path / "t.wav"})
    files.save(voice)
    assert VoiceFiles(tmp_path).load() == voice


def test_every_moment_has_built_in_phrases_and_every_sound_a_recipe():
    from zengo.behavior.voice import CUES

    assert set(MOMENTS) == set(DEFAULT_PHRASES)
    assert set(CUES) == set(names())


def test_he_says_your_phrases_at_their_moments(ctx):
    ctx.voice = Voice({**DEFAULT_PHRASES, "random": ("hello world",)})
    ctx.config = __import__("dataclasses").replace(ctx.config, chirp_every=0.01)
    brain = Brain(ctx, Idle())
    for _ in range(30):
        brain.tick(1 / 30)
        if ctx.speech is not None:
            break
    assert ctx.speech is not None and ctx.speech.text == "hello world"
