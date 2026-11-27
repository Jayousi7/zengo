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
