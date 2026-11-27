"""Tunables. Distances and speeds are in art pixels so they hold at any scale."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    scale: int = 2
    """Screen pixels per art pixel."""

    fps: int = 30

    fly_speed: float = 150.0
    gravity: float = 500.0
    max_fall_speed: float = 140.0
    """Fluttering caps the fall speed; Zengo never drops like a stone."""

    drag_stiffness: float = 140.0
    """Spring constant (1/s²) pulling a held Zengo towards the cursor. With gravity
    it lets him sag a few pixels and swing as he is moved."""

    drag_damping: float = 12.0
    """Damping (1/s) on that spring: low enough to swing, high enough to settle."""

    struggle_speed: float = 120.0
    """Moved faster than this while held, Zengo flaps in protest."""

    max_throw_speed: float = 400.0
    """Fastest a throw can send him; a wild fling of the mouse shouldn't turn him into a missile."""

    air_drag: float = 1.5
    """Rate (1/s) at which a thrown Zengo loses horizontal speed."""

    glide_speed: float = 120.0
    """Speed of the glide that brings him down after being dropped or thrown."""

    idle_seconds: tuple[float, float] = (3.0, 9.0)
    """How long Zengo idles before choosing something else to do."""

    watch_radius: float = 140.0
    """Within this horizontal distance of the cursor, Zengo turns to look at it."""

    cursor_rest: tuple[float, float] = (2.0, 90.0)
    """Seconds the mouse must have rested (at least, at most) before Zengo may fly
    up to perch on the pointer. Past the upper bound you've probably left the desk."""

    cursor_reach: float = 400.0
    """Art pixels: how far away a resting pointer can be for him to fly over to it."""

    branch_every: tuple[float, float] = (600.0, 1200.0)
    """Seconds between one branch withdrawing and the next growing out."""

    branch_stays: tuple[float, float] = (180.0, 300.0)
    """Seconds a branch stays out if Zengo leaves it alone."""

    branch_linger: tuple[float, float] = (20.0, 40.0)
    """Seconds it stays after he leaves it, at least."""

    branch_grow_seconds: float = 1.2
    """Time to grow out from the edge, and to withdraw."""

    branch_height: tuple[float, float] = (0.25, 0.6)
    """Where it grows, as a share of the screen height from the top."""

    bath_every: tuple[float, float] = (1800.0, 5400.0)
    """Seconds between one bath dish going and the next appearing."""

    bath_stays: tuple[float, float] = (180.0, 300.0)
    """Seconds a dish stays out if he leaves it alone."""

    bath_fade_seconds: float = 1.5
    """Time for a dish to fade in, and out."""

    moult_every: tuple[float, float] = (3600.0, 7200.0)
    """Seconds between feathers falling (less in spring and autumn, and on moulting days)."""

    toy_every: tuple[float, float] = (60.0, 180.0)
    """Seconds, at least, between one game with a toy and the next."""

    damp_seconds: float = 60.0
    """How long he's damp after a bath: he won't fly till he's dry."""

    branch_visit: tuple[float, float] = (40.0, 150.0)
    """Seconds Zengo sits on the branch before flying off."""

    chirp_every: float = 50.0
    """Pottering about, he chirps on average once in this many seconds."""

    speech_seconds: float = 2.6
    """How long a whistle's cloud stays up."""

    cage_hang_reach: float = 60.0
    """Let the cage go with its top within this many art px of the top of the screen
    and it hangs from a chain."""

    cage_shelf_reach: float = 40.0
    """...or with a side this close to a side edge, and it goes on a shelf there."""

    cage_min_chain: float = 8.0
    """Shortest chain, in art px, between the top of the screen and the cage's hook."""

    cage_swing_stiffness: float = 9.0
    cage_swing_damping: float = 1.2
    """How a hung cage swings (1/s², 1/s): a few slow swings, then it's still."""

    complaint_every: tuple[float, float] = (4.5, 7.0)
    complaint_seconds: float = 2.5
    """While he's angry: seconds between complaints, and how long each cloud stays up.
    Clearly apart, so each one can be read."""

    escape_after: float = 300.0
    escape_every: float = 60.0
    escape_chance: float = 0.15
    escape_chance_rise: float = 0.01
    escape_feed_penalty: float = 0.03
    """Caged, after ``escape_after`` seconds he tries to escape every ``escape_every``:
    ``escape_chance`` at the first try, ``escape_chance_rise`` more each try after,
    less ``escape_feed_penalty`` for every time he's been fed in the cage, all
    times ``1 - bond``: a devoted bird hardly tries."""

    hunger_drain: float = 0.06
    """Share of a full stomach used up a minute at rest. Activity multiplies it (see
    ``State.effort``): from full, about 5 minutes resting to peckish, 17 to empty."""

    hunger_check_every: float = 30.0
    peckish_below: float = 0.7
    """Every ``hunger_check_every`` seconds he may get hungry: never above
    ``peckish_below`` full, then likelier the emptier he is, certain at empty."""

    seed_fill: float = 0.06
    """How much fuller each seed makes him: a stack of eight, about half a stomach."""

    nag_every: float = 120.0
    """Hungry with nothing to eat, how often he asks you for food."""

    # --- Bond: how close he feels to you, 0 to 1 (see behavior.bond) -----------
    # Earned slowly: an attentive owner (a couple of minutes' petting an hour, the
    # pointer nearby, feeding him when he's hungry) gets him devoted in about four
    # days; casual care levels off just short of it; caging him an hour a day
    # undoes it; neglect sours him within days.
    bond_petting: float = 0.002
    """Gained per second of petting..."""
    bond_petting_per_hour: float = 0.012
    """...up to this much an hour, so it can't be farmed."""
    bond_fed: float = 0.006
    bond_fed_hungry: float = 0.012
    """Gained for a stack of seeds, and for one when he was hungry."""
    bond_let_out: float = 0.02
    bond_company: float = 0.0003
    """Gained per minute with your pointer near him, while he's free."""
    bond_caught: float = 0.12
    bond_caged: float = 0.002
    """Lost when caught in the cage, and per minute spent in it."""
    bond_toy: float = 0.004
    bond_toy_per_hour: float = 0.012
    """Gained each time he plays with a toy you gave him, up to so much an hour."""
    bond_ignored: float = 0.04
    """Lost each time he has to ask again for food."""
    bond_dropped: float = 0.05
    drop_height: float = 120.0
    """Lost when let go of from higher than this (art px) above the ground."""
    bond_drift: float = 0.004
    """Per hour, how far he drifts back towards the middle when nothing happens."""
    bond_close: float = 0.8
    bond_grumpy: float = 0.3
    """Above ``bond_close`` he's devoted; below ``bond_grumpy``, grumpy."""
    away_for: float = 600.0
    """Seconds without any input that count as you being away; he greets you back."""

    window_visit: tuple[float, float] = (30.0, 120.0)
    """Seconds he sits on top of a window before flying off."""

    ledge_min_width: float = 40.0
    """Art px of a window's top edge he needs in view to land on it."""

    sleep_after: float = 300.0
    """Seconds of user inactivity after which Zengo becomes sleepy."""

    night: tuple[int, int] = (23, 6)
    """Local hours [start, end) during which Zengo naps readily, wrapping midnight."""

    dusk: tuple[int, int] = (21, 6)
    """Local hours [start, end) in which he's drawn dimmed, wrapping midnight."""

    edge_margin: float = 31.0
    """Art pixels kept between the anchor and a screen edge; the tail reaches this far back."""

    drag_threshold: int = 4
    """Screen pixels the mouse must move while pressed before a click becomes a drag."""

    def px(self, art_pixels: float) -> float:
        return art_pixels * self.scale

    def is_night(self, hour: int) -> bool:
        return _within(self.night, hour)

    def is_dusk(self, hour: int) -> bool:
        return _within(self.dusk, hour)


def _within(hours: tuple[int, int], hour: int) -> bool:
    start, end = hours
    return start <= hour or hour < end if start > end else start <= hour < end


def quick(config: Config) -> Config:
    """Timers shortened for trying things out: he escapes a cage within seconds,
    gets hungry ten times as fast, gets a bath every minute or so, and drops
    a feather twice a minute."""
    from dataclasses import replace

    return replace(
        config,
        escape_after=5.0,
        escape_every=5.0,
        escape_chance=1.0,
        hunger_drain=0.6,
        hunger_check_every=5.0,
        nag_every=20.0,
        bath_every=(30.0, 60.0),
        moult_every=(20.0, 40.0),
        damp_seconds=20.0,
    )
