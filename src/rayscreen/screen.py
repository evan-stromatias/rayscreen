"""Screen, Window, Event and the ScreenManager stack: the navigation model.

The game starts on a main screen; Settings pushes over it, Back pops, New Game replaces it with the
game screen. A screen marked `overlay` lets the screen below draw too, dimmed and locked (a pause
menu over the game). A `Window` is a modal panel inside a screen: while it is open, the tree under
it is locked, so a click never reaches what lies beneath.

One window of a screen at a time has the focus: the one keys go to (Esc closes it). Opening a
window focuses it; a click focuses (and raises) the window under the mouse or, outside every window,
gives the focus back to the screen. A modal window keeps the focus while it is up.

What lies under the mouse on the screen itself (the game's world) is the screen's to say: its
`hover` hook gives a tooltip for it and its `menu` hook a context menu on a right-click. rayscreen
asks only while the mouse is free (see `draw.mouse_free`) and draws the answer.
"""

from __future__ import annotations

from collections.abc import Hashable, Sequence
from dataclasses import dataclass

from rayscreen.specs import Menu, Node, Tooltip, check_unique_ids, walk
from rayscreen.state import OpenMenu, UiState

type PinnedTip = tuple[Tooltip, tuple[float, float]]  # a tooltip and the point it sits beside


def _ids(root: Node) -> set[str]:
    return {node_id for node in walk(root) if (node_id := getattr(node, "id", None)) is not None}


@dataclass(frozen=True, slots=True)
class Drop:
    """What a drag came to, as the value of its source picture's event: what was `dragged` (the source's `drag`),
    the id of the `drop` picture it was let go over (None: none), where the mouse was (`at`, in screen pixels), and
    whether that was over one of the screen's windows. No target and no window: onto the screen itself (a game's
    world); no target but a window: between its widgets, which is nowhere."""

    dragged: Hashable
    target: str | None
    at: tuple[float, float]
    over_window: bool


@dataclass(frozen=True, slots=True)
class Event:
    """What a widget did this frame; `value` is None for a click, else the new value (a `Drop` for a drag let
    go). A closing window emits an event with the window's id and value None. A context menu emits its id, the
    chosen item's id (None: dismissed) and the menu's `target`, which nothing else sets."""

    screen: str
    widget: str
    value: bool | float | str | Drop | None
    target: Hashable = None


class Window:
    """A panel over its screen: centred until dragged by its title bar, sized to its content unless
    `size` says otherwise. A `modal` window (the default) dims and locks everything below it; a
    non-modal one floats over a live screen, which is locked only while the mouse is over the
    window, so a click on it never reaches what lies beneath. A `borderless` window drops the frame
    (title bar, buttons, border); a draggable one is then dragged by clicking anywhere inside it
    that is not a widget, so its controls keep their clicks, and `minimizable` has no effect on it.
    A borderless window without a `backdrop` paints nothing of its own, so a picture with transparent
    pixels (a round minimap) shows the screen through them.
    A `minimizable` window can collapse to its title bar (the screen stays locked but is no longer
    dimmed) via its title-bar button or a double-click on the title bar; a non-`closeable` one has
    no close button and Esc does not close it. A `pauses` window
    freezes what runs behind it: its own screen and every screen below skip their `update` while the
    window is up (they still draw, locked and dimmed), and a minimized window pauses nothing —
    peeking at a moving world is the point of minimizing. A `resizable` window has a grip in its
    bottom-right corner; resizing it fixes its size (a content-sized window stops following its
    content). A window's `menu` is its context menu: a right-click on it, away from its widgets,
    opens it (a minimap's Close), as a screen's `menu` hook does over the screen itself. `position`, `drag_offset`, `resize_offset` and `minimized` are runtime state, filled
    in by the drawing code."""

    def __init__(
        self,
        id: str,
        title: str,
        root: Node,
        size: tuple[float, float] | None = None,
        draggable: bool = True,
        minimizable: bool = False,
        closeable: bool = True,
        borderless: bool = False,
        pauses: bool = False,
        modal: bool = True,
        resizable: bool = False,
        backdrop: bool = True,
        menu: Menu | None = None,
    ) -> None:
        self.id, self.title, self.root, self.size = id, title, root, size
        self.draggable, self.minimizable, self.closeable, self.borderless, self.pauses, self.modal, self.resizable = (
            draggable,
            minimizable,
            closeable,
            borderless,
            pauses,
            modal,
            resizable,
        )
        self.backdrop, self.menu = backdrop, menu
        self.position: tuple[float, float] | None = None  # the top-left corner; None: centred
        self.drag_offset: tuple[float, float] | None = None  # where in the title bar the mouse grabbed
        self.resize_offset: tuple[float, float] | None = None  # where beside the grip the mouse grabbed
        self.minimized = False
        self._cursor_set = False  # the resize cursor is showing
        self._last_title_press = -1.0  # the time of the last press on the title bar (double-click)
        self._previous_focus: Window | None = None  # what had the focus before this window took it
        self.state = UiState()
        check_unique_ids(root)

    def set_root(self, root: Node) -> None:
        """Show a new tree (a log grown longer), keeping the interaction state of the ids still in it."""
        check_unique_ids(root)
        self.root = root
        self.state.keep(_ids(root))

    def find(self, widget_id: str) -> Node | None:
        """The widget with `widget_id` in this window's tree."""
        for node in walk(self.root):
            if getattr(node, "id", None) == widget_id:
                return node
        return None

    def handle(self, screen: Screen, event: Event) -> Event | bool:
        """First chance at an event while this window is open on `screen`: True consumes an internal event, an `Event`
        replaces it (a dialog finishing with its result), False leaves it to the screen."""
        return False


