"""Words you teach him.

You type a word or short phrase and he listens, then tries it. It takes about
five lessons, at least an hour apart, before he has it; until then his tries
come out garbled ("he..o", "zen-zen"), better with each lesson. The closer he
feels to you, the fewer lessons he needs. You choose when he says it once
learned: any time (now and then, pottering about), or at one of his moments
(see :data:`zengo.behavior.voice.MOMENTS`).

He keeps up to :data:`MAX_WORDS` words; teaching one more makes him forget the
one he's used least. Words being learned are practised now and then, garbled.

Pure Python: no Qt.
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field

MAX_LENGTH = 20
MAX_WORDS = 10
LESSON_GAP = 3600.0
"""Seconds that must pass between lessons for the next one to count."""
LESSONS = 5
"""Lessons a bird of middling bond needs."""


def lessons_needed(bond: float, close: float) -> int:
    """Five lessons, four for a bird that likes you, three for a devoted one."""
    if bond >= close:
        return LESSONS - 2
    return LESSONS - 1 if bond >= 0.6 else LESSONS


@dataclass
class Word:
    text: str
    moment: str = "random"
    """When he says it, once learned: ``"random"`` (any time) or one of his moments."""
    lessons: int = 0
    last_lesson: float = -math.inf
    """Wall-clock time (seconds since the epoch) of the last lesson that counted."""
    uses: int = 0

    def learned(self, needed: int) -> bool:
        return self.lessons >= needed


@dataclass(frozen=True)
class Lesson:
    """How a lesson went, for the teaching box to tell you."""

    word: Word
    counted: bool
    """Far enough after the last one to count."""
    needed: int
    next_in: float
    """Seconds until the next lesson can count (0 once he has it)."""
    said: str
    """What he said back."""
    forgot: str | None = None
    """A word he forgot to make room."""

    @property
    def learned(self) -> bool:
        return self.word.learned(self.needed)


def clean(text: str) -> str:
    """The word as taught: trimmed, spaces squeezed, at most :data:`MAX_LENGTH` long."""
    return re.sub(r"\s+", " ", text).strip()[:MAX_LENGTH]


@dataclass
class Vocabulary:
    words: list[Word] = field(default_factory=list)

    def find(self, text: str) -> Word | None:
        key = clean(text).casefold()
        return next((w for w in self.words if w.text.casefold() == key), None)

    def teach(
        self, text: str, moment: str, now: float, needed: int, rng: random.Random
    ) -> Lesson | None:
        """A lesson: ``text`` said to him for him to learn. ``None`` if there's
        nothing to teach (empty text)."""
        text = clean(text)
        if not text:
            return None
        word, forgot = self.find(text), None
        if word is None:
            if len(self.words) >= MAX_WORDS:
                least = min(self.words, key=lambda w: (w.uses, w.lessons, w.last_lesson))
                self.words.remove(least)
                forgot = least.text
            word = Word(text, moment)
            self.words.append(word)
        word.moment = moment
        counted = not word.learned(needed) and now - word.last_lesson >= LESSON_GAP
        if counted:
            word.lessons += 1
            word.last_lesson = now
            if word.learned(needed):
                word.lessons = LESSONS  # his for good, however he feels about you later
        if word.learned(needed):
            return Lesson(word, counted, needed, 0.0, word.text, forgot)
        next_in = max(0.0, word.last_lesson + LESSON_GAP - now)
        said = garble(word.text, word.lessons / needed, rng)
        return Lesson(word, counted, needed, next_in, said, forgot)

    def forget(self, text: str) -> None:
        word = self.find(text)
        if word is not None:
            self.words.remove(word)

    def learned(self, moment: str, needed: int) -> list[Word]:
        return [w for w in self.words if w.moment == moment and w.learned(needed)]

    def learning(self, needed: int) -> list[Word]:
        return [w for w in self.words if not w.learned(needed)]


def garble(text: str, progress: float, rng: random.Random) -> str:
    """A try at ``text`` by a bird ``progress`` (0 to 1) of the way to knowing it.

    Barely started, he gets the first sound or two and repeats it ("zen-zen");
    further on, the word's all there but with letters missing ("he..o"), fewer
    with each lesson."""
    letters = [i for i, c in enumerate(text) if c.isalnum()]
    if not letters:
        return text
    if progress < 0.25:
        start = text[: max(2, min(4, len(text) // 2))].strip()
        return f"{start}-{start}" if rng.random() < 0.6 else f"{start}..."
    keep = max(0.3, min(0.95, progress))
    chars = list(text)
    for i in letters[1:]:
        if rng.random() > keep:
            chars[i] = "."
    tried = "".join(chars)
    if tried == text and len(letters) > 1:
        i = rng.choice(letters[1:])
        tried = text[:i] + "." + text[i + 1 :]
    return tried


# --- Remembering -----------------------------------------------------------------


def to_json(vocabulary: Vocabulary) -> list[dict[str, object]]:
    return [
        {
            "text": w.text,
            "moment": w.moment,
            "lessons": w.lessons,
            "last_lesson": None if math.isinf(w.last_lesson) else round(w.last_lesson, 1),
            "uses": w.uses,
        }
        for w in vocabulary.words
    ]


def from_json(data: object, moments: tuple[str, ...]) -> Vocabulary:
    """The words in ``data``; anything unusable is left out."""
    vocabulary = Vocabulary()
    if not isinstance(data, list):
        return vocabulary
    for item in data[:MAX_WORDS]:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if not isinstance(text, str) or not clean(text) or vocabulary.find(text):
            continue
        moment = item.get("moment")
        lessons, last, uses = item.get("lessons"), item.get("last_lesson"), item.get("uses")
        vocabulary.words.append(
            Word(
                clean(text),
                moment if moment in moments else "random",
                lessons if isinstance(lessons, int) and 0 <= lessons <= 100 else 0,
                float(last) if isinstance(last, int | float) and math.isfinite(last) else -math.inf,
                uses if isinstance(uses, int) and uses >= 0 else 0,
            )
        )
    return vocabulary
