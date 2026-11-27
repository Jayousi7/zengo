import pytest

from zengo.behavior.machine import Brain
from zengo.sprites.frames import FRAME_LAYERS, build_frames
from zengo.sprites.looks import PLAIN, Look, frame_in
from zengo.sprites.palette import PALETTE

FRAMES = build_frames()
WOOL = {PALETTE["R"], PALETTE["r"]}


def _has_wool(frame) -> bool:
    return any(p in WOOL for p in frame.pixels)


def test_the_plain_look_is_the_frame_itself():
    assert frame_in("perch", PLAIN, FRAMES, frozenset()) is FRAMES["perch"]


@pytest.mark.parametrize(
    "name",
    ["perch", "alert", "bob", "peck_low", "wings_up", "wings_down", "front_perch",
     "front_look_l", "branch_perch", "sulk", "ledge_perch", "turn_up", "listen_cock"],
)  # fmt: skip
def test_the_scarf_goes_round_his_neck_in_any_pose(name):
    assert not _has_wool(FRAMES[name])
    assert _has_wool(frame_in(name, Look(scarf=True), FRAMES, frozenset()))


def test_every_frame_with_a_head_gets_a_scarf():
    bare = [
        name
        for name in FRAME_LAYERS
        if not _has_wool(frame_in(name, Look(scarf=True), FRAMES, frozenset()))
    ]
    assert bare == []


def _top_row(frame) -> int:
    return next(
        y for y in range(frame.height) if any(frame.pixel(x, y) for x in range(frame.width))
    )


@pytest.mark.parametrize("name", ["perch", "alert", "front_alert", "branch_perch"])
def test_damp_slicks_his_crest_down(name):
    damp = frame_in(name, Look(damp=True), FRAMES, frozenset())
    assert _top_row(damp) > _top_row(FRAMES[name]) + 3


def test_damp_darkens_his_feathers_but_not_his_beak():
    plain, damp = FRAMES["perch"], frame_in("perch", Look(damp=True), FRAMES, frozenset())
    assert PALETTE["W"] in plain.pixels and PALETTE["W"] not in damp.pixels
    assert PALETTE["Q"] in damp.pixels


def test_a_frame_from_a_sheet_is_only_recoloured():
    custom = frozenset({"alert"})
    damp = frame_in("alert", Look(damp=True, scarf=True), FRAMES, custom)
    assert _top_row(damp) == _top_row(FRAMES["alert"])  # crest left as drawn
    assert not _has_wool(damp)
    assert PALETTE["W"] not in damp.pixels


def test_dim_darkens_every_pixel():
    plain, dim = FRAMES["perch"], frame_in("perch", Look(dim=True), FRAMES, frozenset())
    for a, b in zip(plain.pixels, dim.pixels, strict=True):
        assert (a is None) == (b is None)
        if a is not None:
            assert sum(b[:3]) < sum(a[:3])


def test_his_look_follows_bath_season_and_hour(ctx):
    brain = Brain(ctx)
    ctx.seasons.forced = "summer"
    ctx.world.hour = 12
    assert brain.look == PLAIN
    ctx.damp = 30.0
    assert brain.look == Look(damp=True)
    ctx.damp, ctx.seasons.forced, ctx.world.hour = 0.0, "winter", 22
    assert brain.look == Look(scarf=True, dim=True)
    ctx.seasons.enabled = False
    assert brain.look == PLAIN


def test_the_sheet_draws_a_look_when_first_asked():
    from zengo.behavior.body import Facing
    from zengo.ui.sprites import SpriteSheet

    sheet = SpriteSheet({"perch": FRAMES["perch"]}, 2)
    plain = sheet.get("perch", Facing.RIGHT)
    scarfed = sheet.get("perch", Facing.LEFT, Look(scarf=True))
    assert scarfed is sheet.get("perch", Facing.LEFT, Look(scarf=True))
    assert scarfed.pixmap.toImage() != plain.pixmap.toImage()
