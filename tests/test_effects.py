import random

from zengo.behavior.effects import LIFE, MAX_PARTICLES, Effects, Particle


def _run(effects, seconds, dt=1 / 30, scale=2):
    for _ in range(round(seconds / dt)):
        effects.update(dt, scale)


def test_droplets_fly_up_then_fall_to_the_ground_and_go():
    effects = Effects()
    effects.splash(100, 500, 520, random.Random(1), scale=2)
    assert len(effects.particles) == 6
    _run(effects, 0.1)
    assert all(p.y < 500 for p in effects.particles)  # thrown upwards first
    _run(effects, 0.4)
    assert any(p.landed is not None and p.y == 520 for p in effects.particles)
    _run(effects, LIFE["drop"] + 1)
    assert effects.particles == []


def test_snow_drifts_down_swaying_and_fades_once_landed():
    effects = Effects()
    effects.falling("snow", 300, 100, 400, random.Random(2))
    xs = []
    for _ in range(60):
        effects.update(1 / 30, 2)
        xs.append(effects.particles[0].x)
    flake = effects.particles[0]
    assert 100 < flake.y < 400
    assert max(xs) - min(xs) > 4  # swaying, not falling straight
    _run(effects, 20)
    assert effects.particles == [] or effects.particles[0].landed is not None


def test_a_leaf_tips_back_and_forth_as_it_falls():
    effects = Effects()
    effects.falling("leaf", 300, 100, 2000, random.Random(3))
    tilts = set()
    for _ in range(90):
        effects.update(1 / 30, 2)
        tilts.add(effects.particles[0].tilt)
    assert tilts == {-1, 0, 1}


def test_there_are_never_too_many():
    effects = Effects()
    for i in range(MAX_PARTICLES + 10):
        effects.add(Particle("snow", i, 0))
    assert len(effects.particles) == MAX_PARTICLES
    assert effects.particles[0].x == 10  # the oldest made way


def test_the_window_covers_just_the_particles_and_hides_without_them():
    from zengo.ui.effects_window import EffectsWindow

    window = EffectsWindow(2)
    window.show_particles([Particle("drop", 100, 100), Particle("snow", 300, 160)])
    assert window.isVisible()
    box = window.geometry()
    assert box.left() < 100 < 300 < box.right()
    assert box.width() < 220
    window.show_particles([])
    assert not window.isVisible()
    window.close()


def test_every_window_drawn_at_his_size_is_stacked_and_remade_on_resize(make_pet):
    pet = make_pet()
    layers = pet._layers()
    for window in pet._scaled_windows():
        assert window in layers
    # The droplets and the rest go in front of him and his cage, behind his cloud.
    assert layers.index(pet._window) < layers.index(pet._effects) < layers.index(pet._bubble)
    assert layers.index(pet._cage) < layers.index(pet._effects)
    old = pet._effects
    pet.change_settings(pet.settings.__class__(scale=3))
    assert pet._effects is not old
    assert pet._effects in pet._layers()


def test_the_bath_dish_stands_in_front_of_him(make_pet):
    pet = make_pet()
    layers = pet._layers()
    assert layers.index(pet._window) < layers.index(pet._bath)
