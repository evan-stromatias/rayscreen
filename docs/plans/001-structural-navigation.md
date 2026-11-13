# Plan 001: moving the focus through the spec tree

Addresses [feature request 002](../feature-requests/002-left-and-right-keep-to-the-row.md). Written 2026-11-13.
Status: proposed; not started.

## Why

`navigation.step` sees only a flat list of focusable widgets and their rects (`focusables`), so it guesses rows and
columns from screen geometry: the distance that way plus `ACROSS_WEIGHT` times the sideways gap. On vichnimon's
character creation screen that guess fails. Right from a chooser's `<` lands on a swatch in the row below, not on
`>` in its own row, and right along a row of weighted toggles leaves the row once the window is wide (the table in
request 002).

The request proposes a geometric fix: for left and right, the widgets whose vertical span overlaps the focus's first.
That still guesses, and the tree already says what is a row and what is a column, because the app built it from
`Row`s and `Column`s. A vertical-overlap rule also has edge cases the tree does not: rows with no gap between them
touch, a tall widget overlaps several rows, and up and down keep the old problem (down from a `>` with no swatch
straight below it).

A rule that only asks "which `Row` is this widget in" is not enough either: in a `Row` of two `Column`s every widget
shares the `Row`, and right from the bottom-left button would tie between the two right-hand ones and go to the top
one. The question to ask the tree is which *child* of the container comes next.

## The rule

A move is handled by the focus's innermost container that moves that way, and bubbles outwards when that container
cannot take it, as console UIs do with focus groups:

| container | moves | how |
| :--- | :--- | :--- |
| `Row`, `Split` | left, right | to the next child that way that has anything focusable in it |
| `Column` | up, down | the same, down or up the column |
| `Grid`, `Table`, `Board` | all four | today's geometric scoring, among the container's own focusables only |
| `Panel`, `Scroll` | none | one child; the move passes through to the container outside |

1. Walk from the focus's innermost container outwards. The first container that moves the way asked and has a
   target that way decides.
2. When the target is a subtree (a `Column` inside a `Row`), the focus goes to the focusable in it nearest the current
   focus, by today's score (distance between the centres along the move plus `ACROSS_WEIGHT` times the sideways gap),
   with ties to the first in tree order.
3. When no container takes the move, today's `step` over every focusable decides, so the focus is never stuck where
   it can move today. At a real edge the focus stays, as now.

There is no wrapping: at a row's end the move leaves the row or stays. `KeyboardWindow` keeps its own wrap.

### What it does on the cases in request 002

- Right from `<`: its `Row` skips the `Label`, which takes no focus, and goes to `>`. The swatch rows are never
  considered.
- The expression toggles: their `Row` steps through them in order, at any window size.
- Right from a row's last widget: the `Row` has nothing further, the `Column` around it does not move right, and the
  move reaches the `Row` or `Split` that holds the panel beside it, landing on the nearest widget in that panel.
- Down from `>`, with no swatch under it: the `Row` does not move down, so the `Column` goes to its next child, the
  swatch row, and picks the nearest swatch. This also fixes the up/down case the request left alone.
- A `Row` of two `Column`s, right from the bottom-left button: the `Row` moves to the right `Column`, and the nearest
  widget there is the bottom-right one.
- `KeyboardWindow`: each line of keys is a `Row`, so left and right keep to the line (Shift to Space included).

## Data

`focusables` already walks the tree; it records where each widget sits in it. `navigation.Placed` gains:

```python
type Axis = Literal["row", "column", "free", "none"]

class Placed(NamedTuple):
    node: Focusable
    rect: Rect
    scroll: Scroll | None
    path: tuple[int, ...] = ()  # the child index at each level from the root
    axes: tuple[Axis, ...] = ()  # the kind of container at each level: Row/Split "row", Column "column",
                                 # Grid/Table/Board "free", Panel/Scroll "none"
```

A container is a prefix of `path`; its focusables are those whose `path` starts with it, and the child a widget is
in is the next index. `step` keeps its signature (`nodes`, `focused`, `move`), so `draw.py` and existing callers do
not change. Everything stays headless, and widget specs and the layout passes do not change.

Note: `specs.Placed` (a `Board` child) and `navigation.Placed` share a name; `navigation.py` does not import the
former, so nothing needs renaming, but the docstring should say which is meant.

## Steps

1. **`navigation.py`.** Add `Axis` and the two fields to `Placed`; have `focusables` fill them from `children`. Split
   `step` into named parts: the current geometric score as a helper (`_nearest(candidates, current, move)`), the walk
   up the containers, and the fallback. Update the module and `step` docstrings to describe the rule.
2. **`KeyboardWindow`.** Reduce `_along_row` to the wrap past a line's ends, leaving moves within a line to `step`.
   Keep it only if the wrap cannot be put more simply.
