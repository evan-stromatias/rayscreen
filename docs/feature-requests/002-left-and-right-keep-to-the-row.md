# Feature request 002: left and right keep to the focus's row

Requested 2026-11-13 by vichnimon, for its character creation screen (vichnimon plan 016, *The simplified screen*).
Status: proposed; not started.

## Why

`navigation.step` moves the focus to the nearest widget that way, scored as the distance that way plus
`ACROSS_WEIGHT` (2) times the sideways gap between the two widgets' edges. Moving left or right, a widget in another
row often wins over the next one in the focus's own row, because the row's next widget is far away and the other row is
only a row-height off:

- A `<  value  >` chooser (a `Button`, a weighted `Label`, a `Button`) above or below a row of small swatches: right
  from `<` goes to a swatch, about 40 px along and 30-60 px off, never to `>` 400 px along in the same row. This
  happens even two rows away: right from the Eyes row's `<` lands on a skin swatch above the Gender row.
- A row of weighted toggles (an expression row: Neutral, Happy, Sad, Angry, Surprised, Blink) in a wide window: right
  from Sad went to a hair-colour swatch further down at 1920 x 1080, and to a slider above at 2560 x 1440. The toggles
  grow with the window while the gaps between rows do not, so the further the next toggle, the likelier another row
  wins.

Measured on vichnimon's screen with rayscreen v0.43.0's `step` (the real tree, `arrange`d at each size):

| from | right goes to, 1280 x 720 | 1920 x 1080 | 2560 x 1440 | expected |
| :--- | :--- | :--- | :--- | :--- |
| `body.prev` (`<`) | `skin.1` | `skin.1` | `skin.1` | `body.next` |
| `eyes.prev` | `skin.1` | `skin.1` | `skin.1` | `eyes.next` |
| `hair.prev` | `hair_colour.1` | `hair_colour.1` | `hair_colour.1` | `hair.next` |
| `expression.sad` | `expression.angry` | `hair_colour.7` | `mouth_height` | `expression.angry` |
| `expression.neutral` | `expression.happy` | `expression.happy` | `hair.prev` | `expression.happy` |

A player pressing right on a row expects the next thing in that row, as on a console. `KeyboardWindow` already does
this for its own keys (`_along_row`), for the same reason.

## Proposal

In `step`, for `left` and `right`:

1. **The row first**: the candidates whose vertical span overlaps the focus's (`_gap(a.y, a.height, b.y, b.height) ==
   0`). If any lies that way, the nearest of them along the move wins (ties to the first in tree order, as today).
2. **Else** today's scoring over every widget that way, so the focus still leaves a row at its end (right from the
   last widget of a row to a panel beside it, or from a list to the buttons right of it).

`up` and `down` stay as they are: a column-first rule would skip rows whose widgets do not line up (down from a
chooser's `>` at the right edge has no swatch under it, and should still reach the swatch row, not the chooser two
rows down).

Optionally, `KeyboardWindow._along_row` can then drop its own rule for the wrap only (wrapping at a row's ends stays
the keyboard's).

## Tests (no window)

- A `<  label  >` row above and below a row of small swatches: right from `<` is `>`, left from `>` is `<`.
- A row of weighted toggles in a wide layout (say 2000 px) with a row of swatches and a slider around it: right and
  left walk the toggles in order.
- At a row's end, right still leaves it for the nearest widget that way (a button in a column beside it).
- The existing navigation and keyboard tests pass unchanged.

## Related, seen while testing the keyboard (v0.43.0)

`KeyboardWindow.navigate` turns the pad's B into a delete while there is text and clears `back` from the nav it
passes on, but does not set `manager.esc_used`. An app that reads its own `nav.back` after `frame` (as the demo's
`read_nav` pattern and vichnimon do) then sees B as Esc and leaves the screen mid-typing. vichnimon works round it
(no Esc while `keyboard_free` is False); marking `esc_used` when a window consumes `back` would fix it for every app.
