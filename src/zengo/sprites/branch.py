"""The branch that now and then grows out from a screen edge for Zengo to sit on.

Drawn growing out from the left edge; the right edge uses a mirrored copy.
Column 0 is the end at the screen edge. Along the perch the upper surface is
flat and kept clear of leaves, so he has somewhere to sit.
"""

from __future__ import annotations

from zengo.sprites.compose import Frame, Layer, compose
from zengo.sprites.palette import PALETTE, outline_for

BRANCH = Layer.parse(
    """
    ........................YVYYYVYYYV
    ........................YYVYYYYVV................................................V
    .........................YYYVVvvv................................................YVvYYV
    ...........................Nn....................................................YVYYVv
    ..........................Nn.....................................................YYYVYYY
    .......V.................Nn....................................................OOnYYYYVVV
    ...YVvYV.Y..............Nn...................................................OOnn..VYYYv
    ...YYYYYYVv............Nn..................................................OOnn....VYVYY
    ...YYYYYVv............Nn.................................................OOnn......vYYVVY
    ....YYYVvv...........Nn................................................OOnn........vVY
    ......Vv............Nn.............................................OOOOnn..........vVY
    OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOONNNN..............V
    NNnNNNNNNNNNNNNnnNNnNNnNNNNNnNnnNNNNnNNNNNNnnNNNNnNNNNNNNNNNNNNNNNNnnnn
    NNNNNnNNnNNNNNNNNNNNNNnNNNNNNNNNNNNNNNnNNNNNNnNnnnnnnnnnnnnnnnnnnnn
    NNNnNNNnnNNNNNNNNNNnnNnnnnnnnnnnnnnnnnnnnnnnnnn......vV
    nnnnnnnnnnnnvvVnnnnnnn.............................vvVYYY
    ...........vVVYYY..................................vVYYYYY
    ...........VYYYYY..................................VYYYYVY
    ...........YYYYYY....................................vY.vV
    .............VYvV
    """
)

BRANCH_WIDTH = max(len(row) for row in BRANCH.rows)
BRANCH_HEIGHT = len(BRANCH.rows)

TOP_ROW = 11
"""Row of the upper surface along the perch: his feet rest on top of it."""

PERCH = (42, 58)
"""Columns, counted from the screen edge, where he may sit."""


def build_branch() -> Frame:
    """The branch with a one-pixel clear border all round for its outline."""
    return compose(
        [BRANCH.shifted(1, 1)], BRANCH_WIDTH + 2, BRANCH_HEIGHT + 2, PALETTE, outline_for
    )
