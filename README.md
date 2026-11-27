# Zengo

A desktop pet of Zengo, a cinnamon white-face cockatiel. Pixel art, Windows and Linux.

Zengo perches on the bottom edge of the screen (above the taskbar), idles and
blinks, waddles about, preens, flies to other spots, watches and follows the
cursor, and falls asleep when you're away or late at night.

| Input | Reaction |
|---|---|
| Left click | Crest up, startled |
| Left drag | Picked up, flutters; let go and Zengo flutters down |
| Right click | Menu with *Quit Zengo* |

## Run

```sh
python -m venv .venv
.venv/bin/pip install -e '.[dev]'      # Windows: .venv\Scripts\pip
.venv/bin/zengo                         # or: python -m zengo
.venv/bin/zengo --scale 3               # bigger bird
.venv/bin/zengo --sprites art.json      # use hand-drawn frames (see below)
```

Requires Python 3.11+. On Linux, Qt's X11 plugin needs `libxcb-cursor0`
(`sudo apt install libxcb-cursor0` on Debian/Ubuntu/Mint), including for the
built binary. X11 is fully supported. Under Wayland, Qt
cannot place windows at absolute positions, so force XWayland:
`QT_QPA_PLATFORM=xcb zengo`.

## Build a standalone executable

```sh
python scripts/build.py    # -> dist/zengo (Linux) or dist/zengo.exe (Windows)
```

PyInstaller does not cross-compile; build on each target OS.

## Develop

```sh
pytest
ruff check . && ruff format --check .
python scripts/preview_sprites.py sprites.png   # contact sheet of every frame
```

### Layout

```
src/zengo/
  app.py            composition root and frame loop
  config.py         tunables (speeds, timings, scale)
  animation.py      Clip and Animator: frame timing, no rendering
  world.py          World protocol: what the pet can observe
  behavior/
    body.py         position and facing
    context.py      what states may read and mutate
    states.py       one class per behaviour
    machine.py      Brain: runs states, routes mouse input
  sprites/
    palette.py      Zengo's colours
    art.py          ASCII pixel-art layers
    compose.py      layers -> RGBA frames, generated outline
    frames.py       named frames and canvas geometry
    clips.py        animation catalogue
  ui/
    qt_world.py     World backed by Qt screens and cursor
    sprites.py      frames -> scaled, mirrored pixmaps and click masks
    window.py       translucent always-on-top window, gestures
    sheet_loader.py Aseprite JSON + PNG -> frames
```

Only `ui/` and `app.py` import Qt. Everything else is plain Python and is
tested headless against a fake `World`.

### Editing the art

Frames are text in `sprites/art.py`, drawn facing right on a 26x28 grid. Each
character is a palette key from `sprites/palette.py`; `.` leaves the pixel
below untouched and `_` erases it. Don't draw outlines: they are generated,
each edge taking a dark shade of the colour it borders.

Perched poses are the base drawing (`BODY`, `HEAD`, `CREST`, `LEGS`) plus small
overlays: a shifted head, another crest, closed eyes. Flight reuses the head on
a forward-leaning body with a wing in one of four beat positions (up, level,
down, recover); the glide holds the wing level and the landing flares it up. `frames.py` stacks
layers into named frames and `clips.py` sequences them. `tests/test_sprites.py`
checks that frames line up with the ground row and that every clip refers to a
real frame.

### Hand-drawn frames

Any frame can be replaced by art from a pixel editor. In Aseprite (or
LibreSprite), draw on a 28x30 canvas facing right, with the feet's lowest
pixel on row 25 and the gap between the feet on column 20 (zero-based). Name
each frame after the one it replaces (`perch`, `blink`, `alert`, `step_back`,
`step_front`, `preen_a`, `preen_b`, `sleep`, `wings_up`, `wings_level`,
`wings_down`, `wings_recover`) and export a sprite sheet with JSON data, hash or array layout.
Frames not in the sheet keep the built-in art. Run with
`zengo --sprites sheet.json`. Draw your own outline here; generated outlines
only apply to the built-in art.

### Adding a behaviour

Subclass `State` in `behavior/states.py`: set `clip`, override `enter` and/or
`step`, and return the next state from `step` when done. Add it to the weights
in `choose_activity`.
