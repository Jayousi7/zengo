"""The state machine driving Zengo, and the entry point for user input."""

from __future__ import annotations

from zengo.behavior.cage import BELOW_FLOOR, Cage, caught_in
from zengo.behavior.context import Context
from zengo.behavior.food import STAND_OFF, Food
from zengo.behavior.states import Caged, Dragged, Fall, Idle, State
from zengo.behavior.status import Status
from zengo.behavior.status import read as read_status


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
        ctx.typing.update(ctx, dt)
        if ctx.typing.active and (following := self._state.typing(ctx)) is not None:
            self.transition(following)
        if (following := self._state.update(ctx, dt)) is not None:
            self.transition(following)
        ctx.hunger.update(ctx, dt, self._state.effort)
        if ctx.food is not None:
            ctx.food.pile.update(dt)
        self._mind_the_food()
        if self._state.grounded:
            self._settle()
            if ctx.body.facing is not self._facing:
                # Turning round on the ground: a glimpse of his front, not a flip.
                ctx.animator.interject("ground_turn")
        self._facing = ctx.body.facing

    def _mind_the_food(self) -> None:
        """Hunger, and what he does about it given what he's up to."""
        ctx = self.ctx
        food = ctx.food
        if food is not None and food.pile.seeds <= 0 and food.pile.shown <= 0:
            ctx.food = food = None  # all eaten
        if not ctx.hunger.hungry:
            return
        following = None
        if food is not None and food.pile.seeds > 0:
            following = self._state.go_eat(ctx)
        elif ctx.hunger.wants_to_ask:
            following = self._state.ask_for_food(ctx)
            if following is not None:
                ctx.hunger.asked(ctx)
        if following is not None:
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

    def resume(self) -> None:
        """Pick up where things were left, after his memory has been restored: back
        in his cage if he was caged, otherwise just settled where he is."""
        if self.ctx.cage is not None and not self.caged:
            self.transition(Caged(just_caught=False))

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

    def feed(self) -> bool:
        """Pour out a stack of sunflower seeds: in front of him, or into his dish if
        he's caged (which puts him off escaping a little). At most three stacks:
        False, and a word from him, if there's no room for more."""
        ctx, cfg = self.ctx, self.ctx.config
        cage = ctx.cage
        if cage is not None and not cage.door_open:
            added = cage.dish.add_stack()
            if added:
                ctx.escape.feedings += 1
        else:
            if ctx.food is None:
                area, reach = ctx.area(), cfg.px(STAND_OFF)
                x = ctx.body.x + int(ctx.body.facing) * cfg.px(45)
                lo, hi = area.left + ctx.margin + reach, area.right - ctx.margin - reach
                ctx.food = Food(min(max(x, lo), hi), area.bottom)
            added = ctx.food.pile.add_stack()
        if not added:
            ctx.say("that's plenty! ♥", 1.8, mood="love")
        elif ctx.hunger.hungry:
            ctx.say("seeds!! ♥", 1.6, mood="love")
        else:
            ctx.say("for later! ♥", 1.6, mood="love")
        return added

    def status(self) -> Status:
        """His needs, for showing: fullness, hunger odds, seeds, escape odds."""
        return read_status(self.ctx, self.food_stacks)

    @property
    def food_stacks(self) -> int:
        """Stacks of seeds out for him where he'd eat them now: his dish, or the pile."""
        ctx = self.ctx
        if ctx.cage is not None and not ctx.cage.door_open:
            return ctx.cage.dish.stacks
        return ctx.food.pile.stacks if ctx.food is not None else 0

    def let_out(self) -> None:
        """Open the cage door; he flies out and the cage goes."""
        if self.ctx.cage is not None:
            self.ctx.cage.door_open = True

    def cage_grab(self, x: float, y: float) -> None:
        self.ctx.petting.suppress()
        if self.ctx.cage is not None and not self.ctx.cage.door_open:
            self.ctx.cage.grab(x, y)

    def cage_drag(self, x: float, y: float) -> None:
        self.ctx.petting.suppress()
        if self.ctx.cage is not None:
            self.ctx.cage.drag(x, y, self.ctx)

    def cage_release(self) -> None:
        self.ctx.petting.suppress()
        if self.ctx.cage is not None:
            self.ctx.cage.release(self.ctx)

    def grab(self, x: float, y: float) -> None:
        """Mouse pressed on Zengo at screen ``(x, y)`` and started moving."""
        if self.caged:
            return  # behind bars: the cage is what gets dragged
        self.ctx.petting.suppress()
        body = self.ctx.body
        self._grab_offset = (body.x - x, body.y - y)
        self.transition(Dragged(target=(body.x, body.y)))

    def drag(self, x: float, y: float) -> None:
        if isinstance(self._state, Dragged):
            self.ctx.petting.suppress()
            dx, dy = self._grab_offset
            self._state.target = (x + dx, y + dy)

    def release(self) -> None:
        """Let go: he keeps the speed the drag gave him (see :class:`Fall`)."""
        if isinstance(self._state, Dragged):
            self.ctx.petting.suppress()
            self.transition(Fall())
