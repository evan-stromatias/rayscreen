# Feature request 001: an on-screen keyboard window, for typing with a gamepad

Requested 2026-11-13 by vichnimon, for the player's name on its character creation screen (vichnimon plan 016,
*The creation screen*). Status: proposed; not started.

## Why

A `TextBox` can only be typed into with a physical keyboard, and it cannot take the focus by keys or the pad
(`navigation.Focusable` leaves it out). A game played with a pad needs a way to enter short text: a name, a save's
label, a seed. Console games do it with an on-screen keyboard: Nintendo Switch games open a panel over the screen
with the text being typed on top, a grid of keys under it, and the pad moving over the keys.

## What vichnimon needs

- A name field on its creation screen, at most about 16 characters, letters, digits, space and a few marks (`-`, `'`,
  `.`).
- With a pad, activating the field opens the keyboard; confirming puts the text in the field (one event, as a
  `TextBox` gives when it is left); cancelling leaves it as it was.
- With the mouse and keyboard, the field stays an ordinary `TextBox`: click and type.

## Proposal

### 1. A focusable `TextBox`

- `TextBox` joins `Focusable` (enabled boxes only): the pad and the arrow keys move onto it like onto a button.
- Activating a focused box (`Nav.activate`) emits an event the screen can act on, say `Event(screen, box.id, None)`
  with a marker, or a new field on `Event`, rather than starting keyboard editing: the app decides whether to open the
  keyboard window (a pad) or start editing in place (Enter on a keyboard). A spec flag could choose it instead:
  `TextBox(..., keyboard=True)` opens the `KeyboardWindow` itself on activation.

### 2. `KeyboardWindow(Window)` (`rayscreen/keyboard_window.py`)

Built from specs, no raylib, like `FileWindow`:

```python
KeyboardWindow(
    id: str,               # the result event's widget
    title: str,            # "Your name"
    text: str = "",        # what the box holds now
    max_length: int = 32,
    layout: KeyLayout = QWERTY,   # rows of keys; a layout constant, so others (AZERTY, digits only) can be added
    ok: str = "OK",
)
```

- **Look**: modal, centred. On top, the text typed so far in a large line with a caret and a count (`5 / 16`); under
  it the key grid, one `Button` per key in rows (`1-0`, `q-p`, `a-l`, `z-m` with marks), and a bottom row with
  **Shift**, **Space** (wide), **Backspace** and **OK**. Shift shows the keys in capitals; it releases after one
  letter unless double-pressed (caps lock).
- **Pad** (Switch conventions):
  - the d-pad or left stick moves over the keys (rayscreen's spatial `step` already does this over a grid of buttons;
    left from the first key of a row wraps to its last, as console keyboards do);
  - **A** types the focused key;
  - **B** deletes the last character; on an empty line it cancels (closes, nothing emitted);
  - **Y** types a space, **X** toggles shift, **Start/+** confirms; **L/R** move the caret (optional, a later step).
  These are more than `Nav`'s move/activate/back: either `Nav` gains optional fields (`delete`, `space`, `shift`,
  `confirm`) that the app fills from its pad, or the window reads raylib's gamepad buttons itself. The first keeps
  rayscreen free of the app's bindings and testable without a window.
- **Keyboard and mouse** work while it is open: a click on a key types it; a physical key types its character,
  Backspace deletes, Enter confirms, Esc cancels.
- **Result**, as `FileWindow` gives its own: `Event(screen.id, window.id, text)` on OK, `Event(screen.id, window.id,
  None)` on cancel or close. OK is greyed while the text is empty (or `allow_empty=True`).
- **Limits**: `max_length` greys the character keys when full; only the layout's characters can be typed (a physical
  key outside it is ignored), so the app gets text its font can draw.

### 3. In the demo

A *Keyboard* scene in `r-rayscreen-demo`: a name field that opens the window, with a screenshot in
`docs/screenshots/`.

## Tests (no window)

- `TextBox` is focusable; activating it gives the event (or opens the window, with the flag).
- The window: typing keys, shift releasing after one letter, caps lock, backspace, the length limit greying the keys,
  OK's event with the text, cancel's with None, B on an empty line cancelling.
- Spatial moves over the key rows, and the row wrap.

## Open questions

- Should the window also offer accented letters (a long press, or a second page of keys, as Switch does)? vichnimon
  does not need them yet.
- Which pad buttons: rayscreen-level `Nav` fields (proposed) or the window's own reading of the pad?
