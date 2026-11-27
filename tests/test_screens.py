"""More than one screen: finding them, losing one, flying between them."""

from zengo.behavior.cage import Cage
from zengo.behavior.food import Food
from zengo.behavior.machine import Brain
from zengo.behavior.states import Away, Caged, Fly, Idle
from zengo.world import Area, nearest, neighbours

LEFT = Area(0, 0, 1920, 1040)
RIGHT = Area(1920, 0, 3200, 1000)  # smaller, and its taskbar's taller
BELOW = Area(400, 1080, 1700, 1800)


def test_the_nearest_screen_for_a_point_on_none():
    assert nearest([LEFT, RIGHT], 100, 500) == LEFT
    assert nearest([LEFT, RIGHT], 5000, 500) == RIGHT
    assert nearest([LEFT, RIGHT], 1950, 1020) == RIGHT  # in the gap under RIGHT's panel


def test_neighbouring_screens_and_which_side_theyre_on():
    assert neighbours(LEFT, [LEFT, RIGHT, BELOW]) == [(RIGHT, "right"), (BELOW, "below")]
    assert neighbours(RIGHT, [LEFT, RIGHT]) == [(LEFT, "left")]
    far = Area(5000, 0, 6000, 1000)
    assert neighbours(LEFT, [LEFT, far]) == []


def _two_screens(ctx):
    ctx.world.screens = [LEFT, RIGHT]
    brain = Brain(ctx, Idle())
    brain.tick(0.05)  # he notices the screens as they are
    return brain


def test_unplugged_he_flies_in_to_the_screen_thats_left(ctx):
    brain = _two_screens(ctx)
    ctx.body.x, ctx.body.y = 2500.0, RIGHT.bottom
    ctx.food = Food(2600.0, RIGHT.bottom)
    ctx.food.pile.add_stack()
    ctx.moult.drop(ctx)
    ctx.world.screens = [LEFT]
    brain.tick(0.05)
    assert isinstance(brain.state, Fly)
    assert LEFT.contains(ctx.food.x, ctx.food.y - 1)
    assert ctx.moult.feathers == []
    for _ in range(400):
        brain.tick(0.05)
        if not isinstance(brain.state, Fly):
            break
    assert LEFT.contains(ctx.body.x, ctx.body.y - 4)
    assert ctx.body.y == LEFT.bottom


def test_unplugged_his_cage_comes_too_with_him_in_it(ctx):
    ctx.world.screens = [LEFT, RIGHT]
    ctx.body.x, ctx.body.y = 2500.0, RIGHT.bottom
    ctx.cage = Cage(x=2500.0, y=RIGHT.bottom - 40)
    ctx.cage.mount = "ground"
    brain = Brain(ctx, Caged(just_caught=False))
    brain.tick(0.05)
    ctx.world.screens = [LEFT]
    brain.tick(0.05)
    brain.tick(0.05)
    assert isinstance(brain.state, Caged)
    assert LEFT.contains(ctx.cage.x, ctx.cage.y - 8)
    assert LEFT.contains(ctx.body.x, ctx.body.y - 8)


def test_hidden_off_a_screen_thats_gone_he_comes_back_on_another(ctx):
    brain = _two_screens(ctx)
    brain.transition(Away(1, RIGHT))
    ctx.world.screens = [LEFT]
    brain.tick(0.05)
    brain.show()
    for _ in range(400):
        brain.tick(0.05)
        if not isinstance(brain.state, Fly):
            break
    assert LEFT.contains(ctx.body.x, ctx.body.y - 4)


def test_his_mirror_stays_on_its_own_screen(ctx):
    brain = _two_screens(ctx)
    ctx.toys.put_out(frozenset({"mirror"}))
    brain.tick(0.05)
    x = ctx.toys.mirror.x
    ctx.body.x, ctx.body.y = 2500.0, RIGHT.bottom  # he's gone over to the other one
    brain.tick(0.05)
    assert ctx.toys.mirror.x == x and LEFT.contains(x, ctx.toys.mirror.y - 1)


# --- Flying between screens ---------------------------------------------------------

from zengo.behavior.states import choose_activity, follow_you_over, perchable_ledges  # noqa: E402
from zengo.world import Ledge  # noqa: E402


def _fly(brain, ctx, seconds=30.0):
    path = []
    for _ in range(round(seconds / 0.05)):
        brain.tick(0.05)
        path.append((ctx.body.x, ctx.body.y))
        if not isinstance(brain.state, Fly):
            break
    return path


def test_he_flies_across_to_the_screen_next_door_where_they_meet(ctx):
    ctx.world.screens = [LEFT, RIGHT]
    ctx.body.x, ctx.body.y = 1500.0, LEFT.bottom
    brain = Brain(ctx, Fly.to_screen(ctx))
    path = _fly(brain, ctx)
    assert RIGHT.contains(ctx.body.x, ctx.body.y - 4) and ctx.body.y == RIGHT.bottom
    crossing = [y for x, y in path if 1900 <= x <= 1940]
    assert crossing and all(y < RIGHT.bottom for y in crossing)  # over the edge they share


def test_to_a_screen_below(ctx):
    ctx.world.screens = [LEFT, BELOW]
    ctx.body.x, ctx.body.y = 1000.0, LEFT.bottom
    brain = Brain(ctx, Fly.to_screen(ctx, BELOW))
    _fly(brain, ctx)
    assert BELOW.contains(ctx.body.x, ctx.body.y - 4) and ctx.body.y == BELOW.bottom


def test_with_one_screen_theres_nowhere_to_cross_to(ctx):
    from zengo.behavior.states import other_screens

    assert other_screens(ctx) == []


def test_window_tops_next_door_count(ctx):
    ctx.world.screens = [LEFT, RIGHT]
    ledge = Ledge(window=7, left=2200.0, right=2700.0, y=400.0, window_left=2200.0)
    ctx.world.windows_on_top = [ledge]
    assert perchable_ledges(ctx) == [ledge]
    brain = Brain(ctx, Fly.to_window(ctx))
    _fly(brain, ctx)
    assert type(brain.state).__name__ == "OnWindow"
    assert RIGHT.contains(ctx.body.x, ctx.body.y)


def test_devoted_he_follows_you_over(ctx):
    ctx.world.screens = [LEFT, RIGHT]
    ctx.world.cursor_pos = (2600.0, 500.0)
    ctx.bond.level = 0.95
    picks = [choose_activity(ctx) for _ in range(60)]
    assert sum(isinstance(p, Fly) for p in picks) >= 20
    brain = Brain(ctx, follow_you_over(ctx))
    _fly(brain, ctx)
    assert RIGHT.contains(ctx.body.x, ctx.body.y - 4)
    assert abs(ctx.body.x - 2600) < 300


def test_not_devoted_he_stays_put(ctx):
    ctx.world.screens = [LEFT, RIGHT]
    ctx.world.cursor_pos = (2600.0, 500.0)
    ctx.bond.level = 0.5
    ctx.rng.seed(5)
    flights = 0
    for _ in range(200):
        pick = choose_activity(ctx)
        if isinstance(pick, Fly) and pick.waypoints and pick.waypoints[-1][0] > 1920:
            flights += 1
    assert flights < 25  # only the odd crossing of his own accord
