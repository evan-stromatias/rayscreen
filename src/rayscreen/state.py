"""What crosses frames for one screen: the text box being edited and its buffer, the dropdown whose
list is open, the context menu, what the mouse has rested on (a tooltip's delay), the picture being
dragged and every scroll's offset. Keyed by widget id, so interaction state survives the tree
being rebuilt, as long as ids stay stable.

The text-editing rules come from the world generator UI's `Widgets`: a click that moves from one box
to another commits the first, and Esc drops what was being typed.
"""

import math
from collections.abc import Hashable
from dataclasses import dataclass
from typing import Any

import pyray as rl

from rayscreen.geometry import Rect
from rayscreen.specs import DRAG_START, Menu, Node, Split, walk

BUFFER = 512  # bytes a text box holds
FOLLOW_SLACK = 1.0  # pixels above its bottom a follow scroll still counts as at the bottom


@dataclass(slots=True)
class OpenList:
    """The dropdown whose list is open: where its button was drawn, what it offers, and the choice with the keys' or
    the pad's focus (`navigation.list_step`), its current one as it opens."""

    id: str
    anchor: Rect
    choices: tuple[str, ...]
    focused: int | None = None


@dataclass(slots=True)
class OpenMenu:
    """The context menu that is open, the point it opened at (it sits beside it), and the index of its item with the
    keys' or the pad's focus (`navigation.menu_step`), None until one moves it."""

    menu: Menu
    at: tuple[float, float]
    focused: int | None = None


@dataclass(slots=True)
class Hovered:
    """What the mouse rests on, since when, and whether a press has hidden its tooltip."""

    key: Hashable
    since: float
    dismissed: bool = False


@dataclass(slots=True)
class Dragging:
    """A press on a picture with `drag`, held: the source picture's id, what it carries (`value`), its texture and
    how it is drawn (`flipped`, at `ghost` pixels: its size on screen), whether it is `clickable`, and where the press
    was. `started` once the mouse has moved `DRAG_START` pixels from there: until then, letting go is a click."""

    source: str
    value: Hashable
    texture: object
    flipped: bool
    ghost: tuple[float, float]
    clickable: bool
    at: tuple[float, float]
    started: bool = False

    def move(self, x: float, y: float) -> None:
        if not self.started and math.hypot(x - self.at[0], y - self.at[1]) >= DRAG_START:
            self.started = True


class UiState:
    def __init__(self) -> None:
        self.editing: str | None = None  # the TextBox id being edited
        self.buffer: Any = rl.ffi.new(f"char[{BUFFER}]")  # its text while editing
        self._editing: str | None = None  # as they were when the frame began, so a click that moves
        self._buffer: Any = self.buffer  # from one box to another commits the first
        self.open_list: OpenList | None = None
        self.menu: OpenMenu | None = None
        self.hovered: Hovered | None = None
        # cffi pointers have no useful Python type: Scroll id -> Vector2 *, ListView id -> int *
        self._scroll: dict[str, Any] = {}
        self._list_scroll: dict[str, Any] = {}
        self.drafts: dict[str, str] = {}  # a submit TextBox's id -> what was typed in it and not sent
        self._bottoms: dict[str, float] = {}  # a follow Scroll's id -> its lowest offset last frame
        self.splits: dict[str, float] = {}  # Split id -> the ratio it was dragged to
        self.dragging_split: str | None = None  # the Split whose bar the mouse holds
        self.split_cursor = False  # the resize cursor is showing for a split's bar
        self.sliding: str | None = None  # the Slider the mouse holds, until the button is let go
        # the picture being dragged (a screen's state only: a drag crosses its windows); kept when the tree is
        # rebuilt, as what it carries names the thing, not its place
        self.dragging: Dragging | None = None
        self.focused: str | None = None  # the widget the keys or the pad move and click (`navigation`)
        self.show_focus = False  # its ring shows: a nav ask came since the mouse last moved

    def begin(self) -> bool:
        """Frame-start housekeeping; True when Esc was spent dropping what was being typed."""
        canceled = False
        if self.editing is not None and rl.is_key_pressed(rl.KeyboardKey.KEY_ESCAPE):
            self.editing = None
            canceled = True
        self._editing, self._buffer = self.editing, self.buffer
        if self.sliding is not None and not rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_LEFT):
            self.sliding = None
        return canceled

    def hover(self, key: Hashable | None, now: float, delay: float, pressed: bool) -> bool:
        """Whether the tooltip for `key` (None: nothing hovered) shows this frame: once the same key
        has been hovered for `delay` seconds. A press hides it until the mouse moves on to something
        else: the player is acting, not reading."""
        if key is None:
            self.hovered = None
            return False
        if self.hovered is None or self.hovered.key != key:
            self.hovered = Hovered(key, now)
        if pressed:
            self.hovered.dismissed = True
        return not self.hovered.dismissed and now - self.hovered.since >= delay

    def keep(self, ids: set[str]) -> None:
        """Forget what belongs to widgets no longer in the tree (a new tree has only `ids`): the box
        being edited, the open list, scroll offsets, where splits were dragged. What the remaining ids had is kept
        as it was."""
        if self.editing not in ids:
            self.editing = None
        if self._editing not in ids:
            self._editing = None
        if self.open_list is not None and self.open_list.id not in ids:
            self.open_list = None
        if self.dragging_split not in ids:
            self.dragging_split = None
        if self.sliding not in ids:
            self.sliding = None
        if self.focused not in ids:
            self.focused = None
        for kept in (self._scroll, self._list_scroll, self.splits, self.drafts, self._bottoms):
            for gone in [widget_id for widget_id in kept if widget_id not in ids]:
                del kept[gone]

    def apply_splits(self, root: Node) -> None:
        """Give the tree's splits the ratios they were dragged to, before it is laid out."""
        if not self.splits:
            return
        for node in walk(root):
            if isinstance(node, Split) and node.id in self.splits:
                node.ratio = self.splits[node.id]

    def scroll_offset(self, scroll_id: str) -> float:
        """How far a `Scroll`'s content is moved up (a negative y), without making an offset for it."""
        offset = self._scroll.get(scroll_id)
        return 0.0 if offset is None else offset[0].y

    def scroll_ptr(self, scroll_id: str) -> Any:
        """The persistent scroll offset of a `Scroll`, which raygui writes to."""
        if scroll_id not in self._scroll:
            self._scroll[scroll_id] = rl.ffi.new("Vector2 *")
        return self._scroll[scroll_id]

    def list_scroll_ptr(self, list_id: str) -> Any:
        """The persistent scroll position of a `ListView`, which raygui writes to."""
        if list_id not in self._list_scroll:
            self._list_scroll[list_id] = rl.ffi.new("int *")
        return self._list_scroll[list_id]

    def take_draft(self, box_id: str) -> str:
        """What was typed in the submit box `box_id` and not sent, which it no longer holds: a Send button's text.
        While the box is being edited, that is the text in it, and the box is cleared."""
        if box_id in (self.editing, self._editing):
            text = rl.ffi.string(self.buffer).decode("utf-8", "replace")
            self.buffer[0] = b"\0"
            self.drafts.pop(box_id, None)
            return text
        return self.drafts.pop(box_id, "")

    def follow(self, scroll_id: str, offset: float, bottom: float) -> float:
        """A follow scroll's offset this frame, given the one it has (`offset`) and its lowest (`bottom`, at most 0):
        the bottom if it was at the bottom last frame (or on its first frame), else `offset` as the user left it."""
        last = self._bottoms.get(scroll_id)
        self._bottoms[scroll_id] = bottom
        return bottom if last is None or offset <= last + FOLLOW_SLACK else offset
