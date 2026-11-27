"""The particles in :mod:`zengo.behavior.effects`, as tiny pieces of pixel art."""

from __future__ import annotations

from zengo.sprites.compose import Frame, Layer, compose
from zengo.sprites.palette import PALETTE, outline_for

_ART: dict[str, tuple[str, ...]] = {
    "drop": ("A", "a"),
    "snow": (".W.", "WWW", ".W."),
    "leaf_0": ("EEe.", ".eEE"),
    "leaf_1": ("..E", ".EE", "eE."),
    "leaf_-1": ("E..", "EE.", ".Ee"),
}


def particle_name(kind: str, tilt: int) -> str:
    return f"leaf_{tilt}" if kind == "leaf" else kind


def build_particles() -> dict[str, Frame]:
    """Each particle's picture, outlined, with a clear border for the outline."""
    frames = {}
    for name, rows in _ART.items():
        width = max(len(row) for row in rows)
        frames[name] = compose([Layer(rows, 1, 1)], width + 2, len(rows) + 2, PALETTE, outline_for)
    return frames
