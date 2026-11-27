"""The state machine driving Zengo, and the entry point for user input."""

from __future__ import annotations

from zengo.behavior.bond import Bond
from zengo.behavior.cage import BELOW_FLOOR, Cage, EscapeProgress, caught_in
from zengo.behavior.context import Context
from zengo.behavior.food import STAND_OFF, Food, Hunger
from zengo.behavior.states import (
    Alert,
    Away,
    Caged,
    Dragged,
    Fall,
    Fly,
    Follow,
    Idle,
    Listen,
    OnBranch,
    State,
    Walk,
    can_fly,
    cursor_is_inviting,
)
from zengo.behavior.status import Status
from zengo.behavior.status import read as read_status
from zengo.behavior.vocabulary import Lesson, Vocabulary
from zengo.sounds import CHIRPS
from zengo.sprites.looks import Look


class Brain:
    def __init__(self, ctx: Context, initial: State | None = None) -> None:
        self.ctx = ctx
        self._grab_offset = (0.0, 0.0)
        self._state: State = initial or Idle()
        self._state.enter(ctx)
        self._facing = ctx.body.facing
        self._asks = 0
        """Times he's asked for food since he got hungry."""
        self._welcome_wait = 0.0

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
        ctx.effects.update(dt, ctx.config.scale)
        ctx.bath.update(
            ctx, dt, occupied=self._state.holds_bath, free=not (self.caged or self.away)
        )
        ctx.damp = max(0.0, ctx.damp - dt)
        ctx.toys.update(ctx, dt, caged=self.caged, away=self.away, at_mirror=self._state.at_mirror)
        on_branch = isinstance(self._state, OnBranch)
        ctx.moult.update(ctx, dt, free=not (self.caged or self.away), on_branch=on_branch)
        ctx.weather.update(ctx, dt, on_branch=on_branch)
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
        ctx.bond.update(ctx, dt, caged=self.caged, petted=ctx.petting.active)
        self._welcome_back(dt)
        if ctx.food is not None:
            ctx.food.pile.update(dt)
        self._mind_the_food()
        self._maybe_chirp(dt)
        self._show_talking()
        if self._state.grounded:
            self._settle()
            if ctx.body.facing is not self._facing:
                # Turning round on the ground: a glimpse of his front, not a flip.
                ctx.animator.interject("ground_turn")
        self._facing = ctx.body.facing

    def _welcome_back(self, dt: float) -> None:
        """You're back after being away. Devoted, he flies to you with a song;
        grumpy, he gives you one look; otherwise a cheerful chirp. If he's busy
        (asleep, mid-flight), he gets round to it within half a minute."""
        ctx, cfg = self.ctx, self.ctx.config
        if ctx.bond.welcome_due:
            ctx.bond.welcome_due, self._welcome_wait = False, 30.0
        if self._welcome_wait <= 0:
            return
        self._welcome_wait -= dt
        if self.caged or not self._state.chirpy:
            return
        self._welcome_wait = 0.0
        if ctx.bond.grumpy(cfg):
            ctx.body.face_towards(ctx.world.cursor()[0])
            if self._state.grounded:
                self.transition(Alert())
            return
        if not ctx.bond.close(cfg):
            ctx.say("oh, hi! ♪", 1.8)
            ctx.play("chirp_a")
            return
        ctx.say(ctx.phrase("greeting"), 2.2, mood="love")
        ctx.play("greeting")
        if can_fly(ctx) and cursor_is_inviting(ctx):
            self.transition(Fly.to_cursor(ctx))
        elif self._state.grounded:
            self.transition(Follow())

    def _maybe_chirp(self, dt: float) -> None:
        """Now and then, pottering about, a little chirp: more often when he's
        devoted to you, less when he's grumpy."""
        ctx, cfg = self.ctx, self.ctx.config
        if not self._state.chirpy or ctx.speech is not None:
            return
        every = cfg.chirp_every * (
            0.6 if ctx.bond.close(cfg) else 2.0 if ctx.bond.grumpy(cfg) else 1.0
        )
        if ctx.season() == "spring":
            every *= 0.6  # full of song
        if ctx.rng.random() < dt / every:
            ctx.play(ctx.rng.choice(CHIRPS))
            ctx.say(ctx.phrase("random"), 1.4)

    def _show_talking(self) -> None:
        """He's just said one of your words: his beak works as he says it, if he's
        sitting side-on on the ground (other poses keep their own beaks)."""
        ctx = self.ctx
        if not ctx.talking:
            return
        ctx.talking = False
        clip = ctx.animator.clip_name
        side_on = not clip.startswith(("front_", "branch_", "back_", "ledge_"))
        if side_on and self._state.grounded and not isinstance(self._state, Listen):
            ctx.animator.interject("talk")

    def _mind_the_food(self) -> None:
        """Hunger, and what he does about it given what he's up to."""
        ctx = self.ctx
        food = ctx.food
        if food is not None and food.pile.seeds <= 0 and food.pile.shown <= 0:
            ctx.food = food = None  # all eaten
        if not ctx.hunger.hungry:
            self._asks = 0
            return
        following = None
        if food is not None and food.pile.seeds > 0:
            following = self._state.go_eat(ctx)
        elif ctx.hunger.wants_to_ask:
            following = self._state.ask_for_food(ctx)
            if following is not None:
                ctx.hunger.asked(ctx)
                self._asks += 1
                if self._asks > 1:  # you didn't answer last time
                    ctx.bond.ignored(ctx.config)
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
        """A poke: what it does depends on what he's doing (see :meth:`State.clicked`).
        Grumpy, he ignores the first one."""
        if not self.caged and self.ctx.bond.snubs(self.ctx.config):
            self.ctx.say("hmph", 1.2, mood="angry")
            return
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

    # --- From the tray ------------------------------------------------------------

    @property
    def away(self) -> bool:
        """Out of sight, sent off by Hide."""
        state = self._state
        return isinstance(state, Away) or (isinstance(state, Fly) and state.onto == "away")

    def can_hide(self) -> bool:
        """He flies off unless he's caged, being carried, or damp from his bath."""
        return not (
            self.caged or self.away or isinstance(self._state, Dragged) or not can_fly(self.ctx)
        )

    def hide(self) -> bool:
        if not can_fly(self.ctx) and not self.away:
            self.ctx.say("still drying off!", 1.8)
            return False
        if not self.can_hide():
            return False
        self.transition(Fly.away(self.ctx))
        return True

    def show(self) -> None:
        """Back in from the side he left by."""
        if isinstance(self._state, Away):
            self.transition(Fly.back(self.ctx, self._state))

    def summon(self) -> None:
        """Here I am! He flies to the middle of the screen (in his cage, he just calls)."""
        ctx = self.ctx
        if isinstance(self._state, Away):
            self.show()
        if self.caged or isinstance(self._state, Dragged):
            ctx.say("here I am! ♪", 2.0)
            ctx.play("chirp_a")
            return
        if isinstance(self._state, Fly) and self._state.onto == "away":
            return  # leaving: Show brings him back
        ctx.say("here I am! ♪", 2.0)
        ctx.play("chirp_a")
        area = ctx.area()
        middle = (area.left + area.right) / 2
        near = abs(ctx.body.x - middle) < ctx.config.px(30)
        on_ground = self._state.grounded and ctx.body.y >= area.bottom - 1
        if near and on_ground:
            return
        if not can_fly(ctx):
            # Damp: he can't fly, so he waddles over (or finishes his bath first).
            if on_ground:
                self.transition(Walk(middle))
            return
        self.transition(Fly.to_middle(ctx))

    # --- Lessons -------------------------------------------------------------------

    def can_learn(self) -> str | None:
        """Why he can't have a lesson right now, or ``None`` if he can."""
        if self.away:
            return "He's away. Show him first."
        if self.caged:
            return "Not while he's caged: let him out first."
        if isinstance(self._state, Listen):
            return "He's still on the last one."
        on_ground = self.ctx.body.y >= self.ctx.area().bottom - 1
        if not (self._state.grounded and on_ground):
            return "He's busy. Try again when he's settled on the ground."
        return None

    def lesson(self, text: str, moment: str) -> Lesson | None:
        """Teach him ``text`` (to say at ``moment`` once learned): he listens, then
        tries it. ``None`` if he can't now (see :meth:`can_learn`) or it's empty."""
        ctx = self.ctx
        if self.can_learn() is not None:
            return None
        lesson = ctx.vocabulary.teach(text, moment, ctx.clock(), ctx.words_needed(), ctx.rng)
        if lesson is not None:
            self.transition(Listen(lesson.said, lesson.learned))
        return lesson

    def forget(self) -> None:
        """Start over, as a new bird: his bond, hunger, seeds, cage, escape
        progress and the words you've taught him all back to how they are the
        first time he runs."""
        ctx = self.ctx
        ctx.bond, ctx.hunger, ctx.escape = Bond(), Hunger(), EscapeProgress()
        ctx.cage = ctx.food = ctx.speech = None
        ctx.vocabulary = Vocabulary()
        self._asks = 0
        self._welcome_wait = 0.0
        ctx.body.vx = ctx.body.vy = 0.0
        self.transition(Fall() if ctx.body.y < ctx.area().bottom - 1 else Idle())

    @property
    def look(self) -> Look:
        """How he looks just now: damp after a bath, wrapped up in winter, dimmed
        late in the evening (the last two only with seasons on)."""
        ctx = self.ctx
        season = ctx.season()
        return Look(
            damp=ctx.damp > 0,
            scarf=season == "winter",
            dim=season is not None and ctx.config.is_dusk(ctx.world.local_hour()),
        )

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
        ctx.bond.caught(ctx.config)
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
        if added:
            ctx.bond.fed(cfg, hungry=ctx.hunger.hungry)
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

    def pick_feather(self, index: int) -> None:
        """You clicked one of the feathers he's dropped: it goes."""
        self.ctx.moult.pick_up(index)

    def let_out(self) -> None:
        """Open the cage door; he flies out and the cage goes."""
        cage = self.ctx.cage
        if cage is not None and not cage.door_open:
            cage.door_open = True
            self.ctx.bond.let_out(self.ctx.config)

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
            ctx = self.ctx
            ctx.petting.suppress()
            if ctx.area().bottom - ctx.body.y > ctx.config.px(ctx.config.drop_height):
                ctx.bond.dropped(ctx.config)  # that was a long way down
            self.transition(Fall())
