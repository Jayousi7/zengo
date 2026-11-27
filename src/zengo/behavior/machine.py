"""The state machine driving Zengo, and the entry point for user input."""

from __future__ import annotations

from zengo.behavior.context import Context
from zengo.behavior.states import Alert, Dragged, Fall, Idle, State


class Brain:
    def __init__(self, ctx: Context, initial: State | None = None) -> None:
        self.ctx = ctx
        self._grab_offset = (0.0, 0.0)
        self._state: State = initial or Idle()
        self._state.enter(ctx)

    @property
    def state(self) -> State:
        return self._state

    def transition(self, state: State) -> None:
        self._state = state
        state.enter(self.ctx)

    def tick(self, dt: float) -> None:
        self.ctx.animator.update(dt)
        if (following := self._state.update(self.ctx, dt)) is not None:
            self.transition(following)
        if self._state.grounded:
            self._settle()

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
        if not isinstance(self._state, Dragged | Fall):
            self.transition(Alert())

    def grab(self, x: float, y: float) -> None:
        """Mouse pressed on Zengo at screen ``(x, y)`` and started moving."""
        self._grab_offset = (self.ctx.body.x - x, self.ctx.body.y - y)
        self.transition(Dragged())

    def drag(self, x: float, y: float) -> None:
        if isinstance(self._state, Dragged):
            dx, dy = self._grab_offset
            self.ctx.body.x, self.ctx.body.y = x + dx, y + dy
            self.ctx.body.face_towards(x)

    def release(self) -> None:
        if isinstance(self._state, Dragged):
            self.transition(Fall())
