"""Modal on-screen keyboard window (`KeyboardWindow`), for typing short text with a pad, built from rayscreen specs with
no raylib.

- The text typed so far shows on top in large type with a caret and a count (`5 / 16`); under it a grid of keys
  (`KeyLayout`, one `Button` per character) and a bottom row of Shift (an arrow icon, filled while shifted), Space,
  Backspace (a key icon with an X) and OK.
- A pad moves over the keys with the focus (`Nav.move`; left and right keep to the row, wrapping at its ends) and types the
  focused one (`Nav.activate`). Its other buttons come in through `Nav`: `delete`, `space`, `shift`, `confirm`, and
  `back`, which deletes, or cancels on an empty line. The app fills them from its own pad bindings.
- The mouse clicks keys, and a physical keyboard types its characters (`Typed`): Backspace deletes, Enter confirms,
  Esc cancels. Only the layout's characters can be typed, so the text is one the app's font can draw.
- Internal events are handled inside `KeyboardWindow.handle`; the screen only receives `Event(screen.id, window.id,
  text)` on OK (or the `box`'s own event, see `KeyboardWindow`), or `Event(screen.id, window.id, None)` on cancel.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

from rayscreen.icons import BACKSPACE, CAPS_LOCK, SHIFT, SHIFT_ON, icon_text
from rayscreen.navigation import Nav, Steered, Typed
from rayscreen.screen import Event, Screen, Window
from rayscreen.specs import GAP, SMALL, Button, Column, Fill, Label, Node, Row, TextBox, Tooltip

type KeyLayout = tuple[str, ...]  # the keys' rows, top first, one character a key
type Shift = Literal["off", "once", "lock"]

QWERTY: KeyLayout = ("1234567890", "qwertyuiop", "asdfghjkl-", "zxcvbnm,.'")
KEY = 40.0  # a key's side
LINE = 32  # the typed text's size: the font's 16 px grid, doubled
_SHIFT_ICONS: dict[Shift, tuple[int, str]] = {"off": (SHIFT, "Shift"), "once": (SHIFT_ON, "Shift"), "lock": (CAPS_LOCK, "Caps lock")}


class KeyboardWindow(Window):
    """A modal keyboard for typing up to `max_length` characters of `layout` into `text`.

    - OK is greyed while the text is empty, unless `allow_empty`; the character keys and Space are greyed once it is
      full, and the focus moves on to OK.
    - Shift shows the letters in capitals for one key; pressed again it locks them (caps lock), and a third press
      releases it. Its arrow is outlined while off and filled while on, with a bar under it while locked.
    - With `capitalize` (the default, for a name), shift is on for the first character: as the window opens on an
      empty line and whenever Backspace empties it. Shift can still be turned off for it.
    - With a `box` (the id of the screen's `TextBox` the text is for), OK sets the box's text and the event is the
      box's own, `Event(screen.id, box, text)`, as leaving the box after typing in it gives: the app handles both
      alike. Cancelling still gives `Event(screen.id, window.id, None)` and leaves the box as it was.
    """

    typing = True

    def __init__(
        self,
        id: str,
        title: str,
        text: str = "",
        *,
        max_length: int = 32,
        layout: KeyLayout = QWERTY,
        ok: str = "OK",
        allow_empty: bool = False,
        box: str | None = None,
        capitalize: bool = True,
    ) -> None:
        self.text = text[:max_length]
        self.max_length = max_length
        self.layout = layout
        self.ok_label = ok
        self.allow_empty = allow_empty
        self.box = box
        self.capitalize = capitalize
        self.shift: Shift = "once" if capitalize and not self.text else "off"
        self.characters = frozenset(" ").union(*layout, *(row.upper() for row in layout))
        super().__init__(id, title, Column(children=[]), modal=True)
        self.refresh()
        self.state.focused = self._key_id(0, 0)

    def _key_id(self, row: int, column: int) -> str:
        return f"{self.id}.key.{row}.{column}"

    @property
    def full(self) -> bool:
        return len(self.text) >= self.max_length

    @property
    def can_confirm(self) -> bool:
        """Whether OK is enabled for the text typed so far."""
        return bool(self.text) or self.allow_empty

    def key(self, row: int, column: int) -> str:
        """The character the key at `row`, `column` types now: in capitals while shifted."""
        character = self.layout[row][column]
        return character.upper() if self.shift != "off" else character

    def insert(self, characters: str) -> None:
        """Type `characters` at the end, skipping any the layout has no key for and stopping when full."""
        for character in characters:
            if self.full:
                break
            if character in self.characters:
                self.text += character
        self.refresh()

    def press(self, row: int, column: int) -> None:
        """Type the key at `row`, `column`; a one-key shift releases."""
        if self.full:
            return
        self.text += self.key(row, column)
        if self.shift == "once":
            self.shift = "off"
        self.refresh()

    def backspace(self) -> None:
        """Delete the last character; emptying the line shifts the next one, with `capitalize`."""
        if self.text:
            self.text = self.text[:-1]
            if not self.text and self.capitalize and self.shift == "off":
                self.shift = "once"
        self.refresh()

    def toggle_shift(self) -> None:
        """Off, then shifted for one key, then locked, then off again."""
        self.shift = {"off": "once", "once": "lock", "lock": "off"}[self.shift]
        self.refresh()

    def _rows(self) -> list[list[str]]:
        """The ids of the widgets the focus moves over, a row each, top first: the keys, then the bottom row."""
        rows = [[self._key_id(r, c) for c in range(len(keys))] for r, keys in enumerate(self.layout)]
        rows.append([f"{self.id}.{name}" for name in ("shift", "space", "backspace", "ok")])
        return rows

    def _enabled(self, widget_id: str) -> bool:
        node = self.find(widget_id)
        return node is not None and getattr(node, "enabled", False)

    def _build(self) -> Column:
        caret = "" if self.full else "_"
        line = Row(children=[
            Label(f"{self.id}.text", self.text + caret, size=LINE, height=LINE + 2 * GAP, weight=1),
            Label(f"{self.id}.count", f"{len(self.text)} / {self.max_length}", size=SMALL, height=LINE + 2 * GAP, tone="muted"),
        ])
        rows: list[Node] = [line]
        for r, keys in enumerate(self.layout):
            buttons: list[Node] = [
                Button(self._key_id(r, c), self.key(r, c), enabled=not self.full, width=KEY, height=KEY)
                for c in range(len(keys))
            ]
            rows.append(Row(children=[Fill(), *buttons, Fill()]))
        icon, name = _SHIFT_ICONS[self.shift]
        rows.append(Row(children=[
            Button(f"{self.id}.shift", icon_text(icon), height=KEY, tooltip=Tooltip.text(f"{self.id}.shift", name)),
            Button(f"{self.id}.space", "Space", enabled=not self.full, height=KEY, weight=1),
            Button(f"{self.id}.backspace", icon_text(BACKSPACE), height=KEY, tooltip=Tooltip.text(f"{self.id}.backspace", "Backspace")),
            Button(f"{self.id}.ok", self.ok_label, enabled=self.can_confirm, height=KEY),
        ]))
        return Column(children=rows)

    def refresh(self) -> None:
        """Rebuild the keys after the text or the shift changed; a focus left on a greyed key moves on to OK."""
        self.set_root(self._build())
        focused = self.state.focused
        if focused is not None and self.find(focused) is not None and not self._enabled(focused):
            self.state.focused = f"{self.id}.ok" if self.can_confirm else f"{self.id}.backspace"

    def _along_row(self, move: str) -> str | None:
        """Where left or right goes: the next enabled widget in the focus's own row, round to the other end past
        its last, as on a console's keyboard. The spatial step would not keep to the row: from Shift, a letter up
        and to the right is nearer than the far centre of the wide Space. None when the focus is in no row."""
        focused = self.state.focused
        for row in self._rows():
            enabled = [widget_id for widget_id in row if self._enabled(widget_id)]
            if focused in enabled:
                at = enabled.index(focused) + (1 if move == "right" else -1)
                return enabled[at % len(enabled)]
        return None

    def navigate(self, nav: Nav, typed: Typed) -> Steered:
        """The pad's keyboard buttons, and the physical keyboard. A physical key pressed this frame wins over what the
        app made of it (Backspace or Enter it also reads as a nav), so nothing is typed twice."""
        clicks: list[str] = []
        if typed.any:
            nav = Nav(move=nav.move, shift=nav.shift)
            if typed.text:
                self.insert(typed.text)
            if typed.backspace:
                self.backspace()
            if typed.enter:
                clicks.append(f"{self.id}.ok")
        if nav.delete or (nav.back and self.text):
            self.backspace()
            nav = replace(nav, back=False)
        if nav.space:
            self.insert(" ")
        if nav.shift:
            self.toggle_shift()
        if nav.confirm:
            clicks.append(f"{self.id}.ok")
        if nav.move in ("left", "right") and (target := self._along_row(nav.move)) is not None:
            self.state.focused = target
            nav = replace(nav, move=None)
        return Steered(replace(nav, delete=False, space=False, shift=False, confirm=False), tuple(clicks))

    def handle(self, screen: Screen, event: Event) -> Event | bool:
        prefix = f"{self.id}."
        if not event.widget.startswith(prefix):
            return False
        action = event.widget.removeprefix(prefix)
        if action.startswith("key."):
            row, _, column = action.removeprefix("key.").partition(".")
            self.press(int(row), int(column))
        elif action == "space":
            self.insert(" ")
        elif action == "backspace":
            self.backspace()
        elif action == "shift":
            self.toggle_shift()
        elif action == "ok":
            if not self.can_confirm:
                return True
            screen.close_window(self)
            if self.box is None:
                return Event(screen.id, self.id, self.text)
            box = screen.find(self.box)
            if isinstance(box, TextBox):
                box.text = self.text
            return Event(screen.id, self.box, self.text)
        else:
            return False
        return True