class Screen:
    """A full-window scene: a widget tree, its interaction state, and its windows (modal dialogs or
    floating panels). `focus` is the window keys go to; None: the screen itself.

    `update` refreshes the mutable spec fields from the app's model once per frame; `handle` gets
    first chance at the screen's events (return True to consume one). `hover` and `menu` say what
    lies under the mouse on the screen itself (the game's world): a tooltip, and the context menu
    for a right-click there. They are asked only while the screen is on top and the mouse is over
    none of its windows and widgets."""

    def __init__(self, id: str, root: Node, *, overlay: bool = False, margin: float = 0.0) -> None:
        self.id, self.root, self.overlay, self.margin = id, root, overlay, margin
        self.windows: list[Window] = []  # bottom first: the last one is on top
        self.focus: Window | None = None
        self.state = UiState()
        check_unique_ids(root)

    def update(self, dt: float) -> None:
        """Refresh mutable spec fields from the app's model; called once per frame while visible."""

    def handle(self, event: Event) -> bool:
        """First chance at the screen's own events; True consumes the event."""
        return False

    def hover(self, x: float, y: float) -> Tooltip | None:
        """What to show for the point under the mouse, in screen pixels; None: nothing there. Asked
        every frame the mouse is free, so answer from a lookup, not a search of the whole world."""
        return None

    def menu(self, x: float, y: float) -> Menu | None:
        """The context menu for a right-click at the point; None: no menu there."""
        return None

    def pinned_tip(self) -> PinnedTip | None:
        """A tooltip shown without the mouse, beside a point in screen pixels (what a gamepad points at in the
        world); None: none. The mouse's own tooltip, an open menu or a drag hide it."""
        return None

    def open_menu(self, menu: Menu, x: float, y: float) -> None:
        """Show a context menu beside the point, closing any other, the tooltip, a half-finished edit
        and an open list. A right-click opens one from `menu`; call this to open one from code."""
        self.state.editing = None
        self.state.open_list = None
        self.state.hovered = None
        self.state.menu = OpenMenu(menu, (x, y))

    def close_menu(self, choice: str | None = None) -> Event | None:
        """Close the context menu, returning the event that says so: the chosen item's id, or None
        when it was dismissed. None when no menu is open."""
        opened = self.state.menu
        if opened is None:
            return None
        self.state.menu = None
        return Event(self.id, opened.menu.id, choice, target=opened.menu.target)

    def set_root(self, root: Node) -> None:
        """Replace the tree when its shape changes (a problem's label comes or goes): the interaction
        state of the ids still in the new tree is kept (the box being edited and what was typed in
        it, scroll offsets, an open list), the rest dropped. Ids are checked as in the constructor."""
        check_unique_ids(root)
        self.root = root
        self.state.keep(_ids(root))

    def find(self, widget_id: str) -> Node | None:
        """The widget with `widget_id`, for updating a spec from `handle`/`update`."""
        for node in walk(self.root):
            if getattr(node, "id", None) == widget_id:
                return node
        return None

    @property
    def window(self) -> Window | None:
        """The topmost window, if any."""
        return self.windows[-1] if self.windows else None

    def open(self, window: Window, focus: bool = True) -> None:
        """Show a window on top of any others, dropping any half-finished edit or open list in the
        tree beneath. It takes the focus unless `focus` is False (a panel opened in the background);
        a modal window always takes it, since nothing else can be clicked while it is up. An open
        context menu closes, silently."""
        self.state.editing = None
        self.state.open_list = None
        self.state.menu = None
        self.windows.append(window)
        if focus or window.modal:
            window._previous_focus = self.focus
            self.focus = window

    def close_window(self, window: Window | None = None) -> None:
        """Close `window` (the topmost when not given). Closing the focused window hands the focus
        back to what had it before (a modal window still up comes first)."""
        if window is None:
            window = self.window
        if window is None or window not in self.windows:
            return
        self.windows.remove(window)
        for other in self.windows:  # skip the closed window in the chain of previous focuses
            if other._previous_focus is window:
                other._previous_focus = window._previous_focus
        if self.focus is window:
            modal = next((w for w in reversed(self.windows) if w.modal), None)
            self.focus = modal or window._previous_focus

    def focus_window(self, window: Window | None) -> None:
        """Give the focus to `window`, raising it over the others, or to the screen (None). A modal
        window up keeps the focus."""
        if any(w.modal for w in self.windows) and (window is None or not window.modal):
            return
        self.focus = window
        if window is not None and window in self.windows:
            self.windows.remove(window)
            self.windows.append(window)


