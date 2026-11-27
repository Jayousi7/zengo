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
    "walk": Clip.even("step_back", "perch", "step_front", "perch", fps=7),
    "preen": Clip(
        ("preen_a", "preen_b") * 4 + ("preen_a",),
        (0.35, 0.25) * 4 + (0.5,),
        loop=False,
    ),
    "sleep": Clip(("sleep",), (1.0,)),
    # Up, level, down, recover. Kept slow: fast two-frame flapping reads as an insect.
    "fly": Clip.even("wings_up", "wings_level", "wings_down", "wings_recover", fps=12),
    "glide": Clip(("wings_level",), (1.0,)),
    "flare": Clip(("wings_up",), (1.0,)),
    "flutter": Clip.even("wings_up", "wings_level", "wings_down", "wings_recover", fps=15),
    # Front view, banking round to fly the other way.
    "turn": Clip(("turn_up", "turn_down"), (0.12, 0.12)),
    "held": Clip(*zip(*_HELD_FIDGETS, strict=True)),
    # One seed: peck it up, crack it open, swallow. About a second each.
    "eat": Clip(
        ("peck_down", "peck_low", "peck_down", "chew_a", "chew_b", "chew_a", "chew_b"),
        (0.08, 0.16, 0.08, 0.18, 0.16, 0.18, 0.2),
    ),
    # Petted: a slow lean into the hand and back.
    "petted": Clip(("petted_a", "petted_b"), (1.1, 0.9)),
    # Whistling: crest up, nodding to the tune.
    "whistle": Clip(("whistle_a", "alert") * 7, (0.16,) * 14, loop=False),
    # A quick ruffle after landing, then settle.
    "shake": Clip(
        ("shake_a", "shake_b") * 3 + ("perch",),
        (0.07,) * 6 + (0.25,),
        loop=False,
    ),
}

# Facing you, sitting: long looks between blinks and glances to either side.
_FRONT_IDLE = (
    ("front_perch", 2.6),
    ("front_blink", 0.12),
    ("front_perch", 1.4),
    ("front_look_l", 0.9),
    ("front_perch", 0.5),
    ("front_look_r", 0.9),
    ("front_perch", 1.8),
    ("front_blink", 0.12),
    ("front_perch", 0.2),
    ("front_blink", 0.12),
)

FRONT_CLIPS: dict[str, Clip] = {
    "front_idle": Clip(*zip(*_FRONT_IDLE, strict=True)),
    "front_alert": Clip(("front_alert", "front_blink", "front_alert"), (0.7, 0.1, 0.6), loop=False),
    # Nibbling one shoulder, then the other.
    "front_preen": Clip(
        ("front_preen_a", "front_perch", "front_preen_b", "front_perch") * 2 + ("front_preen_a",),
        (0.45, 0.2, 0.45, 0.2) * 2 + (0.5,),
        loop=False,
    ),
    "front_fluff": Clip(
        ("front_fluff_a", "front_fluff_b") * 3 + ("front_perch",), (0.07,) * 6 + (0.3,), loop=False
    ),
    "front_sleep": Clip(("front_sleep",), (1.0,)),
    # Working the cage latch open with his beak, glancing about to see if you notice.
    "front_pick": Clip(
        ("front_peck", "front_look_r", "front_peck", "front_look_l"), (0.25, 0.3, 0.25, 0.3)
    ),
    # Asking for food: crest up, looking up at you, beak opening to call.
    "front_ask": Clip(
        (
            "front_alert",
            "front_whistle_a",
            "front_alert",
            "front_look_l",
            "front_alert",
            "front_whistle_a",
        ),
        (0.5, 0.2, 0.4, 0.3, 0.4, 0.2),
    ),
    # One seed: peck it up, crack it open, swallow. About a second each.
    "front_eat": Clip(
        ("front_peck", "front_chew", "front_perch", "front_chew", "front_perch"),
        (0.22, 0.2, 0.18, 0.2, 0.24),
    ),
    # Caged and furious: crest up, puffing and shaking, glaring this way and that.
    "front_angry": Clip(
        (
            "front_alert",
            "front_fluff_a",
            "front_fluff_b",
            "front_alert",
            "front_look_l",
            "front_look_r",
        ),
        (0.3, 0.08, 0.08, 0.35, 0.18, 0.18),
    ),
    "front_petted": Clip(("front_petted_a", "front_petted_b"), (1.1, 0.9)),
    "front_whistle": Clip(("front_whistle_a", "front_alert") * 7, (0.16,) * 14, loop=False),
}


def _on_branch(clip: Clip) -> Clip:
    names = tuple(name.replace("front_", "branch_") for name in clip.frames)
    return Clip(names, clip.durations, clip.loop)


CLIPS.update(FRONT_CLIPS)
CLIPS.update({name.replace("front_", "branch_"): _on_branch(c) for name, c in FRONT_CLIPS.items()})
# Turning round on the ground: a glimpse of his front, played over whatever he's doing.
CLIPS["ground_turn"] = Clip(("front_perch",), (0.18,), loop=False)
