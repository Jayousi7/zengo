"""The Words and Sounds tabs of his settings window."""

import random

from zengo.behavior.voice import DEFAULT_PHRASES, VoiceFiles


def test_editing_a_moments_phrases_reports_them_after_a_pause():
    from zengo.ui.voice_tabs import WordsTab

    tab = WordsTab()
    tab.show_phrases(DEFAULT_PHRASES)
    edits = []
    tab.edited.connect(edits.append)
    tab.moments.setCurrentRow(list(DEFAULT_PHRASES).index("hungry"))
    assert tab.lines.toPlainText().splitlines() == list(DEFAULT_PHRASES["hungry"])
    tab.lines.setPlainText("snacc?\n\n  more snacc  \n")
    assert edits == []  # waits for the pause in typing
    tab.flush()
    assert edits[-1]["hungry"] == ("snacc?", "more snacc")
    tab.lines.setPlainText("")
    tab.flush()
    assert edits[-1]["hungry"] == DEFAULT_PHRASES["hungry"]  # empty: back to his own


def test_switching_moments_keeps_the_edit_and_built_in_resets_one():
    from zengo.ui.voice_tabs import WordsTab

    tab = WordsTab()
    tab.show_phrases(DEFAULT_PHRASES)
    edits = []
    tab.edited.connect(edits.append)
    tab.moments.setCurrentRow(0)
    tab.lines.setPlainText("hello")
    tab.moments.setCurrentRow(1)  # moving on takes it up
    assert edits[-1]["random"] == ("hello",)
    tab.moments.setCurrentRow(0)
    tab.reset.click()
    assert edits[-1]["random"] == DEFAULT_PHRASES["random"]


def test_sounds_can_be_replaced_played_and_put_back(tmp_path):
    from zengo.ui.voice_tabs import SoundsTab

    mine = tmp_path / "mine.wav"
    tab = SoundsTab(choose_file=lambda: mine)
    edits, played = [], []
    tab.edited.connect(edits.append)
    tab.play.connect(played.append)
    tab.buttons["trill"]["file"].click()
    assert edits[-1] == {"trill": mine}
    assert tab.buttons["trill"]["reset"].isEnabled()
    tab.buttons["trill"]["play"].click()
    assert played == ["trill"]
    tab.buttons["trill"]["reset"].click()
    assert edits[-1] == {}
    tab.set_recording(False, "no microphone found")
    assert not tab.buttons["ask"]["record"].isEnabled()


def test_the_settings_window_edits_his_voice_and_its_files(tmp_path):
    from zengo.app import Pet
    from zengo.config import Config
    from zengo.sprites.frames import build_frames

    files = VoiceFiles(tmp_path)
    pet = Pet(Config(), build_frames(), random.Random(1), voice_files=files)
    pet.open_settings()
    try:
        tabs = pet._settings_window.tabs
        assert [tabs.tabText(i) for i in range(tabs.count())] == [
            "General",
            "Life",
            "Words",
            "Sounds",
        ]
        pet._words_tab.moments.setCurrentRow(list(DEFAULT_PHRASES).index("fed"))
        pet._words_tab.lines.setPlainText("nom nom")
        pet._settings_window.close()  # takes up the edit
        assert pet.voice.lines("fed") == ("nom nom",)
        assert VoiceFiles(tmp_path).load().lines("fed") == ("nom nom",)
        elsewhere = tmp_path.parent / "somewhere" / "t.wav"
        pet._sounds_tab._choose = lambda: elsewhere
        pet._sounds_tab.buttons["trill"]["file"].click()
        assert VoiceFiles(tmp_path).load().sounds == {"trill": elsewhere}
    finally:
        pet._window.close()
