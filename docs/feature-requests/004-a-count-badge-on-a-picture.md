# Feature request 004: a count badge on a picture

Requested 2026-11-13 by vichnimon, for its inventory's stacks (vichnimon plan 029, *Stacks of items*). Status:
proposed; not started. Until it is in, vichnimon draws the number itself over the box's `rect` after the screen draws.

## Why

An inventory box shows a stack of things (logs: one box, "7" in its corner), as games do. `Picture` cannot say a
number over its texture: its `caption` is written only while it has no texture (an empty slot's name), and its
`tooltip` needs the mouse. The app can draw over the box from outside, reading `Picture.rect` after the layout, but it
then has to follow the picture through a drag (the dragged texture follows the mouse, the box shows empty), the
window's dimming under a modal, and the theme's colours and font, all of which the picture already knows.

## Proposal

`Picture(badge: str = "")`: a short text drawn in the box's bottom right corner, over the texture.

- In the theme's small text size (`SMALL`), the theme's text colour on a rounded dark plate (the theme's background
  at about 70% alpha) inset a few pixels from the corner, so it reads over any texture.
- Drawn only with a texture (an empty box has its `caption`); `""` draws nothing.
- While the picture is dragged, the badge travels with the texture under the mouse and the box shows empty, as now.
- Under a modal window the badge dims with the rest of the screen.
- `tint` does not tint the badge.

### In the demo

The pictures scene gets a grid box with a badge ("7", "128"), with a screenshot.

## Not asked for

- Badges in the other corners, icons in badges, a badge on other widgets.
