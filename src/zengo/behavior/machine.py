"""The state machine driving Zengo, and the entry point for user input."""

from __future__ import annotations

from zengo.behavior.context import Context
from zengo.behavior.states import Dragged, Fall, Idle, State


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
        ctx.petting.update(ctx, dt)
        if ctx.petting.active and (following := self._state.petted(ctx)) is not None:
            self.transition(following)
        if (following := self._state.update(ctx, dt)) is not None:
            self.transition(following)
        if self._state.grounded:
            self._settle()
            if ctx.body.facing is not self._facing:
                # Turning round on the ground: a glimpse of his front, not a flip.
                ctx.animator.interject("ground_turn")
        self._facing = ctx.body.facing

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

    def grab(self, x: float, y: float) -> None:
        """Mouse pressed on Zengo at screen ``(x, y)`` and started moving."""
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
