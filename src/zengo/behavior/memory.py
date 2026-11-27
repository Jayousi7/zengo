"""What Zengo remembers between runs: where he was and which way he faced, whether
he was caged (and where the cage hung or stood, and the seeds in its dish), how
full he is, whether he's hungry, the seeds you've put out, how far he's got
towards escaping, and the words you've taught him.

Plain data in and out, so the app can keep it in a file. Restoring is forgiving:
anything missing, of the wrong type or out of range is left at its default, so a
damaged or old file never stops him starting. Timers pick up where they left off
rather than counting the time he was closed, so he isn't starving the moment
he's opened again.

Places are checked against the screens as they are now: anything remembered off
them is brought back on. Anywhere passing (the branch, your pointer, mid-air) he
comes back on the ground below.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from zengo.behavior import vocabulary
from zengo.behavior.body import Facing
from zengo.behavior.cage import BELOW_FLOOR, Cage
from zengo.behavior.food import STAND_OFF, Food, Pile
from zengo.behavior.voice import MOMENTS
from zengo.sprites.cage import CAGE_WIDTH, FLOOR
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
        "zengo": {"x": round(ctx.body.x, 1), "facing": int(ctx.body.facing)},
        "cage": _cage_snapshot(ctx.cage),
        "bond": round(ctx.bond.level, 4),
        "vocabulary": vocabulary.to_json(ctx.vocabulary),
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
    ctx.bond.level = _number(data.get("bond"), 0.0, 1.0, ctx.bond.level)
    if "vocabulary" in data:
        ctx.vocabulary = vocabulary.from_json(data["vocabulary"], tuple(MOMENTS))
    hunger = data.get("hunger")
    if isinstance(hunger, dict):
        h = ctx.hunger
        h.fullness = _number(hunger.get("fullness"), 0.0, 1.0, h.fullness)
        if isinstance(hunger.get("hungry"), bool):
            h.hungry = hunger["hungry"]
        h._check_in = _number(hunger.get("check_in"), 0.0, cfg.hunger_check_every, None)
        h._ask_in = _number(hunger.get("ask_in"), 0.0, cfg.nag_every, 0.0)

    zengo = data.get("zengo")
    if isinstance(zengo, dict):
        x = _number(zengo.get("x"), -math.inf, math.inf, None)
        if x is not None:
            area = ctx.world.area_at(x, ctx.body.y - 1)
            ctx.body.x, ctx.body.y = area.clamp_x(x, ctx.margin), area.bottom
        if zengo.get("facing") in (-1, 1):
            ctx.body.facing = Facing(zengo["facing"])

    cage = data.get("cage")
    if isinstance(cage, dict):
        ctx.cage = _cage_restored(ctx, cage)

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


def _cage_snapshot(cage: Cage | None) -> dict[str, Any] | None:
    if cage is None or cage.door_open:
        return None
    mount = cage.mount if cage.mount in ("chain", "shelf") else "ground"
    return {
        "x": round(cage.x, 1),
        "y": round(cage.y, 1),
        "mount": mount,
        "side": cage.side,
        "dish": cage.dish.seeds,
    }


def _cage_restored(ctx: Context, data: dict) -> Cage | None:
    """The cage put back where it was: hung, shelved or standing, on today's screens."""
    x = _number(data.get("x"), -math.inf, math.inf, None)
    y = _number(data.get("y"), -math.inf, math.inf, None)
    if x is None or y is None:
        return None
    cfg = ctx.config
    area = ctx.world.area_at(x, y - cfg.px(FLOOR / 2))
    half = cfg.px(CAGE_WIDTH / 2)
    x = min(max(x, area.left + half), area.right - half)
    y = min(max(y, area.top + cfg.px(FLOOR)), area.bottom - cfg.px(BELOW_FLOOR))
    cage = Cage(x=x, y=y, mount="held")
    mount = data.get("mount")
    if mount == "chain":
        cage._hang(ctx, area)
        cage.sway_speed = 0.0  # hanging still, not swinging from a throw
    elif mount == "shelf" and data.get("side") in (-1, 1) and cage.shelf_fits(ctx, area):
        cage._shelve(ctx, area, side=data["side"])
    else:
        cage.mount, cage.y = "ground", area.bottom - cfg.px(BELOW_FLOOR)
    cage.events.clear()  # nothing happened to it: it's simply where it was
    seeds = _number(data.get("dish"), 0, MAX_SEEDS, 0)
    cage.dish = Pile(seeds=int(seeds), shown=int(seeds))
    return cage
