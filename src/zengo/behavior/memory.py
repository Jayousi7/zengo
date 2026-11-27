"""What Zengo remembers between runs: how full he is, whether he's hungry, the
seeds you've put out, and how far he's got towards escaping a cage.

Plain data in and out, so the app can keep it in a file. Restoring is forgiving:
anything missing, of the wrong type or out of range is left at its default, so a
damaged or old file never stops him starting. Timers pick up where they left off
rather than counting the time he was closed, so he isn't starving the moment
he's opened again.

The cage itself isn't remembered: he always starts free, so seeds in a cage dish go
with it.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from zengo.behavior.food import STAND_OFF, Food, Pile
from zengo.sprites.food import MAX_SEEDS

if TYPE_CHECKING:
    from zengo.behavior.context import Context

VERSION = 1


def snapshot(ctx: Context) -> dict[str, Any]:
    hunger, food = ctx.hunger, ctx.food
    return {
        "version": VERSION,
        "hunger": {
            "fullness": round(hunger.fullness, 4),
            "hungry": hunger.hungry,
            "check_in": round(hunger.check_in, 2),
            "ask_in": round(max(0.0, hunger._ask_in), 2),
        },
        "food": None if food is None else {"x": round(food.x, 1), "seeds": food.pile.seeds},
        "escape": {
            "caged_for": round(ctx.escape.caged_for, 2),
            "feedings": ctx.escape.feedings,
            "next_try": None if ctx.escape.next_try is None else round(ctx.escape.next_try, 2),
        },
    }


def restore(ctx: Context, data: object) -> None:
    """Take up what ``data`` remembers. Anything unusable is ignored."""
    if not isinstance(data, dict) or data.get("version") != VERSION:
        return
    cfg = ctx.config
    hunger = data.get("hunger")
    if isinstance(hunger, dict):
        h = ctx.hunger
        h.fullness = _number(hunger.get("fullness"), 0.0, 1.0, h.fullness)
        if isinstance(hunger.get("hungry"), bool):
            h.hungry = hunger["hungry"]
        h._check_in = _number(hunger.get("check_in"), 0.0, cfg.hunger_check_every, None)
        h._ask_in = _number(hunger.get("ask_in"), 0.0, cfg.nag_every, 0.0)

    escape = data.get("escape")
    if isinstance(escape, dict):
        e = ctx.escape
        e.caged_for = _number(escape.get("caged_for"), 0.0, math.inf, e.caged_for)
        e.feedings = int(_number(escape.get("feedings"), 0, 10_000, e.feedings))
        e.next_try = _number(escape.get("next_try"), 0.0, math.inf, None)

    food = data.get("food")
    if isinstance(food, dict):
        seeds = _number(food.get("seeds"), 0, MAX_SEEDS, 0)
        x = _number(food.get("x"), -math.inf, math.inf, None)
        if seeds >= 1 and x is not None:
            # Screens may have changed since: put it back on his, within his reach.
            area, reach = ctx.area(), cfg.px(STAND_OFF)
            lo, hi = area.left + ctx.margin + reach, area.right - ctx.margin - reach
            pile = Pile(seeds=int(seeds), shown=int(seeds))
            ctx.food = Food(min(max(x, lo), hi), area.bottom, pile)


def _number(value: object, low: float, high: float, default):
    if isinstance(value, bool) or not isinstance(value, int | float) or math.isnan(value):
        return default
    return min(max(value, low), high)