def dispatch(screen: Screen, events: Sequence[Event]) -> list[Event]:
    """Let `screen`'s open windows handle `events` first (`Window.handle`), then `screen.handle`; returns the events
    neither consumed."""
    remaining: list[Event] = []
    for event in events:
        consumed = False
        for window in reversed(list(screen.windows)):
            result = window.handle(screen, event)
            if isinstance(result, Event):
                event = result
                break
            if result:
                consumed = True
                break
        if not consumed and not screen.handle(event):
            remaining.append(event)
    return remaining


def paused_through(visible: list[Screen]) -> int:
    """The index up to which the visible screens are paused by a window, -1 when none: a window with
    `pauses=True` pauses its own screen and everything below it; screens pushed over it are in front
    of it and keep running."""
    return max(
        (i for i, screen in enumerate(visible) if any(w.pauses and not w.minimized for w in screen.windows)),
        default=-1,
    )


class ScreenManager:
    """The stack of screens; the top one is what the user interacts with."""

    def __init__(self) -> None:
        self._stack: list[Screen] = []
        # True when rayscreen spent this frame's Esc (dropping what was typed, closing the focused
        # window): the app's own Esc (a pause menu) skips it. Set by `draw.frame`.
        self.esc_used = False
        # True when rayscreen spent this frame's mouse press (on a window, a widget, a context
        # menu), for an app that reads clicks after `draw.frame`; before it, ask `draw.mouse_free`
        self.mouse_used = False

    def push(self, screen: Screen) -> None:
        """Show `screen` over the current top (Settings over the main screen); the top's context
        menu, tooltip and drag go away, silently."""
        if self._stack:
            self._stack[-1].state.menu = None
            self._stack[-1].state.hovered = None
            self._stack[-1].state.dragging = None
        self._stack.append(screen)

    def pop(self) -> Screen:
        """Remove and return the top screen (Settings' Back button)."""
        return self._stack.pop()

    def replace(self, screen: Screen) -> None:
        """Swap the top screen (the main menu for the game)."""
        if self._stack:
            self._stack.pop()
        self._stack.append(screen)

    def reset(self, screen: Screen) -> None:
        """Start over from one screen (quit to the main menu)."""
        self._stack = [screen]

    @property
    def top(self) -> Screen | None:
        return self._stack[-1] if self._stack else None

    def visible(self) -> list[Screen]:
        """The screens to draw, bottom first: the top, then down past any overlays."""
        if not self._stack:
            return []
        screens = [self._stack[-1]]
        while screens[-1].overlay and len(self._stack) > len(screens):
            screens.append(self._stack[-1 - len(screens)])
        return screens[::-1]


def keyboard_free(manager: ScreenManager) -> bool:
    """True when no text box of the visible screens, or of their windows, is being edited: the keys pressed are the
    app's (a game's W walks the player), not the box's."""
    for screen in manager.visible():
        if screen.state.editing is not None or any(window.state.editing is not None for window in screen.windows):
            return False
    return True
