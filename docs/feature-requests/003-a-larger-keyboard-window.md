# Feature request 003: a larger keyboard window, and larger text over part of a screen

Requested 2026-11-13 by vichnimon, for the player's name on its character creation screen (vichnimon plan 016,
*The simplified screen*). Status: proposed; not started.

## Why

`KeyboardWindow` is sized for a desktop: 40 px keys with 16 px labels, a 32 px typed line. Played with a pad from a
sofa, on a TV, it is small: vichnimon wants it twice the size, keys and their labels alike. The game cannot do it
itself:

- the key side is a module constant (`keyboard_window.KEY`), the typed line's size another (`LINE`), and the bottom
  row's heights use `KEY`; changing them means overriding the private `_build`;
- `Button` has no text size, so even with 80 px keys the labels would stay 16 px, small in a large key.

## Proposal

### 1. `Button(size=...)`

An optional text size, as `Label` has (`size: int | None = None`: the theme's `TEXT` when None). The button sized to
its text (no `width`) measures with it. The font is drawn on a 16 px grid, so 32 stays crisp.

### 2. `KeyboardWindow(..., scale: float = 1.0)`

Everything the window lays out, times `scale`:

| part | at 1 | at 2 |
| :--- | :--- | :--- |
| a key's side (`KEY`) | 40 | 80 |
| a key's label (`Button.size`) | `TEXT` 16 | 32 |
| the typed line (`LINE`) | 32 | 64 |
| the count (`5 / 16`) | `SMALL` 14 | 28 |
| the bottom row's heights (Shift, Space, Backspace, OK) and their labels | 40, 16 | 80, 32 |
| the Shift and Backspace icons | 1 x raygui's icon scale | 2 x |

- Labels round to whole multiples of the font's grid where `scale` makes them fractional (or the docstring says to use
  whole or half scales).
- The gaps between keys can stay as they are (`GAP`), or scale too: whichever looks right in the demo.
- The window is centred as now; at a scale too large for the screen it shrinks to fit (or the docstring says it is
  the app's to choose a scale that fits).
- The title bar can stay at the theme's size.

### 3. In the demo

The *Keyboard* scene gets a scale toggle (1 and 2), with a screenshot of each.

### 4. Larger text over part of a screen: `text_scale` on a container

vichnimon's creation screen wants its options pane (the right half: name box, choosers, swatches, sliders, the
expression toggles, the Appearance and Outfit tabs) in larger text, and the rest of the game's screens as they are.
Today only `Label` takes a size. `Button`, `Toggle`, `Slider` (its value text), `TextBox` and the tabs draw at
raygui's one `TEXT_SIZE` (`Theme.text`, set once for every screen), and rows are a fixed `ROW` (26 px), so neither a
per-widget size nor raising `Theme.text` gets there: the first is not there, the second enlarges every screen and
overflows the rows.

Proposal: `Column` and `Row` (or any container) take `text_scale: float | None = None`, inherited by everything
under them until a container sets its own:

- **Text**: a `Label`'s size and a widget's raygui text size are their usual size times the scale in force (`TEXT`
  16 -> 24 at 1.5, 32 at 2; `SMALL` likewise). raygui's `TEXT_SIZE` (and the font, `Theme.font(size)`) are set
  around each widget drawn under a scale and put back after, so the rest of the screen is untouched.
- **Rows**: the default heights grow with it (`ROW`, `CHECK`, a slider's and a text box's height), so the text fits;
  a height given explicitly stays as given. Widths sized to their text (`MIN_BUTTON`, a button with no `width`)
  measure at the scaled size.
- **Icons**: raygui's icon scale times the scale, as for the keyboard's Shift and Backspace.
- **Measuring**: `measure` and `arrange` read the scale in force, so a `Scroll` of scaled content scrolls the right
  height and the pad's `into_view` still works.
- **Navigation**: unchanged (it works on the arranged rects).
- A per-widget `size=` (section 1's, on `Button`, and on `Toggle`, `Slider`, `TextBox` too) would then be the
  same machinery for one widget: a widget's own size wins over the scale in force.

The keyboard window's `scale` (section 2) can be built on it: its root a `Column(text_scale=scale)` with its keys
`KEY * scale`.

vichnimon's use: the options pane's `Column(..., text_scale=1.5)` (the value to be tried by eye).

## Tests (no window)

- `Button(size=32)` measures wider than at the default size when sized to its text.
- `KeyboardWindow(scale=2)`: a key's spec is 80 x 80 with label size 32, the typed line's size 64, the bottom row's
  heights 80; `scale=1` gives today's specs exactly.
- Navigation over the keys (including the row wrap and the moves of feature request 002) is unchanged at `scale=2`.
- A `Column(text_scale=2)` of a `Label`, a `Button`, a `Toggle`, a `Slider` and a `TextBox` measures each row about
  twice today's height and arranges them without overlap; a sibling column without a scale arranges as today.
- A nested `text_scale` replaces the outer one; a widget's own `size` wins over both.
- A `Scroll` of scaled content reports the scaled content height (the focus scrolls into view as before).

## vichnimon's use

`KeyboardWindow(KEYBOARD, "Your name", name, max_length=16, box=NAME, scale=2.0)`, once released.
