import pytest

from zengo.sprites.compose import Layer, compose

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)
BLACK = (0, 0, 0, 255)
PALETTE = {"r": RED, "b": BLUE}


def test_parse_dedents_and_strips_blank_edges():
    layer = Layer.parse(
        """
        r.
        .r
        """,
        x=1,
        y=2,
    )
    assert layer == Layer(("r.", ".r"), 1, 2)


def test_later_layers_paint_over_earlier_ones_and_dots_are_transparent():
    frame = compose([Layer(("rr",)), Layer((".b",))], 2, 1, PALETTE)
    assert frame.pixels == (RED, BLUE)


def test_erase_clears_lower_layers():
    frame = compose([Layer(("rr",)), Layer(("_.",))], 2, 1, PALETTE)
    assert frame.pixels == (None, RED)


def test_pixels_outside_canvas_are_clipped():
    frame = compose([Layer(("rr",), x=-1), Layer(("r",), y=5)], 2, 1, PALETTE)
    assert frame.pixels == (RED, None)


def test_outline_surrounds_silhouette_orthogonally():
    frame = compose([Layer(("r",), x=1, y=1)], 3, 3, PALETTE, outline=lambda _: BLACK)
    assert frame.pixel(1, 1) == RED
    for x, y in ((0, 1), (2, 1), (1, 0), (1, 2)):
        assert frame.pixel(x, y) == BLACK
    assert frame.pixel(0, 0) is None  # diagonals stay clear for a crisper pixel-art edge


def test_outline_derives_from_darkest_neighbour():
    palette = {"w": (250, 250, 250, 255), "g": (90, 90, 90, 255)}
    frame = compose([Layer(("w.g",))], 3, 1, palette, outline=lambda c: c)
    assert frame.pixel(1, 0) == palette["g"]


def test_unknown_key_reports_position():
    with pytest.raises(ValueError, match=r"'x' at row 0, column 1"):
        compose([Layer(("rx",))], 2, 1, PALETTE)


def test_rgba_bytes_layout():
    frame = compose([Layer(("r.",))], 2, 1, PALETTE)
    assert frame.to_rgba_bytes() == bytes([255, 0, 0, 255, 0, 0, 0, 0])
