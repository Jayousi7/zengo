"""Seeds, stacks, hunger, and asking for food."""

import pytest

from zengo.behavior.food import STAND_OFF, Pile, hunger_chance
from zengo.behavior.machine import Brain
from zengo.behavior.states import (
    Ask,
    Caged,
    Eat,
    Fall,
    Fly,
    FrontIdle,
    Idle,
    OnBranch,
    Sleep,
)
from zengo.sprites.food import MAX_SEEDS, MAX_STACKS, SEEDS_PER_STACK

DT = 1 / 30


def run(brain: Brain, seconds: float) -> None:
    for _ in range(round(seconds / DT)):
        brain.tick(DT)


def run_until(brain: Brain, kind: type, limit: float = 60.0) -> None:
    for _ in range(round(limit / DT)):
        brain.tick(DT)
        if isinstance(brain.state, kind):
            return
    raise AssertionError(f"never reached {kind.__name__}; stuck in {brain.state!r}")


def make_hungry(ctx):
    ctx.hunger.hungry = True
    ctx.hunger.fullness = 0.0
    ctx.hunger._ask_in = 0.0


# --- Stacks ------------------------------------------------------------------


def test_each_feed_pours_on_a_stack_up_to_three(ctx):
    brain = Brain(ctx, Idle())
    for n in range(1, MAX_STACKS + 1):
        assert brain.feed()
        assert brain.food_stacks == n
    assert not brain.feed()  # full
    assert brain.food_stacks == MAX_STACKS
    assert ctx.food.pile.seeds == MAX_SEEDS
    assert "plenty" in ctx.speech.text


def test_the_pile_visibly_fills_as_a_stack_pours_on(ctx):
    brain = Brain(ctx, Idle())
    brain.feed()
    shown = []
    for _ in range(round(1 / DT)):
        brain.tick(DT)
        shown.append(round(ctx.food.pile.shown))
    assert shown[0] < SEEDS_PER_STACK  # it doesn't just appear
    assert shown == sorted(shown) and shown[-1] == SEEDS_PER_STACK


def test_seeds_go_down_in_front_of_him(ctx):
    brain = Brain(ctx, Idle())
    brain.feed()
    assert ctx.food.y == ctx.world.area.bottom
    assert ctx.food.x > ctx.body.x  # he faces right: in front of him


def test_a_partly_eaten_pile_still_counts_its_stacks():
    pile = Pile(seeds=SEEDS_PER_STACK + 3)
    assert pile.stacks == 2
    assert pile.add_stack()
    assert not Pile(seeds=MAX_SEEDS - SEEDS_PER_STACK + 1).add_stack()


# --- Hunger ------------------------------------------------------------------


def test_not_hungry_he_leaves_the_seeds_for_later(ctx):
    brain = Brain(ctx, Idle())
    brain.feed()
    assert "later" in ctx.speech.text
    run(brain, 20)
    assert ctx.food.pile.seeds == SEEDS_PER_STACK


def test_fullness_drains_with_time(ctx):
    ctx.hunger.fullness = 1.0
    for _ in range(round(60 / DT)):
        ctx.hunger.update(ctx, DT, effort=1.0)  # a minute at rest
    assert ctx.hunger.fullness == pytest.approx(1 - ctx.config.hunger_drain, abs=0.002)


@pytest.mark.parametrize(
    ("busy", "faster_than_resting"),
    [(lambda ctx: Fly.tour(ctx), True), (lambda ctx: Sleep(), False)],
)
def test_activity_drains_him_faster_and_sleep_slower(ctx, world, busy, faster_than_resting):
    world.hour = 2  # so a nap stays a nap
    ctx.hunger.fullness = 1.0
    brain = Brain(ctx, FrontIdle())
    run(brain, 3)
    resting = 1.0 - ctx.hunger.fullness
    ctx.hunger.fullness = 1.0
    brain.transition(busy(ctx))
    run(brain, 3)
    busy_drain = 1.0 - ctx.hunger.fullness
    assert (busy_drain > 1.5 * resting) if faster_than_resting else (busy_drain < 0.6 * resting)


def test_the_odds_of_getting_hungry_follow_how_full_he_is(ctx):
    cfg = ctx.config
    assert hunger_chance(cfg, 1.0) == 0
    assert hunger_chance(cfg, cfg.peckish_below) == 0  # well fed: never
    half, low = hunger_chance(cfg, 0.5), hunger_chance(cfg, 0.2)
    assert 0 < half < low < 1  # likelier the emptier he is
    assert hunger_chance(cfg, 0.0) == 1  # empty: certain


def test_well_fed_he_never_gets_hungry(ctx):
    ctx.hunger.fullness = 1.0
    brain = Brain(ctx, Idle())
    run(brain, 4 * 60)  # still above peckish
    assert not ctx.hunger.hungry


def test_empty_he_gets_hungry_at_the_next_check(ctx):
    ctx.hunger.fullness = 0.0
    brain = Brain(ctx, Idle())
    run(brain, ctx.config.hunger_check_every + 1)
    assert ctx.hunger.hungry


def test_a_meal_fills_him_up_and_stops_when_he_is_full(ctx):
    brain = Brain(ctx, Idle())
    brain.feed()
    run(brain, 1)
    make_hungry(ctx)
    ctx.hunger.fullness = 0.9  # nearly full already
    run_until(brain, Eat, limit=10)
    run_until(brain, Idle, limit=SEEDS_PER_STACK * 1.2 + 3)
    assert ctx.hunger.fullness > 0.99
    assert 0 < ctx.food.pile.seeds < SEEDS_PER_STACK  # he stopped part way through


