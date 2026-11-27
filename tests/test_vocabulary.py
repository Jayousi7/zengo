"""Teaching him words: lessons an hour apart, garbled tries, and saying them."""

import random

import pytest

from zengo.behavior.machine import Brain
from zengo.behavior.memory import restore, snapshot
from zengo.behavior.states import Idle, Listen
from zengo.behavior.vocabulary import (
    LESSON_GAP,
    MAX_WORDS,
    Vocabulary,
    garble,
    lessons_needed,
)

HOUR = LESSON_GAP
DT = 1 / 30


def test_a_word_takes_five_lessons_an_hour_apart():
    vocab, rng = Vocabulary(), random.Random(1)
    t = 1_000_000.0
    first = vocab.teach("hello", "random", t, 5, rng)
    assert first.counted and first.word.lessons == 1 and not first.learned
    assert first.said != "hello"  # a garbled try
    too_soon = vocab.teach("hello", "random", t + 600, 5, rng)
    assert not too_soon.counted and too_soon.word.lessons == 1
    assert too_soon.next_in == pytest.approx(HOUR - 600)
    for i in range(2, 6):
        lesson = vocab.teach("Hello ", "random", t + i * HOUR, 5, rng)  # same word
    assert lesson.learned and lesson.said == "hello" and lesson.next_in == 0
    assert len(vocab.words) == 1


def test_a_bonded_bird_learns_faster():
    assert lessons_needed(0.5, 0.8) == 5
    assert lessons_needed(0.65, 0.8) == 4
    assert lessons_needed(0.9, 0.8) == 3


def test_once_learned_its_his_for_good():
    vocab, rng = Vocabulary(), random.Random(1)
    for i in range(3):
        lesson = vocab.teach("hi", "random", i * HOUR, 3, rng)  # devoted: three lessons
    assert lesson.learned
    assert vocab.learned("random", 5)  # still known when he likes you less


def test_garbled_tries_get_better():
    rng = random.Random(3)
    early = garble("zengo", 0.1, rng)
    assert early.startswith("ze") and early != "zengo"
    late = [garble("pretty bird", 0.8, rng) for _ in range(20)]
    assert all(len(t) == len("pretty bird") and t != "pretty bird" for t in late)
    assert sum(t.count(".") for t in late) < sum(
        garble("pretty bird", 0.4, rng).count(".") for _ in range(20)
    )


def test_teaching_an_eleventh_word_forgets_the_least_used():
    vocab, rng = Vocabulary(), random.Random(1)
    for i in range(MAX_WORDS):
        vocab.teach(f"word{i}", "random", 0, 5, rng)
        vocab.words[-1].uses = 5
    vocab.words[3].uses = 0
    lesson = vocab.teach("new one", "random", 0, 5, rng)
    assert lesson.forgot == "word3" and len(vocab.words) == MAX_WORDS


def test_a_lesson_makes_him_listen_then_try_it(ctx):
    ctx.clock = lambda: 5_000.0
    brain = Brain(ctx, Idle())
    lesson = brain.lesson("good bird", "fed")
    assert isinstance(brain.state, Listen) and lesson.word.lessons == 1
    for _ in range(round(2 / DT)):
        brain.tick(DT)
    assert ctx.speech is not None and ctx.speech.text == lesson.said
    for _ in range(round(3 / DT)):
        brain.tick(DT)
    assert isinstance(brain.state, Idle)


def test_no_lessons_when_he_cant_listen(ctx):
    brain = Brain(ctx, Idle())
    assert brain.catch_in(ctx.body.x - 40, ctx.body.y - 80, ctx.body.x + 40, ctx.body.y + 10)
    assert "caged" in brain.can_learn()
    assert brain.lesson("hi", "random") is None


def test_learned_words_are_said_at_their_moment(ctx):
    vocab = ctx.vocabulary
    for i in range(5):
        vocab.teach("snack time", "hungry", i * HOUR, 5, ctx.rng)
    said = {ctx.phrase("hungry") for _ in range(60)}
    assert "snack time" in said and said & set(ctx.voice.lines("hungry"))
    assert "snack time" not in {ctx.phrase("fed") for _ in range(60)}
    assert vocab.words[0].uses > 0


def test_words_being_learned_are_practised_garbled_now_and_then(ctx):
    ctx.vocabulary.teach("hello there", "random", 0, 5, ctx.rng)
    said = [ctx.phrase("random") for _ in range(100)]
    assert any(s != "♪" and s != "hello there" for s in said)
    assert "hello there" not in said


