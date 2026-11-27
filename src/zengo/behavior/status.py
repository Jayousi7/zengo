"""A read-out of Zengo's needs, for showing to you: how full he is, his odds of
getting hungry, his seeds, and, caged, his odds of escaping."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from zengo.behavior.cage import escape_chance
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
    escape_chance: float = 0.0
    """Caged: odds he gets out at his next try."""
    escape_try_in: float = 0.0
    """Caged: seconds to his next try."""
    escape_started: bool = False
    """Caged: has he started trying yet (after five minutes)?"""


def read(ctx: Context, food_stacks: int) -> Status:
    cfg, hunger, cage = ctx.config, ctx.hunger, ctx.cage
    status = Status(
        fullness=hunger.fullness,
        hungry=hunger.hungry,
        hunger_chance=0.0 if hunger.hungry else hunger_chance(cfg, hunger.fullness),
        hunger_check_in=0.0 if hunger.hungry else hunger.check_in,
        food_stacks=food_stacks,
        caged=cage is not None and not cage.door_open,
    )
    if not status.caged:
        return status
    assert cage is not None
    next_try = cage.next_try_at(cfg)
    return replace(
        status,
        escape_chance=escape_chance(cfg, max(next_try, cage.caged_for), cage.feedings),
        escape_try_in=max(0.0, next_try - cage.caged_for),
        escape_started=cage.caged_for >= cfg.escape_after,
    )
