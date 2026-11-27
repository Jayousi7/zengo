"""Recording a sound for him: turning raw audio into a trimmed 16-bit mono WAV.

None of these open a microphone: the samples are made up here."""

import array
import math
import wave

import pytest

from zengo.ui import recorder
from zengo.ui.recorder import RecorderBox, to_mono16, trim_silence, write_wav

RATE = 8000


def tone(seconds, level=0.5):
    return [
        round(level * 32767 * math.sin(2 * math.pi * 2500 * i / RATE))
        for i in range(round(seconds * RATE))
    ]


def test_stereo_formats_become_16_bit_mono():
    left_right = array.array("h", [1000, 3000, -2000, -4000]).tobytes()
    assert to_mono16(left_right, 2, "Int16") == [2000, -3000]
    int32 = array.array("i", [2**30, 2**30]).tobytes()
    assert to_mono16(int32, 2, "Int32") == [16384]
    floats = array.array("f", [0.5, -0.5, 1.0, 1.0]).tobytes()
    assert to_mono16(floats, 2, "Float") == [0, 32767]
    assert to_mono16(bytes([128, 255]), 1, "UInt8") == [0, 32511]
    with pytest.raises(ValueError):
        to_mono16(b"\0\0", 1, "Unknown")


def test_silence_is_trimmed_from_both_ends():
    quiet = [3] * RATE  # a second of near silence
    sound = tone(0.25)
    trimmed = trim_silence(quiet + sound + quiet, RATE)
    pad = round(recorder.PAD * RATE)
    assert len(sound) <= len(trimmed) <= len(sound) + 2 * pad + 2
    assert trim_silence(quiet, RATE) == []


def test_the_wav_is_16_bit_mono(tmp_path):
    path = tmp_path / "recordings" / "trill.wav"
    write_wav(path, tone(0.1), RATE)
    with wave.open(str(path)) as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, RATE)
        assert wav.getnframes() == round(0.1 * RATE)


def test_a_take_is_played_kept_or_thrown_away(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "microphone", lambda: (None, "no microphone found"))
    kept, played = [], []
    box = RecorderBox(tmp_path, lambda c, p: kept.append((c, p)), played.append, cue="trill")
    assert not box.record.isEnabled() and "no microphone found" in box.status.text()
    assert not box.save.isEnabled()

    box.set_take([0] * 4000 + tone(0.3) + [0] * 4000, RATE)
    assert box.save.isEnabled() and "Recorded 0.4 s" in box.status.text()  # with padding
    box.play.click()
    assert played and played[0].exists()
    box.save.click()
    assert kept == [("trill", tmp_path / "recordings" / "trill.wav")]
    assert kept[0][1].exists() and not box.save.isEnabled()

    box.set_take([0] * 8000, RATE)
    assert "Nothing heard" in box.status.text() and not box.save.isEnabled()
    box.set_take(tone(0.2), RATE)
    box.discard.click()
    assert len(kept) == 1
    box.close()


def test_a_kept_recording_replaces_his_sound(tmp_path, monkeypatch):
    import random

    from zengo.app import Pet
    from zengo.behavior.voice import VoiceFiles
    from zengo.config import Config
    from zengo.sprites.frames import build_frames

    monkeypatch.setattr(recorder, "microphone", lambda: (None, "no microphone found"))
    pet = Pet(Config(), build_frames(), random.Random(1), voice_files=VoiceFiles(tmp_path))
    try:
        pet.open_recorder("ask")
        box = pet._recorder
        box.set_take(tone(0.3), RATE)
        box.save.click()
        path = tmp_path / "recordings" / "ask.wav"
        assert pet.voice.sounds == {"ask": path}
        assert VoiceFiles(tmp_path).load().sounds == {"ask": path}
        box.close()
    finally:
        pet._window.close()
