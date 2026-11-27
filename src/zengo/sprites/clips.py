"""The animation catalogue. Every frame named here must exist in ``FRAME_LAYERS``."""

from zengo.animation import Clip

# Hanging from the cursor: long, irregular holds between small fidgets (a blink,
# a kick of the feet, a look down, a wing flick), so the ~7 s loop never reads as
# a pattern.
_HELD_FIDGETS = (
    ("held", 0.9),
    ("held_blink", 0.12),
    ("held", 0.6),
    ("held_kick_a", 0.14),
    ("held_kick_b", 0.14),
    ("held_kick_a", 0.14),
    ("held", 1.1),
    ("held_look", 0.9),
    ("held_blink", 0.12),
    ("held_look", 0.5),
    ("held", 0.7),
    ("held_flick", 0.12),
    ("held", 0.15),
    ("held_flick", 0.12),
    ("held", 0.8),
)

CLIPS: dict[str, Clip] = {
    # Irregular gaps and an occasional double blink keep idling from looking mechanical.
    "idle": Clip(
        ("perch", "blink", "perch", "blink", "perch", "blink"),
        (3.2, 0.12, 2.4, 0.12, 0.18, 0.12),
    ),
    "alert": Clip(("alert", "blink", "alert"), (0.7, 0.1, 0.6), loop=False),
    "walk": Clip.even("step_back", "perch", "step_front", "perch", fps=8),
    "preen": Clip(
        ("preen_a", "preen_b") * 4 + ("preen_a",),
        (0.35, 0.25) * 4 + (0.5,),
        loop=False,
    ),
    "sleep": Clip(("sleep",), (1.0,)),
    # Up, level, down, recover. Kept slow: fast two-frame flapping reads as an insect.
    "fly": Clip.even("wings_up", "wings_level", "wings_down", "wings_recover", fps=10),
    "glide": Clip(("wings_level",), (1.0,)),
    "flare": Clip(("wings_up",), (1.0,)),
    "flutter": Clip.even("wings_up", "wings_level", "wings_down", "wings_recover", fps=13),
    # Front view, banking round to fly the other way.
    "turn": Clip(("turn_up", "turn_down"), (0.12, 0.12)),
    "held": Clip(*zip(*_HELD_FIDGETS, strict=True)),
    # A quick ruffle after landing, then settle.
    "shake": Clip(
        ("shake_a", "shake_b") * 3 + ("perch",),
        (0.07,) * 6 + (0.25,),
        loop=False,
    ),
}
