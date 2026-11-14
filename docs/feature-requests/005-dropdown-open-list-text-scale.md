# An open dropdown list that follows the `text_scale`

Against rayscreen v0.47.0.

## What the game needs

The game's option screens (Graphics, Gameplay, ...) are drawn under a `text_scale` (`WindowSettings.menu_text_scale`,
2 by default so a TV is readable from the sofa). The labels, buttons and the dropdowns' own buttons grow with it, but
a dropdown's **open list** stays at the theme's size: tiny text in thin rows under a large button. On a TV the choices
cannot be read, and the rows are hard to hit with the mouse.

This is the documented behaviour of `Dropdown` (`specs.py`): "Its text and default height (`ROW` when None) grow
with the `text_scale`; its open list stays at the theme's size." So it is a missing feature, not a bug.

## Steps

1. `uv run vichni`, Options, Graphics (menu text scale 2).
2. Click the Shadows dropdown.
3. Off / Low / Medium / High show at the theme's text size in `POPUP_ROW`-high rows, under a button twice that
   height.

## What it could look like

The open list draws its rows at the text size its dropdown was drawn at: rows as tall as the dropdown's button
(or `POPUP_ROW` scaled the same way), their text at that size, and the "..." row, the keys'/pad's focus ring and the
fit/cut computation using the same row height.

Where it could go:

- `draw.py` `_dropdown`: it already computes `size = self._size(spec)` (and has the button's height); store them on
  the `OpenList` when it opens (`state.py` `OpenList`, e.g. `text_size: int` and `row: float`).
- `_open_list_layout`: `fits` and `bounds` use that row height instead of `POPUP_ROW`.
- `_draw_choices`: take the row height and size; draw the buttons under `_text_at(theme, size)` and the "..." at that
  size. Context menus keep calling it with the theme's defaults.
- `_navigate_list`: the focus ring's `y` and height use the same row height.

A context menu under a `text_scale` would want the same, but the game does not need it yet.
