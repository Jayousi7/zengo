"""How close Zengo feels to you.

A level from 0 (grumpy) to 1 (devoted), starting in the middle. Petting,
feeding and letting him out of the cage raise it, as does simply having your
pointer near him; catching him, keeping him caged, ignoring his calls for food
and dropping him from high up lower it. Left alone it drifts slowly back to the
middle, so neither extreme sticks for ever. Every rate is in the config.

It also notices you coming back after being away (no input for a while), so he
can greet you.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zengo.behavior.context import Context
    from zengo.config import Config

SNUB_EVERY = 20.0
"""Grumpy, he ignores one poke, and at most one in this many seconds."""


@dataclass
class Bond:
    level: float = 0.5
    petting_left: float = -1.0
    """What petting can still add this hour (negative: not started yet)."""
    petting_refill: float = 0.0
    away: bool = False
    welcome_due: bool = False
    """You've just come back after being away: he means to greet you."""
    snub_in: float = 0.0
    near_for: float = 0.0

    def close(self, cfg: Config) -> bool:
        return self.level >= cfg.bond_close

    def grumpy(self, cfg: Config) -> bool:
        return self.level <= cfg.bond_grumpy

    def change(self, amount: float) -> None:
        self.level = min(1.0, max(0.0, self.level + amount))

    def update(self, ctx: Context, dt: float, *, caged: bool, petted: bool) -> None:
        cfg = ctx.config
        if self.petting_left < 0:
            self.petting_left = cfg.bond_petting_per_hour
        # The petting allowance refills over the hour.
        self.petting_left = min(
            cfg.bond_petting_per_hour, self.petting_left + cfg.bond_petting_per_hour * dt / 3600
        )
        if petted:
            gain = min(self.petting_left, cfg.bond_petting * dt)
            self.petting_left -= gain
            self.change(gain)
        if caged:
            self.change(-cfg.bond_caged * dt / 60)
        elif self._pointer_near(ctx):
            self.change(cfg.bond_company * dt / 60)
        # A slow drift back towards the middle.
        drift = cfg.bond_drift * dt / 3600
        self.level += max(-drift, min(drift, 0.5 - self.level))
        self.snub_in = max(0.0, self.snub_in - dt)

        idle = ctx.world.input_idle_seconds()
        if idle is not None:
            if idle >= cfg.away_for:
                self.away = True
            elif self.away and idle < 1.0:
                self.away, self.welcome_due = False, True

    def _pointer_near(self, ctx: Context) -> bool:
        cx, cy = ctx.world.cursor()
        reach = ctx.config.px(ctx.config.watch_radius)
        return abs(cx - ctx.body.x) < reach and abs(cy - ctx.body.y) < 2 * reach

    # --- Things that happen to him --------------------------------------------

    def fed(self, cfg: Config, *, hungry: bool) -> None:
        self.change(cfg.bond_fed_hungry if hungry else cfg.bond_fed)

    def let_out(self, cfg: Config) -> None:
        self.change(cfg.bond_let_out)

    def caught(self, cfg: Config) -> None:
        self.change(-cfg.bond_caught)

    def ignored(self, cfg: Config) -> None:
        self.change(-cfg.bond_ignored)

    def dropped(self, cfg: Config) -> None:
        self.change(-cfg.bond_dropped)

    def snubs(self, cfg: Config) -> bool:
        """Grumpy enough to ignore this poke? (At most one every SNUB_EVERY seconds.)"""
        if not self.grumpy(cfg) or self.snub_in > 0:
            return False
        self.snub_in = SNUB_EVERY
        return True