def test_taught_words_are_remembered_and_forgotten_on_reset(ctx):
    ctx.vocabulary.teach("hi", "petted", 123.0, 5, ctx.rng)
    data = snapshot(ctx)
    ctx.vocabulary = Vocabulary()
    restore(ctx, data)
    word = ctx.vocabulary.words[0]
    assert (word.text, word.moment, word.lessons, word.last_lesson) == ("hi", "petted", 1, 123.0)
    restore(ctx, {**data, "vocabulary": [{"text": 5}, "junk", {"text": "ok", "lessons": -3}]})
    assert [(w.text, w.lessons) for w in ctx.vocabulary.words] == [("ok", 0)]
    Brain(ctx, Idle()).forget()
    assert ctx.vocabulary.words == []


def test_the_teach_box_tells_you_how_it_went():
    from zengo.behavior.vocabulary import Lesson, Word
    from zengo.ui.teach_box import TeachBox, outcome

    assert "Lesson 2 of 5" in outcome(Lesson(Word("hi", lessons=2), True, 5, HOUR, "h."))
    assert "too soon" in outcome(Lesson(Word("hi", lessons=2), False, 5, 1800, "h."))
    assert "30 minutes" in outcome(Lesson(Word("hi", lessons=2), False, 5, 1800, "h."))
    assert "got it" in outcome(Lesson(Word("hi", "fed", lessons=5), True, 5, 0, "hi"))
    assert "after a meal" in outcome(Lesson(Word("hi", "fed", lessons=5), True, 5, 0, "hi"))

    lessons = []
    box = TeachBox(lambda t, m: lessons.append((t, m)), lambda: "He's away. Show him first.")
    box.word.setText("hi")
    box.button.click()
    assert lessons == [] and "away" in box.result.text()
    assert box.when.findData("whistle") == -1  # whistles go with his tunes
    box.close()


def test_lessons_show_in_the_words_tab_and_can_be_forgotten_there(tmp_path):
    from zengo.app import Pet
    from zengo.behavior.voice import VoiceFiles
    from zengo.config import Config
    from zengo.sprites.frames import build_frames

    pet = Pet(Config(), build_frames(), random.Random(1), voice_files=VoiceFiles(tmp_path))
    try:
        pet.open_settings()
        tab = pet._words_tab
        assert tab.no_words.isVisibleTo(tab)
        assert pet.teach("hello", "random") is not None
        assert tab.taught.count() == 1 and "1 of 5 lessons" in tab.taught.item(0).text()
        tab.taught.setCurrentRow(0)
        tab.forget_button.click()
        assert pet._brain.ctx.vocabulary.words == [] and tab.taught.count() == 0
    finally:
        pet._settings_window.close()
        pet._window.close()


def test_he_cocks_his_head_to_listen_and_his_beak_works_as_he_tries_it(ctx):
    ctx.clock = lambda: 0.0
    brain = Brain(ctx, Idle())
    brain.lesson("hello", "random")
    brain.tick(DT)
    assert ctx.animator.clip_name == "listen"
    seen = set()
    for _ in range(round(1.4 / DT)):
        brain.tick(DT)
        seen.add(ctx.animator.frame)
    assert {"listen_turn", "listen_cock"} <= seen
    for _ in range(round(0.5 / DT)):
        brain.tick(DT)
        seen.add(ctx.animator.frame)
    assert {"talk_a", "talk_b"} <= seen


def test_saying_a_taught_word_works_his_beak(ctx):
    from dataclasses import replace

    for i in range(5):
        ctx.vocabulary.teach("hi there", "random", i * HOUR, 5, ctx.rng)
    ctx.config = replace(ctx.config, chirp_every=0.01)
    brain = Brain(ctx, Idle())
    for _ in range(300):
        brain.tick(DT)
        if ctx.speech is not None and ctx.speech.text == "hi there":
            break
    assert ctx.speech.text == "hi there"
    frames = set()
    for _ in range(10):
        frames.add(ctx.animator.frame)
        brain.tick(DT)
    assert frames & {"talk_a", "talk_b"}


def test_no_lessons_up_on_a_perch(ctx):
    brain = Brain(ctx, Idle())
    ctx.body.y -= 200  # up on a window, say
    assert "settled on the ground" in brain.can_learn()