3. **Tests (`tests/test_navigation.py`, no window).**
   - A `<  label  >` row above and below a row of small swatches: right from `<` is `>`, left from `>` is `<`.
   - A row of weighted toggles arranged 2000 px wide with swatches and a slider around it: right and left walk the
     toggles in order.
   - Down from `>` with no swatch under it reaches the swatch row; up from it reaches the row above.
   - A `Row` of two `Column`s: right from the bottom-left is the bottom-right, left back again.
   - Right at a row's end goes into the panel beside it, to its nearest widget.
   - A `Grid` of thumbnails still moves spatially in all four directions.
   - A move that no container takes falls back to the geometric step; at an edge the focus stays.
   - The existing navigation and keyboard tests pass unchanged.
4. **Demo scene `nav`: a character creation form.** A `NavScreen` in `demo/screens.py`, laid out like vichnimon's
   creation screen (the screenshot this plan was written from), because that screen is where the bug was found. It
   is a `Column` of form lines, each a `Row` of a fixed-width `Label` and its control:

   | line | control |
   | :--- | :--- |
   | Name | a weighted `TextBox` (`keyboard=True`, as the `keyboard` scene's) |
   | Gender | a chooser: `Button("<")`, a weighted centred `Label` with the value, `Button(">")` |
   | Skin | a `Row` of eight small clickable `Picture` swatches, light to dark |
   | (rule) | a `Separator`, then a muted `Face` heading |
   | Eyes, Nose, Mouth | choosers, as Gender |
   | Eye spacing, Eye height, Eye size, Mouth height | weighted `Slider`s showing their value (`"{:.2f}"`) |
   | (text) | a muted `Try an expression (not saved)` label |
   | (no label) | a full-width `Row` of six weighted `Toggle`s: Neutral, Happy, Sad, Angry, Surprised, Blink |
   | (rule) | a `Separator`, then a muted `Hair` heading |
   | Hair | a chooser |
   | Colour | a `Row` of ten small clickable `Picture` swatches |

   - Swatches are solid-colour textures made in the demo (`rl.gen_image_color`, then `rl.load_texture_from_image`),
     unloaded when the screen is left through `_unload_screen`, as `GalleryScreen`'s are. A click picks the colour;
     the choosers step through a short list of values and wrap. The expression toggles are exclusive. None of it is
     saved: the scene exists to be moved through.
   - The swatch rows are what make the bug: in the old `step`, right from `<` lands on a swatch in the next line,
     about 40 px along, rather than on `>` at the far end. The full-width toggle row is the second case: its toggles
     grow with the window and the gaps between lines do not, so the wider the window, the sooner another line wins.
   - A muted line at the bottom shows where each move goes from the current focus
     (`gender.prev: ← gender.prev  → gender.next  ↑ name  ↓ skin.1`), worked out with `step(focusables(...))` against
     the arranged tree, so a screenshot checks itself without pressing keys.
   - The structural cases this form does not have (a `Row` of `Column`s, a `Grid`, a panel beside a row's end) are
     covered by the tests in step 3, not by this scene.
5. **Demo option `--focus ID`.** Sets the starting screen's `state.focused` before the first frame, for screenshots of
   a given focus. Then check the table of request 002 at each size:

   ```sh
   uv run rayscreen-demo --screen nav --focus gender.prev --size 1280,720 --screenshot out.png
   uv run rayscreen-demo --screen nav --focus eyes.prev --size 1280,720 --screenshot out.png
   uv run rayscreen-demo --screen nav --focus hair.prev --size 1280,720 --screenshot out.png
   uv run rayscreen-demo --screen nav --focus expression.sad --size 1920,1080 --screenshot out.png
   uv run rayscreen-demo --screen nav --focus expression.neutral --size 2560,1440 --screenshot out.png
   ```

6. **`README.md` and `AGENTS.md`.** Describe the navigation rule where navigation is described, and add the `nav`
   scene and `--focus` to the demo commands.

## Out of scope

The `esc_used` problem noted at the end of request 002 (`KeyboardWindow.navigate` consumes the pad's B without
marking `manager.esc_used`) is a separate fix in `draw.py` and should get its own request (003).

## Release

The PR changes how every move is chosen, not only left and right, so it is a `minor:` PR under the 0.x rules.

## Risks

- Trees whose structure does not match how they look (a `Row` of `Fill`s and absolutely sized children, deep
  wrappers) now follow the structure. The fallback keeps the focus from getting stuck, but the target may differ
  from today's; the demo scene and the existing screens should be checked by hand with the keys.
- Windows: each window's tree is navigated on its own, as now; nothing crosses from a window to the screen below.