def test_hungry_he_eats_one_stack_and_leaves_the_rest(ctx):
    brain = Brain(ctx, Idle())
    brain.feed()
    brain.feed()
    run(brain, 2)
    make_hungry(ctx)
    run_until(brain, Eat, limit=10)
    food = ctx.food
    assert ctx.body.x == pytest.approx(food.x - ctx.config.px(STAND_OFF), abs=1)
    run_until(brain, Idle, limit=SEEDS_PER_STACK * 1.2 + 3)
    assert not ctx.hunger.hungry
    assert food.pile.seeds == SEEDS_PER_STACK  # one stack left
    assert brain.food_stacks == 1


def test_eating_the_last_stack_clears_the_pile_away(ctx):
    brain = Brain(ctx, Idle())
    brain.feed()
    run(brain, 1)
    make_hungry(ctx)
    run_until(brain, Eat, limit=10)
    run_until(brain, Idle, limit=SEEDS_PER_STACK * 1.2 + 3)
    assert ctx.food is None


def test_hungry_with_nothing_to_eat_he_comes_to_you_and_asks(ctx, world):
    world.cursor_pos = (ctx.body.x + 500, 600)
    brain = Brain(ctx, Idle())
    make_hungry(ctx)
    brain.tick(DT)
    assert isinstance(brain.state, Fly) and brain.state.onto == "ask"
    run_until(brain, Ask, limit=15)
    assert ctx.body.x == pytest.approx(world.cursor_pos[0], abs=1)  # right below your pointer
    assert ctx.body.y == ctx.world.area.bottom
    assert ctx.speech.text in ctx.config.begging


def test_feed_him_while_he_asks_and_he_eats_straight_away(ctx, world):
    world.cursor_pos = (ctx.body.x + 300, 700)
    brain = Brain(ctx, Idle())
    make_hungry(ctx)
    run_until(brain, Ask, limit=15)
    brain.feed()
    assert "seeds" in ctx.speech.text
    run_until(brain, Eat, limit=10)


def test_ignored_he_gives_up_and_asks_again_later(ctx, world):
    world.cursor_pos = (ctx.body.x + 50, 700)
    brain = Brain(ctx, Idle())
    make_hungry(ctx)
    run_until(brain, Ask, limit=10)
    run_until(brain, Idle, limit=Ask.gives_up_after + 1)
    assert ctx.hunger.hungry
    run(brain, ctx.config.nag_every - 2)
    state = brain.state
    asking = isinstance(state, Ask) or getattr(state, "then", None) == "ask"
    asking = asking or getattr(state, "onto", None) == "ask"
    assert not asking  # not straight away
    run_until(brain, Ask, limit=6)  # but again, a couple of minutes on


def test_from_the_branch_he_flies_down_to_eat(ctx):
    brain = Brain(ctx, Idle())
    ctx.scenery.grow(ctx)
    run(brain, ctx.config.branch_grow_seconds + 0.1)
    brain.transition(Fly.to_branch(ctx))
    run_until(brain, OnBranch, limit=20)
    brain.feed()
    make_hungry(ctx)
    brain.tick(DT)
    assert isinstance(brain.state, Fly) and brain.state.onto == "food"
    run_until(brain, Eat, limit=20)


def test_held_he_eats_once_he_has_landed(ctx):
    brain = Brain(ctx, Idle())
    brain.feed()
    brain.grab(ctx.body.x, ctx.body.y - 30)
    brain.drag(ctx.body.x, ctx.body.y - 300)
    make_hungry(ctx)
    run(brain, 1)
    assert ctx.food.pile.seeds == SEEDS_PER_STACK  # can't reach them yet
    brain.release()
    assert isinstance(brain.state, Fall)
    run_until(brain, Eat, limit=15)


def test_hunger_waits_till_he_wakes(ctx, world):
    world.hour = 2
    brain = Brain(ctx, Sleep())
    brain.feed()
    make_hungry(ctx)
    run(brain, 5)
    assert isinstance(brain.state, Sleep)


# --- In the cage ---------------------------------------------------------------


def cage_him(ctx, brain):
    assert brain.catch_in(ctx.body.x - 40, ctx.body.y - 80, ctx.body.x + 40, ctx.body.y + 5)
    run(brain, 15)  # let the tantrum pass


def test_caged_his_seeds_go_in_the_dish_and_he_eats_a_stack_when_hungry(ctx):
    brain = Brain(ctx, Idle())
    cage_him(ctx, brain)
    brain.feed()
    brain.feed()
    assert ctx.cage.dish.stacks == 2 and ctx.food is None
    run(brain, 2)
    assert ctx.cage.dish.seeds == 2 * SEEDS_PER_STACK  # not hungry: saved
    make_hungry(ctx)
    brain.tick(DT)
    assert ctx.animator.clip_name == "front_eat"
    run(brain, SEEDS_PER_STACK * 1.2)
    assert ctx.cage.dish.seeds == SEEDS_PER_STACK
    assert not ctx.hunger.hungry
    assert isinstance(brain.state, Caged)


def test_caged_and_hungry_with_an_empty_dish_he_only_asks(ctx):
    brain = Brain(ctx, Idle())
    cage_him(ctx, brain)
    make_hungry(ctx)
    brain.tick(DT)
    assert isinstance(brain.state, Caged)  # can't come to you from in there
    assert ctx.speech.text in ctx.config.begging


def test_feeding_him_in_the_cage_counts_against_escaping(ctx):
    brain = Brain(ctx, Idle())
    cage_him(ctx, brain)
    brain.feed()
    brain.feed()
    assert ctx.cage.feedings == 2
