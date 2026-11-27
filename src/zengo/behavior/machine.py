"""The state machine driving Zengo, and the entry point for user input."""

from __future__ import annotations

from zengo.behavior.cage import BELOW_FLOOR, Cage, caught_in
from zengo.behavior.context import Context
from zengo.behavior.food import PECK_REACH, Food
from zengo.behavior.states import Caged, Dragged, Fall, Idle, State


class Brain:
    def __init__(self, ctx: Context, initial: State | None = None) -> None:
        self.ctx = ctx
        self._grab_offset = (0.0, 0.0)
        self._state: State = initial or Idle()
        self._state.enter(ctx)
        self._facing = ctx.body.facing

    @property
    def state(self) -> State:
        return self._state

    def transition(self, state: State) -> None:
        self._state = state
        state.enter(self.ctx)

    def tick(self, dt: float) -> None:
        ctx = self.ctx
        ctx.animator.update(dt)
        ctx.scenery.update(ctx, dt, occupied=self._state.holds_branch)
        if ctx.speech is not None:
            ctx.speech.remaining -= dt
            if ctx.speech.remaining <= 0:
                ctx.speech = None
        if ctx.cage is not None:
            ctx.cage.update(ctx, dt)
            if ctx.cage.empty_for > 1.5:  # he's out: the cage goes
                ctx.cage = None
        ctx.petting.update(ctx, dt)
        if ctx.petting.active and (following := self._state.petted(ctx)) is not None:
            self.transition(following)
        if (following := self._state.update(ctx, dt)) is not None:
            self.transition(following)
        self._mind_the_food()
        if self._state.grounded:
            self._settle()
            if ctx.body.facing is not self._facing:
                # Turning round on the ground: a glimpse of his front, not a flip.
                ctx.animator.interject("ground_turn")
        self._facing = ctx.body.facing

    def _mind_the_food(self) -> None:
        """Seeds in the cage go where the cage goes; seeds on the ground draw him."""
        ctx, food = self.ctx, self.ctx.food
        if food is None:
            return
        if food.in_cage:
            if ctx.cage is None or ctx.cage.door_open:
                ctx.food = None  # out with the tray
            else:
                food.x, food.y = ctx.cage.shown_x, ctx.cage.y
        elif (following := self._state.food_nearby(ctx)) is not None:
            self.transition(following)

    def _settle(self) -> None:
        """Keep a grounded pet on the ground line and on-screen.

        Handles the desktop changing underneath Zengo: panels resizing, screens
        being unplugged, resolution changes.
        """
        body, area = self.ctx.body, self.ctx.area()
        body.y = area.bottom
        body.x = area.clamp_x(body.x, self.ctx.margin)

    # --- Input -------------------------------------------------------------

    def click(self) -> None:
        """A poke: what it does depends on what he's doing (see :meth:`State.clicked`)."""
        if (following := self._state.clicked(self.ctx)) is not None:
            self.transition(following)

    def double_click(self) -> None:
        """Double-clicked: a whistle, when he's settled (see :meth:`State.double_clicked`)."""
        if (following := self._state.double_clicked(self.ctx)) is not None:
            self.transition(following)

    @property
    def caged(self) -> bool:
        return isinstance(self._state, Caged)

    def catch_in(self, left: float, top: float, right: float, bottom: float) -> bool:
        """A box was drawn on screen. If it takes him in, he's caged where he is: on
        the ground, or the cage drops there. Miss him and he lets you know."""
        ctx = self.ctx
        if self.caged or isinstance(self._state, Dragged):
            return False
        if not caught_in(ctx, left, top, right, bottom):
            ctx.say("missed! hehe", 2.0)
            return False
        area = ctx.area()
        ctx.cage = Cage(x=area.clamp_x(ctx.body.x, ctx.config.px(16)), y=ctx.body.y)
        if ctx.body.y >= area.bottom - 1:  # caught on the ground: the cage stands there
            ctx.cage.mount = "ground"
            ctx.cage.y = area.bottom - ctx.config.px(BELOW_FLOOR)
        self.transition(Caged())
        return True

    def feed(self) -> None:
        """Put down sunflower seeds: in front of him, or on his tray if he's caged.
        More seeds while there are some left just tops the pile up."""
        ctx, cfg = self.ctx, self.ctx.config
        if ctx.food is not None:
            ctx.food = Food(ctx.food.x, ctx.food.y, in_cage=ctx.food.in_cage)
        elif ctx.cage is not None and not ctx.cage.door_open:
            ctx.food = Food(ctx.cage.shown_x, ctx.cage.y, in_cage=True)
        else:
            area, reach = ctx.area(), cfg.px(PECK_REACH)
            x = ctx.body.x + int(ctx.body.facing) * cfg.px(45)
            lo, hi = area.left + ctx.margin + reach, area.right - ctx.margin - reach
            ctx.food = Food(min(max(x, lo), hi), area.bottom)
        ctx.say("seeds!! ♥", 1.6, mood="love")

    def let_out(self) -> None:
        """Open the cage door; he flies out and the cage goes."""
        if self.ctx.cage is not None:
            self.ctx.cage.door_open = True

    def cage_grab(self, x: float, y: float) -> None:
        if self.ctx.cage is not None and not self.ctx.cage.door_open:
            self.ctx.cage.grab(x, y)

    def cage_drag(self, x: float, y: float) -> None:
        if self.ctx.cage is not None:
            self.ctx.cage.drag(x, y)

    def cage_release(self) -> None:
        if self.ctx.cage is not None:
            self.ctx.cage.release(self.ctx)

    def grab(self, x: float, y: float) -> None:
        """Mouse pressed on Zengo at screen ``(x, y)`` and started moving."""
        if self.caged:
            return  # behind bars: the cage is what gets dragged
        body = self.ctx.body
        self._grab_offset = (body.x - x, body.y - y)
        self.transition(Dragged(target=(body.x, body.y)))

    def drag(self, x: float, y: float) -> None:
        if isinstance(self._state, Dragged):
            dx, dy = self._grab_offset
            self._state.target = (x + dx, y + dy)

    def release(self) -> None:
        """Let go: he keeps the speed the drag gave him (see :class:`Fall`)."""
        if isinstance(self._state, Dragged):
            self.transition(Fall())
