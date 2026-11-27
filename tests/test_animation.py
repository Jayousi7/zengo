import pytest

from zengo.animation import Animator, Clip

CLIPS = {
    "loop": Clip(("a", "b"), (1.0, 0.5)),
    "once": Clip.even("x", "y", fps=2, loop=False),
}


def test_clip_validates_shape():
    with pytest.raises(ValueError):
        Clip(("a",), (1.0, 2.0))
    with pytest.raises(ValueError):
        Clip(("a",), (0.0,))


def test_looping_clip_wraps_and_never_finishes():
    animator = Animator(CLIPS, "loop")
    animator.update(1.2)
    assert animator.frame == "b"
    animator.update(0.4)  # 1.6 wraps to 0.1
    assert animator.frame == "a"
    assert not animator.finished


def test_one_shot_holds_last_frame_and_finishes():
    animator = Animator(CLIPS, "once")
    animator.update(0.6)
    assert (animator.frame, animator.finished) == ("y", False)
    animator.update(10)
    assert (animator.frame, animator.finished) == ("y", True)


def test_replaying_current_clip_continues_unless_restarted():
    animator = Animator(CLIPS, "loop")
    animator.update(1.2)
    animator.play("loop")
    assert animator.frame == "b"
    animator.play("loop", restart=True)
    assert animator.frame == "a"


def test_unknown_clip_raises():
    with pytest.raises(KeyError):
        Animator(CLIPS, "loop").play("nope")
