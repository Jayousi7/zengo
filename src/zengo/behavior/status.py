"""A read-out of Zengo's needs, for showing to you: how full he is and his odds
of getting hungry, his seeds, and how far he's got towards escaping a cage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from zengo.behavior.food import hunger_chance

if TYPE_CHECKING:
    from zengo.behavior.context import Context


@dataclass(frozen=True)
class Status:
    fullness: float
    hungry: bool
    hunger_chance: float
    """Odds he gets hungry at the next check (0 when he's hungry already)."""
    hunger_check_in: float
    food_stacks: int
    caged: bool
    escape_chance: float
    """Odds he gets out at his next try."""
    escape_try_in: float
    """Time caged still to go before his next try (it only runs while he's caged)."""
    escape_started: bool
    """Has he been caged long enough, all told, to start trying?"""
    escape_warmup: float
    """Before he starts trying: how far towards it, 0 to 1."""
    bond: float = 0.5
    """How close he feels to you, 0 (grumpy) to 1 (devoted)."""
    bond_mood: str = "content"
    """``"devoted"``, ``"content"`` or ``"grumpy"``."""


def read(ctx: Context, food_stacks: int) -> Status:
    cfg, hunger, cage, escape = ctx.config, ctx.hunger, ctx.cage, ctx.escape
    next_try = escape.next_try_at(cfg)
    return Status(
        fullness=hunger.fullness,
        hungry=hunger.hungry,
        hunger_chance=0.0 if hunger.hungry else hunger_chance(cfg, hunger.fullness),
        hunger_check_in=0.0 if hunger.hungry else hunger.check_in,
        food_stacks=food_stacks,
        caged=cage is not None and not cage.door_open,
        escape_chance=escape.chance_at_next_try(cfg),
        escape_try_in=max(0.0, next_try - escape.caged_for),
        escape_started=escape.caged_for >= cfg.escape_after,
        escape_warmup=min(1.0, escape.caged_for / cfg.escape_after) if cfg.escape_after else 1.0,
        bond=ctx.bond.level,
        bond_mood="devoted"
        if ctx.bond.close(cfg)
        else "grumpy"
        if ctx.bond.grumpy(cfg)
        else "content",
    )
