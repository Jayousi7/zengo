"""Integrity checks on the actual art, so a bad edit fails fast instead of at runtime."""

from zengo.sprites.clips import CLIPS
from zengo.sprites.frames import CANVAS_HEIGHT, CANVAS_WIDTH, GROUND_ROW, build_frames

FRAMES = build_frames()


def test_every_clip_frame_exists():
    missing = {f for clip in CLIPS.values() for f in clip.frames} - FRAMES.keys()
    assert not missing


def test_every_frame_is_used():
    used = {f for clip in CLIPS.values() for f in clip.frames}
    assert FRAMES.keys() <= used


def test_frames_share_canvas():
    assert all((f.width, f.height) == (CANVAS_WIDTH, CANVAS_HEIGHT) for f in FRAMES.values())


def test_art_does_not_touch_canvas_edges():
    """The generated outline needs one free pixel all round, or it gets clipped."""
    for name, frame in build_frames(outline=None).items():
        for x in range(frame.width):
            assert frame.pixel(x, 0) is None, name
            assert frame.pixel(x, frame.height - 1) is None, name
        for y in range(frame.height):
            assert frame.pixel(0, y) is None, name
            assert frame.pixel(frame.width - 1, y) is None, name


def test_grounded_frames_stand_on_ground_row():
    """Feet must end exactly on GROUND_ROW, or Zengo floats or sinks into the taskbar."""
    from zengo.sprites.palette import PALETTE

    feet = {PALETTE["F"]}
    for name in ("perch", "blink", "alert", "step_back", "step_front", "preen_a", "sleep"):
        frame = FRAMES[name]
        lowest = max(
            y for y in range(frame.height) for x in range(frame.width) if frame.pixel(x, y) in feet
        )
        assert lowest == GROUND_ROW, name
