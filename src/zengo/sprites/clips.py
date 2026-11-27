"""The animation catalogue. Every frame named here must exist in ``FRAME_LAYERS``."""

from zengo.animation import Clip
from zengo.sprites.frames import LEDGE_LAYERS

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
    # One step: feet together, push off with the back foot lifted, then reach
    # forward with it. The body moves a stride between push-off and reach, while
    # the planted foot stays put (see behavior.states.STRIDE). A step every
    # 0.22 s, 3 px each: about 14 art px a second, a long bird's quick little waddle.
    "walk": Clip(("perch", "step_back", "step_front"), (0.08, 0.07, 0.07)),
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
    # Startled off a perch that went from under him: fast, crest up. Shown over
    # the fall's own flapping, once.
    "startle": Clip.even(
        *("startle_up", "startle_level", "startle_down", "startle_recover") * 3,
        fps=18,
        loop=False,
    ),
    # Balancing on a window that's being moved: shown over whatever he's doing.
    "grip": Clip(("grip",), (0.3,), loop=False),
    # Front view, banking round to fly the other way.
    "turn": Clip(("turn_up", "turn_down"), (0.12, 0.12)),
    "held": Clip(*zip(*_HELD_FIDGETS, strict=True)),
    # One seed: peck it up, crack it open, swallow. About a second each.
    "eat": Clip(
        ("peck_down", "peck_low", "peck_down", "chew_a", "chew_b", "chew_a", "chew_b"),
        (0.08, 0.16, 0.08, 0.18, 0.16, 0.18, 0.2),
    ),
    # Bobbing his head along while you type: forward and down, back through the
    # same in-between. Uneven beats, so minutes of it never look mechanical.
    "bob": Clip(
        ("perch", "bob_fwd", "bob", "bob_fwd") * 3,
        (0.12, 0.05, 0.13, 0.05, 0.16, 0.05, 0.11, 0.05, 0.1, 0.06, 0.15, 0.05),
    ),
    # Petted: a slow lean into the hand and back.
    "petted": Clip(("petted_a", "petted_b"), (1.1, 0.9)),
    # Whistling: crest up, head tipped back once, then only the beak works with
    # the tune; the head comes level again at the end. Same length as before.
    "whistle": Clip(
        ("alert", "whistle_b", *("whistle_a", "whistle_b") * 6, "alert"),
        (0.1, 0.12, *(0.16,) * 12, 0.1),
        loop=False,
    ),
    # A lesson: he turns to you and cocks his head, listening, now and then
    # turning back to check; then says the word, beak working, and closes it.
    "listen": Clip(("listen_turn", "listen_cock"), (0.3, 1.1)),
    "talk": Clip((*("talk_a", "talk_b") * 4,), (0.12, 0.1) * 4, loop=False),
    # A quick ruffle after landing, then settle.
    # Turned towards you, back through the middle, away, and so on: a turn of the
    # head each way, quick but never skipping the middle.
    "shake": Clip(
        ("shake_mid",) + ("shake_a", "shake_mid", "shake_b", "shake_mid") * 2 + ("perch",),
        (0.12,) + (0.07, 0.05, 0.07, 0.05) * 2 + (0.25,),
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
        ("front_fluff_a", "front_alert", "front_fluff_b", "front_alert") * 2 + ("front_perch",),
        (0.07, 0.05, 0.07, 0.05) * 2 + (0.3,),
        loop=False,
    ),
    "front_sleep": Clip(("front_sleep",), (1.0,)),
    # Bobbing his head along while you type, on uneven beats.
    "front_bob": Clip(
        ("front_perch", "front_bob") * 3,
        (0.14, 0.16, 0.18, 0.13, 0.12, 0.17),
    ),
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
    # Nodding down to bow over the dish, then back up through the nod to crack it.
    "front_eat": Clip(
        (
            "front_bob",
            "front_peck",
            "front_bob",
            "front_chew",
            "front_perch",
            "front_chew",
            "front_perch",
        ),
        (0.06, 0.18, 0.06, 0.2, 0.18, 0.18, 0.18),
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

# Sulking with his back to you: long stretches of cold shoulder, a peek round to
# see if you've noticed, and a huffy puff.
CLIPS["sulk"] = Clip(
    ("sulk", "sulk_peek", "sulk", "sulk_huff", "sulk", "sulk_peek"),
    (2.4, 0.7, 1.8, 0.5, 2.0, 0.4),
)


def _on_branch(clip: Clip) -> Clip:
    names = tuple(name.replace("front_", "branch_") for name in clip.frames)
    return Clip(names, clip.durations, clip.loop)


CLIPS.update(FRONT_CLIPS)
CLIPS.update({name.replace("front_", "branch_"): _on_branch(c) for name, c in FRONT_CLIPS.items()})
# Turning round on the ground: a glimpse of his front, played over whatever he's doing.
CLIPS["ground_turn"] = Clip(("front_perch",), (0.18,), loop=False)


def _on_ledge(clip: Clip) -> Clip:
    """The same clip sitting on something thin: frames with the tail angled down."""
    names = tuple(n if f"ledge_{n}" not in LEDGE_LAYERS else f"ledge_{n}" for n in clip.frames)
    return Clip(names, clip.durations, clip.loop)


LEDGE_CLIPS = ("idle", "preen", "shake", "sleep", "alert", "whistle", "petted", "bob", "grip")
"""Side-on clips he plays sitting on your pointer or a window: each has a ``ledge_``
version with his tail hanging down past the perch."""
CLIPS.update({f"ledge_{name}": _on_ledge(CLIPS[name]) for name in LEDGE_CLIPS})
