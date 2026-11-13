# Bugfix request 001: a titled panel's title runs into its content under a `text_scale`

Reported 2026-11-13 by vichnimon, from its character creation screen's options pane at `text_scale=2.0` (vichnimon
plan 016), on the `feature-request-keyboard-window-sizes` branch (feature request 003, section 4). Status: open.

## What happens

Under a `text_scale` above about 1.25, a titled `Panel`'s title overlaps the panel's first child. At 2.0 the lower part
of "Make your character" (the descender of the "y") is hidden under the tabs drawn just below it.

## Why

raygui's group box draws the title centred on the box's top line, so half the title is above the line and half is
below it:

- the half above is covered: `title_strip(panel, scale)` (`layout.py`) is `scaled(TEXT, scale) / 2`, so it grows with
  the scale;
- the half below is meant to fit inside the panel's `pad` (as `title_strip`'s docstring says), but `pad` is the
  fixed `PAD` (10) at every scale. At 1 the lower half is 8 and fits. At 2 it is 16, so 6 px of the title falls on
  the child, which `arrange` places at `rect.y + strip + node.pad`.

## To reproduce

```python
Column(children=[
    Panel(Column(children=[Button("a", "First"), Button("b", "Second")]), title="Make your character", weight=1.0),
], text_scale=2.0)
```

The title's descenders are drawn under "First" (a filled panel shows it best: `fill=True`).

![The same filled panel at text_scale 1, at 2, and at 2 with pad=16](001-panels.png)

Left to right: `text_scale` 1 (the title clears "First"), `text_scale` 2 (the bug: the lower part of "your
character" is under "First"), and `text_scale` 2 with `pad=16` (vichnimon's workaround). The middle panel, enlarged:

![The middle panel's title, enlarged: its lower part hidden under the button](001-zoom.png)

## Proposed fix

Keep the content clear of the title's lower half at any scale: in `arrange` (and `measure`) put a titled panel's
child at least half the scaled title below the box's top line, for example the top inset
`max(node.pad, scaled(TEXT, scale) / 2 + 2)`. The sides and the bottom keep `pad`. At a scale of 1 nothing moves,
because 10 already covers 8.

## Tests (no window)

- A titled `Panel` under `text_scale=2` arranges its child at least `scaled(TEXT, 2) / 2` below the box's top line
  (the top of the title strip plus the strip).
- At `text_scale=1` (and with no title) the child's rect is the same as today.

## vichnimon's workaround, to remove once fixed

`screens/character.py` gives the options panel `pad=PANE_PAD` (16) instead of the default `PAD`.
