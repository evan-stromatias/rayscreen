"""The per-frame walk: calls the raygui control matching each spec, and returns what happened.

Locking rules, proven in the world generator UI: a screen under an overlay screen, and a tree under
a modal window or an open dropdown, draw locked, so a click on top never reaches what lies beneath;
overlays (the open list, a window) draw last. A scroll's content draws scissored to its view; what is
wholly outside is skipped, and what is half in view is locked, so it cannot take the click meant for
what shows through.

The mouse is free when it is over the top screen itself, not over a window, a widget or a popup:
then the screen's `hover` hook is asked for a tooltip, and its `menu` hook on a right-click. A picture,
label, text, button, toggle or bar with a `tooltip` shows it while the mouse rests on it, in place of the hook's. An open context menu
locks everything under it, and a press outside it dismisses it and is spent there.

A drag (a picture with `drag`, pressed and moved) belongs to the top screen's state, so it crosses its windows: while
it runs everything draws locked (letting go over a button must not click it), its picture follows the mouse over
everything, and letting go emits the source's `Drop` event (`release_drag`). Esc cancels it.
"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager, nullcontext
from typing import NamedTuple

import pyray as rl

from rayscreen.geometry import Rect, place_beside
from rayscreen.layout import (
    POPUP_ROW,
    MenuSize,
    arrange,
    elided,
    icon_scale,
    measure,
    menu_size,
    picture_rect,
    scale_in,
    split_bar,
    split_ratio,
    text_lines,
    text_size,
    title_strip,
    tooltip_size,
    widget_scale,
    wrap_text,
)
from rayscreen.navigation import Nav, Typed, focusables, into_view, list_step, menu_step, slid, step, visible
from rayscreen.screen import Drop, Event, Screen, ScreenManager, Window, dispatch, paused_through
from rayscreen.specs import (
    CHECK,
    GAP,
    ICON,
    PAD,
    ROW,
    SCROLL_BORDER,
    TOOLTIP_OFFSET,
    WINDOW_TITLE,
    WINDOW_WIDTH,
    Board,
    Button,
    CheckBox,
    Column,
    Dropdown,
    Fill,
    Grid,
    Label,
    ListView,
    Menu,
    Node,
    Panel,
    Picture,
    Progress,
    Row,
    Scroll,
    Separator,
    Slider,
    Split,
    Swatch,
    Table,
    Text,
    TextBox,
    Toggle,
    Tone,
    Tooltip,
    walk,
)
from rayscreen.state import BUFFER, Dragging, OpenList, OpenMenu, UiState
from rayscreen.theme import Theme

ARROW_DOWN, ARROW_UP = rl.GuiIconName.ICON_ARROW_DOWN, rl.GuiIconName.ICON_ARROW_UP
# window title bars: raygui has no minimize glyph, so the button reads as collapse (up) and expand (down)
ICON_CLOSE, ICON_MINIMIZE, ICON_RESTORE = rl.GuiIconName.ICON_CROSS, ARROW_UP, ARROW_DOWN
TITLE_BUTTON = 20.0  # the side of a window's title bar button
GRIP = 16.0  # the resize grip's hit zone, in the window's bottom-right corner
MIN_WINDOW = 160.0  # a resizable window's minimum width
DOUBLE_CLICK = 0.4  # seconds between two title-bar presses that toggle a window's minimization
LEFT, RIGHT = rl.MouseButton.MOUSE_BUTTON_LEFT, rl.MouseButton.MOUSE_BUTTON_RIGHT
WHEEL_STEP = 30.0
_TOOLTIP_STATE = UiState()  # a tooltip's widgets draw locked: their state is never kept
GHOST_ALPHA = 0.8  # a dragged picture under the mouse: the boxes beneath show through a little


class _Drawn(NamedTuple):
    ate_esc: bool  # Esc was spent on the screen (dropping what was typed, closing the focused window, a drag)
    tooltip: Tooltip | None  # of the picture, label or button under the mouse, in the tree that has the mouse
    menu: Menu | None  # of the picture under the mouse there, for a right-click


def frame(manager: ScreenManager, theme: Theme, nav: Nav | None = None) -> list[Event]:
    """Draw one frame of the manager's visible screens; returns the events no screen consumed. `nav` is what the keys
    or the pad asked of the top screen this frame (`navigation`), applied after it is drawn: a back that closes a
    window marks `esc_used`, as Esc does; any other back is the app's."""
    visible = manager.visible()
    if not visible:
        return []
    dt = rl.get_frame_time()
    paused = paused_through(visible)  # paused screens keep drawing, frozen in time
    for i, screen in enumerate(visible):
        if i > paused:
            screen.update(dt)
    events: list[Event] = []
    width, height = float(rl.get_screen_width()), float(rl.get_screen_height())
    manager.esc_used = False
    for screen in visible[:-1]:
        manager.esc_used = _draw_screen(screen, theme, width, height, events, locked=True).ate_esc or manager.esc_used
        rl.draw_rectangle(0, 0, int(width), int(height), theme.dim)
    top = visible[-1]
    mouse = rl.get_mouse_position()
    pressed = rl.is_mouse_button_pressed(LEFT) or rl.is_mouse_button_pressed(RIGHT)
    pointer = _pointer_free(top, theme, width, height, mouse)  # as the frame begins, a menu aside
    window_menu = _window_menu_at(top, theme, width, height, mouse)
    free = pointer and top.state.menu is None
    held = top.state.dragging if top.state.dragging is not None and top.state.dragging.started else None  # as the frame begins
    drawn = _draw_screen(top, theme, width, height, events, locked=False)
    manager.esc_used = drawn.ate_esc or manager.esc_used
    opened = False
    dragging = held is not None
    # free, or a right-click outside the open menu just dismissed it: right-clicking around moves it
    if pointer and top.state.menu is None and rl.is_mouse_button_pressed(RIGHT):
        menu = top.menu(mouse.x, mouse.y)
        if menu is not None:
            top.open_menu(menu, mouse.x, mouse.y)
            opened = True
    elif window_menu is not None and top.state.menu is None and rl.is_mouse_button_pressed(RIGHT):
        top.open_menu(window_menu, mouse.x, mouse.y)
        opened = True
    elif drawn.menu is not None and top.state.menu is None and not dragging and rl.is_mouse_button_pressed(RIGHT):
        top.open_menu(drawn.menu, mouse.x, mouse.y)
        opened = True
    tooltip = None
    if not opened and top.state.menu is None and not dragging:
        tooltip = drawn.tooltip or (top.hover(mouse.x, mouse.y) if free else None)
    if top.state.hover(None if tooltip is None else tooltip.key, rl.get_time(), theme.tooltip_delay, pressed):
        _draw_tooltip(tooltip, theme, width, height, mouse)
    elif tooltip is None and top.state.menu is None and not dragging and (pinned := top.pinned_tip()) is not None:
        _draw_tooltip(pinned[0], theme, width, height, rl.Vector2(*pinned[1]))
    if held is not None:  # on the frame it is let go too: the box it lands in is drawn from next frame
        _draw_ghost(held, theme, mouse)
    manager.mouse_used = pressed and (not free or opened)
    _navigate(manager, top, theme, nav if nav is not None else Nav(), events)
    return dispatch(top, events)


def _navigate(manager: ScreenManager, screen: Screen, theme: Theme, nav: Nav, events: list[Event]) -> None:
    """Apply `nav` to the screen, or to its window that has the focus: move the focus (left and right move a focused
    slider instead), click it (a button's event, a toggle or check box flipped, a dropdown's list opened, a picture's
    click or its menu opened beside it, a text box edited or its keyboard event), back out of a closeable window; then
    ring the focus while it shows, with its tooltip beside it.

    - An open context menu takes the nav first (`_navigate_menu`), then an open dropdown list (`_navigate_list`).
    - The focused window then sees it (`Window.navigate`), with what was typed if it takes typing: its pad shortcuts
      are its, and the nav it leaves moves the focus.
    - While a text box is being edited, the nav is ignored: the keys are the box's, and a move would leave it
      editing behind a ring somewhere else.
    - The mouse moving or clicking hides the ring, the next ask brings it back."""
    window = screen.focus if screen.focus is not None and screen.focus in screen.windows else None
    root, state = (window.root, window.state) if window is not None else (screen.root, screen.state)
    delta = rl.get_mouse_delta()
    if delta.x or delta.y or rl.is_mouse_button_pressed(LEFT):
        state.show_focus = False
    if nav.any:
        state.show_focus = True
    if screen.state.menu is not None:
        _navigate_menu(manager, screen, theme, nav, events, state.show_focus)
        return
    if state.open_list is not None:
        _navigate_list(manager, screen.id, root, state, theme, nav, events)
        return
    if state.editing is not None:
        return
    if window is not None:
        steered = window.navigate(nav, _typed() if window.typing else Typed())
        nav = steered.nav
        events.extend(Event(screen.id, widget, None) for widget in steered.clicks)
        root = window.root  # the window may have rebuilt its tree
    nodes = focusables(root, state.scroll_offset)
    current = next((placed.node for placed in nodes if placed.node.id == state.focused), None)
    value = slid(current, nav.move) if isinstance(current, Slider) and nav.move is not None else None
    if value is not None:
        if value != current.value:
            current.value = value
            events.append(Event(screen.id, current.id, value))
    elif nav.move is not None:
        state.focused = step(nodes, state.focused, nav.move)
    elif nav.activate:
        placed = next((placed for placed in nodes if placed.node.id == state.focused), None)
        focused = placed.node if placed is not None else None
        if focused is None:  # nothing focused yet: the first press only shows where the focus is
            state.focused = nodes[0].node.id if nodes else None
        elif isinstance(focused, Button):
            events.append(Event(screen.id, focused.id, None))
        elif isinstance(focused, Toggle):
            focused.active = not focused.active
            events.append(Event(screen.id, focused.id, focused.active))
        elif isinstance(focused, CheckBox):
            focused.checked = not focused.checked
            events.append(Event(screen.id, focused.id, focused.checked))
        elif isinstance(focused, Dropdown):
            state.open_list = OpenList(focused.id, placed.rect, focused.choices, focused.current)
            return
        elif isinstance(focused, TextBox) and focused.keyboard:
            events.append(Event(screen.id, focused.id, None))
        elif isinstance(focused, TextBox):
            state.edit(focused)
            return
        elif isinstance(focused, Picture) and focused.clickable:
            events.append(Event(screen.id, focused.id, None))
        elif isinstance(focused, Picture) and focused.menu is not None:
            x, y, width, _ = placed.rect
            screen.open_menu(focused.menu, x + width, y)
            screen.state.menu.focused = menu_step(focused.menu.items, None, "down")
            return
    if nav.back and window is not None and window.closeable and not manager.esc_used:
        events.append(Event(screen.id, window.id, None))
        screen.close_window(window)
        manager.esc_used = True
        return
    placed = next((placed for placed in nodes if placed.node.id == state.focused), None)
    if placed is None:
        return
    if nav.any and placed.scroll is not None:  # the focus's scroll follows it; the wheel may still scroll it away
        scroll = state.scroll_ptr(placed.scroll.id)
        shown = into_view(placed, scroll[0].y)
        placed = placed._replace(rect=placed.rect._replace(y=placed.rect.y + shown - scroll[0].y))
        scroll[0].y = shown
    if state.show_focus and visible(placed):
        x, y, width, height = placed.rect
        rl.draw_rectangle_lines_ex(rl.Rectangle(x - 3, y - 3, width + 6, height + 6), 2, theme.accent)
        tooltip = None if isinstance(placed.node, (CheckBox, TextBox)) else placed.node.tooltip
        if tooltip is not None:  # what the mouse resting on it would show, beside its corner
            _draw_tooltip(tooltip, theme, float(rl.get_screen_width()), float(rl.get_screen_height()),
                          rl.Vector2(x + width, y + height))


def _typed() -> Typed:
    """What was typed on the physical keyboard this frame: its characters (raylib's queue, emptied), and Backspace
    (held, it repeats) and Enter."""
    characters: list[str] = []
    while (codepoint := rl.get_char_pressed()) > 0:
        characters.append(chr(codepoint))
    backspace = rl.is_key_pressed(rl.KeyboardKey.KEY_BACKSPACE) or rl.is_key_pressed_repeat(rl.KeyboardKey.KEY_BACKSPACE)
    enter = rl.is_key_pressed(rl.KeyboardKey.KEY_ENTER) or rl.is_key_pressed(rl.KeyboardKey.KEY_KP_ENTER)
    return Typed("".join(characters), backspace, enter)


def _navigate_list(manager: ScreenManager, owner: str, root: Node, state: UiState, theme: Theme, nav: Nav,
                   events: list[Event]) -> None:
    """The open dropdown list under the nav: up and down its choices, activating takes the focused one, back closes it
    with the choice unchanged (spending the back, as Esc on it is spent); the focused choice ringed while the focus
    shows."""
    open_list = state.open_list
    assert open_list is not None
    layout = _open_list_layout(open_list)
    if nav.move is not None:
        open_list.focused = list_step(len(layout.shown), open_list.focused, nav.move)
    elif nav.activate and open_list.focused is not None and open_list.focused < len(layout.shown):
        _choose(owner, root, state, events, layout.shown[open_list.focused])
        return
    if nav.back and not manager.esc_used:
        state.open_list = None
        manager.esc_used = True
        return
    if state.show_focus and open_list.focused is not None and open_list.focused < len(layout.shown):
        bounds = layout.bounds
        y = bounds.y + 1 + open_list.focused * POPUP_ROW
        rl.draw_rectangle_lines_ex(rl.Rectangle(bounds.x, y - 1, bounds.width, ROW + 2), 2, theme.accent)


def _navigate_menu(manager: ScreenManager, screen: Screen, theme: Theme, nav: Nav, events: list[Event], ring: bool) -> None:
    """The open context menu under the nav: up and down its enabled items, activating chooses the focused one, back
    dismisses it (spending the back, as Esc on it is spent); the focused item ringed while the focus shows."""
    opened = screen.state.menu
    assert opened is not None
    items = opened.menu.items[: menu_size(opened.menu, float(rl.get_screen_height()), theme.text_width).shown]
    if nav.move is not None:
        opened.focused = menu_step(items, opened.focused, nav.move)
    elif nav.activate and opened.focused is not None:
        if (event := screen.close_menu(items[opened.focused].id)) is not None:
            events.append(event)
        return
    elif nav.activate:
        opened.focused = menu_step(items, None, "down")
    if nav.back and not manager.esc_used:
        if (event := screen.close_menu()) is not None:
            events.append(event)
        manager.esc_used = True
        return
    if ring and opened.focused is not None:
        width, height = float(rl.get_screen_width()), float(rl.get_screen_height())
        rect = _menu_item_rect(opened, theme, width, height, opened.focused)
        rl.draw_rectangle_lines_ex(rl.Rectangle(rect.x - 1, rect.y - 1, rect.width + 2, rect.height + 2), 2, theme.accent)


def mouse_free(manager: ScreenManager, screen: Screen, theme: Theme) -> bool:
    """True when the mouse belongs to `screen` itself this frame (the game's world under its HUD):
    the screen is on top of the stack, no context menu is open, and the mouse is over none of its
    windows and widgets. It is the rule `frame` asks the `hover` and `menu` hooks under, from last
    frame's layout, so a game that reads clicks before `frame` acts on exactly the ones rayscreen
    leaves it."""
    if manager.top is not screen or screen.state.menu is not None:
        return False
    width, height = float(rl.get_screen_width()), float(rl.get_screen_height())
    return _pointer_free(screen, theme, width, height, rl.get_mouse_position())


def _pointer_free(screen: Screen, theme: Theme, width: float, height: float, mouse: rl.Vector2) -> bool:
    """True when the mouse is over the screen itself: no modal window, open dropdown list, drag or
    resize in flight, and not over a window or a widget that takes the mouse (as laid out last
    frame). An open context menu is left to the caller: a right-click outside one moves it."""
    if screen.state.open_list is not None or screen.state.dragging_split is not None or screen.state.dragging is not None:
        return False
    for window in screen.windows:
        if window.modal or window.state.open_list is not None or window.drag_offset is not None or window.resize_offset is not None:
            return False
    if _window_at(screen, theme, width, height, mouse) is not None:
        return False
    return not _over_widget(screen.root, mouse, solid=True)


def _window_menu_at(screen: Screen, theme: Theme, width: float, height: float, mouse: rl.Vector2) -> Menu | None:
    """The context menu of the window under the mouse, when the mouse is on the window itself (not on one of its
    widgets) and nothing else holds the mouse: no modal window below or above, no open list, drag or resize."""
    if screen.state.open_list is not None or screen.state.dragging_split is not None:
        return None
    window = _window_at(screen, theme, width, height, mouse)
    if window is None or window.menu is None or window.minimized:
        return None
    for other in screen.windows:
        if (other.modal and other is not window) or other.state.open_list is not None or other.drag_offset is not None \
                or other.resize_offset is not None:
            return None
    return None if _over_widget(window.root, mouse) else window.menu


def _draw_screen(screen: Screen, theme: Theme, width: float, height: float, events: list[Event], locked: bool) -> _Drawn:
    """Draw one screen and its windows; whether Esc was spent here, and the tooltip of the picture, label or button under the
    mouse (in the topmost window there, or the screen's tree outside every window)."""
    ate_esc = screen.state.begin()
    for window in screen.windows:
        ate_esc = window.state.begin() or ate_esc
    dragging = screen.state.dragging
    if not locked and not ate_esc and dragging is not None and dragging.started and rl.is_key_pressed(rl.KeyboardKey.KEY_ESCAPE):
        screen.state.dragging = dragging = None  # cancelled: no event
        ate_esc = True
    dragged = dragging.source if dragging is not None and dragging.started else None
    menu_open = screen.state.menu is not None
    if not locked and not menu_open and rl.is_mouse_button_pressed(LEFT):
        _focus_at(screen, theme, width, height, rl.get_mouse_position())
    if not locked and not ate_esc and menu_open and rl.is_key_pressed(rl.KeyboardKey.KEY_ESCAPE):
        if (event := screen.close_menu()) is not None:
            events.append(event)
        ate_esc = True
    focused = screen.focus
    listing = screen.state if screen.state.open_list is not None else focused.state if focused is not None else None
    if not locked and not ate_esc and listing is not None and listing.open_list is not None \
            and rl.is_key_pressed(rl.KeyboardKey.KEY_ESCAPE):  # Esc closes an open dropdown list first
        listing.open_list = None
        ate_esc = True
    if not locked and not ate_esc and focused is not None and focused.closeable and rl.is_key_pressed(rl.KeyboardKey.KEY_ESCAPE):
        events.append(Event(screen.id, focused.id, None))
        screen.close_window(focused)
        ate_esc = True
    bounds = Rect(0, 0, width, height).inset(screen.margin)
    screen.state.apply_splits(screen.root)
    arrange(screen.root, bounds, theme.text_width)
    drawer = _Drawer(theme, screen.id, screen.state, events, dragged)
    under = _window_at(screen, theme, width, height, rl.get_mouse_position())
    lock = locked or _screen_locked(screen, theme, width, height)
    if lock:
        rl.gui_lock()
    drawer.draw(screen.root)
    if lock:
        rl.gui_unlock()
    if not locked and screen.state.open_list is not None:
        _draw_open_list(screen.id, screen.root, screen.state, theme, events)
    found = drawer if under is None else None  # the tree that has the mouse: its tooltip, menu and press
    windows = list(screen.windows)  # a window's close button removes it mid-loop
    for i, window in enumerate(windows):
        if window.modal and not window.minimized:
            rl.draw_rectangle(0, 0, int(width), int(height), theme.dim)
        modal_above = any(w.modal for w in windows[i + 1 :])
        window_locked = locked or modal_above or screen.state.menu is not None or dragged is not None
        window_drawer = _draw_window(screen, window, theme, width, height, events, window_locked, dragged)
        if window is under:
            found = window_drawer
    if not locked:
        _follow_drag(screen, theme, width, height, events, found.pressed if found is not None else None)
    if not locked and screen.state.menu is not None:
        _draw_menu(screen, theme, width, height, events)
    if locked or found is None:
        return _Drawn(ate_esc, None, None)
    return _Drawn(ate_esc, found.tooltip, found.menu)


def _follow_drag(screen: Screen, theme: Theme, width: float, height: float, events: list[Event], pressed: Dragging | None) -> None:
    """The drag across frames: begun by this frame's press on a picture with `drag`, started once the mouse has
    moved far enough, and let go with its event (`release_drag`)."""
    state = screen.state
    if state.dragging is None:
        state.dragging = pressed
        return
    mouse = rl.get_mouse_position()
    if rl.is_mouse_button_down(LEFT):
        state.dragging.move(mouse.x, mouse.y)
        return
    event = release_drag(screen, theme, width, height, (mouse.x, mouse.y))
    if event is not None:
        events.append(event)


def release_drag(screen: Screen, theme: Theme, width: float, height: float, mouse: tuple[float, float]) -> Event | None:
    """Let go of the screen's drag at `mouse`: the source's `Drop` event once it had started; before that, its click
    when it is clickable, else nothing. The drag is over either way."""
    dragging, screen.state.dragging = screen.state.dragging, None
    if dragging is None:
        return None
    if not dragging.started:
        return Event(screen.id, dragging.source, None) if dragging.clickable else None
    target, over_window = drop_target(screen, theme, width, height, mouse)
    return Event(screen.id, dragging.source, Drop(dragging.value, target, mouse, over_window))


def drop_target(screen: Screen, theme: Theme, width: float, height: float, mouse: tuple[float, float]) -> tuple[str | None, bool]:
    """The `drop` picture under `mouse` (None: none), in the topmost window there or else the screen's own tree, as
    laid out last frame and scrolled as they are; and whether the mouse is over a window."""
    window = _window_at(screen, theme, width, height, rl.Vector2(*mouse))
    if window is None:
        return _drop_under(screen.root, screen.state, mouse), False
    return (None if window.minimized else _drop_under(window.root, window.state, mouse)), True


def _drop_under(node: Node, state: UiState, mouse: tuple[float, float], oy: float = 0.0, clip: Rect | None = None) -> str | None:
    """The `drop` picture of the tree under `mouse`: its rect moved by the scrolls it is in (`oy`), and inside their
    views (`clip`), as the drawer draws it."""
    match node:
        case Picture(drop=True):
            rect = Rect(node.rect.x, node.rect.y + oy, node.rect.width, node.rect.height)
            return node.id if rect.contains(*mouse) and (clip is None or clip.contains(*mouse)) else None
        case Scroll():
            view = Rect(node.rect.x, node.rect.y + oy, node.rect.width, node.rect.height).inset(SCROLL_BORDER)
            inner = view if clip is None else clip.overlap(view)
            return _drop_under(node.child, state, mouse, oy + state.scroll_offset(node.id), inner)
        case Column(children=children) | Row(children=children) | Grid(children=children):
            nodes: list[Node] = children
        case Table(rows=rows):
            nodes = [cell for row in rows for cell in row]
        case Split(left=left, right=right):
            nodes = [left, right]
        case Board(background=background, children=children):
            nodes = [background, *(placed.child for placed in children)]
        case Panel(child=child):
            nodes = [child]
        case _:
            return None
    return next((found for child in nodes if (found := _drop_under(child, state, mouse, oy, clip)) is not None), None)


def _focus_at(screen: Screen, theme: Theme, width: float, height: float, mouse: rl.Vector2) -> None:
    """A press focuses the topmost window under the mouse, or the screen when it lands outside every
    window. A press while the focused window's dropdown list is open belongs to that list, which may
    reach outside the window."""
    if screen.focus is not None and screen.focus.state.open_list is not None:
        return
    screen.focus_window(_window_at(screen, theme, width, height, mouse))


def _window_at(screen: Screen, theme: Theme, width: float, height: float, mouse: rl.Vector2) -> Window | None:
    """The topmost window under the mouse, if any."""
    for window in reversed(screen.windows):
        if _contains(_window_rect(window, theme, width, height), mouse):
            return window
    return None


def _screen_locked(screen: Screen, theme: Theme, width: float, height: float) -> bool:
    """A screen's tree is locked while a modal window is up, a dropdown list or a context menu is
    open, a split's bar is being dragged — and while the mouse is over a floating window, so a click
    on the window never reaches what lies beneath."""
    if screen.state.open_list is not None or screen.state.menu is not None:
        return True
    if screen.state.dragging_split is not None:  # letting go of the bar over a button must not click it
        return True
    if screen.state.dragging is not None and screen.state.dragging.started:  # nor of a dragged picture
        return True
    if any(window.modal for window in screen.windows):
        return True
    return _window_at(screen, theme, width, height, rl.get_mouse_position()) is not None


def _window_rect(window: Window, theme: Theme, width: float, height: float) -> rl.Rectangle:
    """Where the window is this frame, before any drag this frame moves it. A minimized window is
    placed where its open self would be, so its title bar does not jump when it collapses."""
    if window.size is not None:
        w, h = window.size
        w, h = min(w, width - 2 * PAD), min(h, height - 2 * PAD)
    else:
        w = min(window.width if window.width is not None else WINDOW_WIDTH, width - 2 * PAD)
        h = _title_height(window) + 2 * PAD + measure(window.root, w - 2 * PAD, theme.text_width)
        w, h = w, min(h, height - 2 * PAD)
    x, y = window.position or ((width - w) / 2, (height - h) / 2)
    if window.position is not None:  # kept on the screen when the screen shrinks under it
        x, y = max(min(x, width - w), 0.0), max(min(y, height - h), 0.0)
    if window.minimized:
        h = WINDOW_TITLE
    return rl.Rectangle(x, y, w, h)


def _draw_window(
    screen: Screen, window: Window, theme: Theme, width: float, height: float, events: list[Event], locked: bool, dragged: str | None
) -> "_Drawer | None":
    """Draw one window; the drawer of its content (the tooltip, menu and press under the mouse in it), None when it
    shows none (minimized, or closed this frame). `dragged`: the picture being dragged, drawn empty."""
    rect = _window_rect(window, theme, width, height)
    rect, resizing = _resized(window, rect, width, height, locked)
    if not resizing:  # a resize owns the mouse; the drag must not start from the grip
        was_minimized = window.minimized
        rect = _dragged(window, rect, width, height, locked)
        if window.minimized != was_minimized:  # a double-click on the title bar toggled it
            rect = _window_rect(window, theme, width, height)
    lock = locked or window.state.open_list is not None or resizing
    if lock:
        rl.gui_lock()
    clicked = _window_frame(rect, window, theme, window is screen.focus)
    if clicked == "close":
        events.append(Event(screen.id, window.id, None))
        screen.close_window()
    elif clicked == "minimize":
        window.minimized = not window.minimized
    drawer = None
    if not window.minimized and clicked != "close":
        title = _title_height(window)
        content = Rect(rect.x + PAD, rect.y + title + PAD, rect.width - 2 * PAD, rect.height - title - 2 * PAD)
        arrange(window.root, content, theme.text_width)
        drawer = _Drawer(theme, screen.id, window.state, events, dragged)
        drawer.draw(window.root)
    if lock:
        rl.gui_unlock()
    if window.resizable and not window.minimized:
        _draw_grip(rect, theme)
    if not locked and not window.minimized and window.state.open_list is not None:
        _draw_open_list(screen.id, window.root, window.state, theme, events)
    return drawer


def _resized(window: Window, rect: rl.Rectangle, width: float, height: float, locked: bool) -> tuple[rl.Rectangle, bool]:
    """Resize a window dragged by its bottom-right grip; the new size is remembered on the window
    and clamped to a minimum and to the screen. Returns the rect and whether a resize owns the
    mouse."""
    if not window.resizable or window.minimized or locked:
        if window._cursor_set:
            rl.set_mouse_cursor(rl.MouseCursor.MOUSE_CURSOR_DEFAULT)
            window._cursor_set = False
        return rect, False
    mouse = rl.get_mouse_position()
    grip = rl.Rectangle(rect.x + rect.width - GRIP, rect.y + rect.height - GRIP, GRIP, GRIP)
    resizing = window.resize_offset is not None
    if not resizing and rl.is_mouse_button_pressed(LEFT) and _contains(grip, mouse):
        window.resize_offset = (rect.x + rect.width - mouse.x, rect.y + rect.height - mouse.y)
        resizing = True
    if resizing:
        if rl.is_mouse_button_down(LEFT):
            minimum_h = _title_height(window) + 2 * PAD + ROW
            w = min(max(mouse.x + window.resize_offset[0] - rect.x, MIN_WINDOW), width - rect.x)
            h = min(max(mouse.y + window.resize_offset[1] - rect.y, minimum_h), height - rect.y)
            window.size = (w, h)
            rect = rl.Rectangle(rect.x, rect.y, w, h)
        else:
            window.resize_offset = None
            resizing = False
    if resizing or _contains(grip, mouse):
        rl.set_mouse_cursor(rl.MouseCursor.MOUSE_CURSOR_RESIZE_NWSE)
        window._cursor_set = True
    elif window._cursor_set:
        rl.set_mouse_cursor(rl.MouseCursor.MOUSE_CURSOR_DEFAULT)
        window._cursor_set = False
    return rect, resizing


def _draw_grip(rect: rl.Rectangle, theme: Theme) -> None:
    """The resize grip: three short diagonals in the bottom-right corner."""
    x1, y1 = rect.x + rect.width, rect.y + rect.height
    for i in (4.0, 9.0, 14.0):
        rl.draw_line_ex(rl.Vector2(x1 - i, y1 - 2), rl.Vector2(x1 - 2, y1 - i), 1.0, theme.muted)


def _title_height(window: Window) -> float:
    """A borderless window has no title bar."""
    return 0.0 if window.borderless else WINDOW_TITLE


def _window_frame(rect: rl.Rectangle, window: Window, theme: Theme, focused: bool) -> str | None:
    """The window's frame: the title bar with its buttons over a panel; "close"/"minimize" on a
    click. The focused window's title bar is drawn in raygui's focused colours, the others in its
    normal ones. A borderless window is just its background, or nothing with `backdrop` off. raygui's
    GuiWindowBox always has a close button, so the frame is composed from parts."""
    if window.borderless:
        if window.backdrop:
            rl.draw_rectangle_rec(rect, theme.background)
        return None
    state = rl.gui_get_state()
    if focused:
        rl.gui_set_state(rl.GuiState.STATE_FOCUSED)
    rl.gui_status_bar(rl.Rectangle(rect.x, rect.y, rect.width, WINDOW_TITLE), window.title)
    rl.gui_set_state(state)
    clicked = None
    x = rect.x + rect.width - 2 - TITLE_BUTTON
    if window.closeable:
        if rl.gui_button(rl.Rectangle(x, rect.y + 2, TITLE_BUTTON, TITLE_BUTTON), f"#{ICON_CLOSE}#"):
            clicked = "close"
        x -= TITLE_BUTTON + 2
    if window.minimizable:
        icon = ICON_RESTORE if window.minimized else ICON_MINIMIZE
        if rl.gui_button(rl.Rectangle(x, rect.y + 2, TITLE_BUTTON, TITLE_BUTTON), f"#{icon}#"):
            clicked = "minimize"
    if not window.minimized:
        # NULL, not "": GuiPanel draws a header bar for any title that is not NULL
        rl.gui_panel(rl.Rectangle(rect.x, rect.y + WINDOW_TITLE - 1, rect.width, rect.height - WINDOW_TITLE + 1), rl.ffi.NULL)
    return clicked


def _dragged(window: Window, rect: rl.Rectangle, width: float, height: float, locked: bool) -> rl.Rectangle:
    """Move a window being dragged; the position is remembered on the window, and clamped so the
    window stays wholly on screen. A framed window drags by its title bar (the buttons' corner
    excepted); a borderless one by anywhere inside it that is not a widget, so its controls keep
    their clicks."""
    if locked or not window.draggable:
        return rect
    mouse = rl.get_mouse_position()
    if window.drag_offset is None:
        # framed windows drag by the title bar, which holds no widgets
        can_drag = _contains(_drag_zone(window, rect), mouse) and not (window.borderless and _over_widget(window.root, mouse))
        if can_drag and rl.is_mouse_button_pressed(LEFT):
            if window.minimizable and not window.borderless:
                now = rl.get_time()
                if now - window._last_title_press < DOUBLE_CLICK:
                    window.minimized = not window.minimized
                    now = -1.0  # a third click right after is not another double-click
                window._last_title_press = now
            window.drag_offset = (mouse.x - rect.x, mouse.y - rect.y)
    if window.drag_offset is not None:
        if rl.is_mouse_button_down(LEFT):
            x = min(max(mouse.x - window.drag_offset[0], 0.0), width - rect.width)
            y = min(max(mouse.y - window.drag_offset[1], 0.0), height - rect.height)
            window.position = (x, y)
            return rl.Rectangle(x, y, rect.width, rect.height)
        window.drag_offset = None
    return rect


def _drag_zone(window: Window, rect: rl.Rectangle) -> rl.Rectangle:
    if window.borderless:
        return rect
    buttons = sum((window.closeable, window.minimizable))
    exclusion = buttons * (TITLE_BUTTON + 2) + 2 if buttons else 0.0  # the title bar buttons' corner
    return rl.Rectangle(rect.x, rect.y, rect.width - exclusion, WINDOW_TITLE)


_INTERACTIVE = (Button, CheckBox, Dropdown, ListView, Slider, TextBox, Toggle)


def _takes_mouse(node: Node, mouse: rl.Vector2) -> bool:
    """An interactive widget; a picture only when it is clickable, dragged or has a menu (otherwise the mouse over it
    is free); a split only over its bar."""
    if isinstance(node, Split):
        return _contains(rl.Rectangle(*split_bar(node)), mouse)
    if isinstance(node, Picture):
        return node.clickable or node.drag is not None or node.menu is not None
    return isinstance(node, _INTERACTIVE)


def _over_widget(root: Node, mouse: rl.Vector2, solid: bool = False) -> bool:
    """True when the mouse is over one of the tree's interactive widgets (their rects as laid out
    last frame, which is where they are drawn this frame). `solid` also counts what covers the
    screen behind it, so the mouse there is not over the game's world: a scroll (the wheel is its,
    and its content moves by its offset, so it is not searched) and a filled or `solid` panel."""
    for node in walk(root):
        inside = _contains(rl.Rectangle(node.rect.x, node.rect.y, node.rect.width, node.rect.height), mouse)
        covers = isinstance(node, Scroll) or (isinstance(node, Panel) and (node.fill or node.solid))
        if inside and (_takes_mouse(node, mouse) or (solid and covers)):
            return True
    return False


def _draw_open_list(owner: str, root: Node, state: UiState, theme: Theme, events: list[Event]) -> None:
    """The open dropdown's list, over everything else; a click outside closes it. It opens on the
    side of its button with more room, and a list too long for that side is cut, its last row "...".
    """
    open_list = state.open_list
    if open_list is None:
        return
    anchor = open_list.anchor
    bounds, shown, cut = _open_list_layout(open_list)
    chosen = _draw_choices(bounds, shown, cut, theme)
    if chosen is not None:
        _choose(owner, root, state, events, shown[chosen])
        return
    mouse = rl.get_mouse_position()
    clicked_outside = rl.is_mouse_button_pressed(LEFT) and not _contains(bounds, mouse) and not _contains(
        rl.Rectangle(anchor.x, anchor.y, anchor.width, anchor.height), mouse
    )
    if clicked_outside:
        state.open_list = None


class _ListLayout(NamedTuple):
    bounds: rl.Rectangle
    shown: tuple[str, ...]
    cut: bool  # a last row of "..." for the choices that did not fit


def _open_list_layout(open_list: OpenList) -> _ListLayout:
    """Where the open dropdown's list sits: on the side of its button with more room, cut when too long for it."""
    anchor = open_list.anchor
    screen_height = rl.get_screen_height()
    room = max(screen_height - (anchor.y + anchor.height + 2), anchor.y - 2)
    fits = max(2, int((room - 2) // POPUP_ROW))
    cut = len(open_list.choices) > fits
    shown = open_list.choices[: fits - 1] if cut else open_list.choices
    bounds = rl.Rectangle(anchor.x, anchor.y + anchor.height + 2, anchor.width, (len(shown) + cut) * POPUP_ROW + 2)
    if bounds.y + bounds.height > screen_height:  # open upwards near the bottom
        bounds.y = anchor.y - bounds.height - 2
    return _ListLayout(bounds, shown, cut)


def _choose(owner: str, root: Node, state: UiState, events: list[Event], choice: str) -> None:
    """The open dropdown takes `choice` (clicked, or activated by the keys or the pad), closes and says so."""
    open_list = state.open_list
    assert open_list is not None
    for node in walk(root):
        if isinstance(node, Dropdown) and node.id == open_list.id:
            node.current = node.choices.index(choice)
    state.open_list = None
    events.append(Event(owner, open_list.id, choice))


def _draw_menu(screen: Screen, theme: Theme, width: float, height: float, events: list[Event]) -> None:
    """The open context menu, beside the point it opened at, over everything else. A click on an
    enabled item chooses it; a press of either button outside it dismisses it, and is spent."""
    opened = screen.state.menu
    if opened is None:
        return
    menu = opened.menu
    size = menu_size(menu, height, theme.text_width)
    bounds = _menu_bounds(opened, size, width, height)
    x, y = bounds.x, bounds.y
    items = menu.items[: size.shown]
    chosen = _draw_choices(bounds, [item.text for item in items], size.cut, theme, [item.enabled for item in items], menu.title,
                           size.info)
    if menu.info is not None:  # drawn locked, as a tooltip is: it never takes the mouse
        top = y + 1 + (POPUP_ROW if menu.title is not None else 0.0)
        arrange(menu.info, Rect(x + 1, top, size.width - 2, size.info).inset(PAD), theme.text_width)
        rl.gui_lock()
        _Drawer(theme, "", _TOOLTIP_STATE, []).draw(menu.info)
        rl.gui_unlock()
        rl.draw_line_ex(rl.Vector2(x + 1, top + size.info - 1), rl.Vector2(x + size.width - 1, top + size.info - 1), 1.0, theme.muted)
    event = None
    if chosen is not None:
        event = screen.close_menu(items[chosen].id)
    elif (rl.is_mouse_button_pressed(LEFT) or rl.is_mouse_button_pressed(RIGHT)) and not _contains(bounds, rl.get_mouse_position()):
        event = screen.close_menu()
    if event is not None:
        events.append(event)


def _menu_bounds(opened: OpenMenu, size: MenuSize, width: float, height: float) -> rl.Rectangle:
    """Where an open context menu sits: beside the point it opened at, inside the window."""
    x, y = place_beside(opened.at, size.width, size.height, width, height, 0.0)
    return rl.Rectangle(x, y, size.width, size.height)


def _menu_item_rect(opened: OpenMenu, theme: Theme, width: float, height: float, index: int) -> rl.Rectangle:
    """The button of the open menu's `index`th item, as `_draw_choices` lays it out."""
    size = menu_size(opened.menu, height, theme.text_width)
    bounds = _menu_bounds(opened, size, width, height)
    top = bounds.y + 1 + (POPUP_ROW if opened.menu.title is not None else 0.0) + size.info
    return rl.Rectangle(bounds.x + 1, top + index * POPUP_ROW, bounds.width - 2, ROW)


def _draw_choices(
    bounds: rl.Rectangle,
    choices: Sequence[str],
    cut: bool,
    theme: Theme,
    enabled: Sequence[bool] | None = None,
    title: str | None = None,
    gap: float = 0.0,
) -> int | None:
    """A popup list (an open dropdown, a context menu): a bordered box of `POPUP_ROW` buttons, read
    from the left, under an optional title row and `gap` pixels left for a menu's info; the index of the
    choice clicked. A disabled choice is greyed and never chosen; `cut` adds a last row reading "..." for
    the choices that did not fit."""
    rl.draw_rectangle_rec(bounds, theme.background)
    rl.draw_rectangle_lines_ex(bounds, 1, theme.ink)
    top = bounds.y + 1
    if title is not None:
        theme.draw_text(title, bounds.x + PAD, top + (ROW - theme.text) / 2, theme.text, theme.muted)
        top += POPUP_ROW
        rl.draw_line_ex(rl.Vector2(bounds.x + 1, top - 1), rl.Vector2(bounds.x + bounds.width - 1, top - 1), 1.0, theme.muted)
    top += gap
    if cut:
        last = top + len(choices) * POPUP_ROW
        theme.draw_text("...", bounds.x + PAD, last + (ROW - theme.text) / 2, theme.text, theme.muted)
    chosen = None
    with _left_aligned_buttons():
        for i, choice in enumerate(choices):
            disabled = enabled is not None and not enabled[i]
            if disabled:
                rl.gui_disable()
            if rl.gui_button(rl.Rectangle(bounds.x + 1, top + i * POPUP_ROW, bounds.width - 2, ROW), choice) and not disabled:
                chosen = i
            if disabled:
                rl.gui_enable()
    return chosen


@contextmanager
def _disabled(disabled: bool) -> Iterator[None]:
    """raygui's controls drawn inside are greyed and take no input, when `disabled`."""
    if disabled:
        rl.gui_disable()
    try:
        yield
    finally:
        if disabled:
            rl.gui_enable()


@contextmanager
def _text_at(theme: Theme, size: int) -> Iterator[None]:
    """raygui's controls drawn inside write at `size`, in the theme's font loaded at it, and draw the icons in their
    text at its `icon_scale`. raygui's style is one for every control, so a widget under a `text_scale` (or with a
    `size`) sets it around its own call and puts the theme's back, leaving the rest of the screen as it was."""
    if size == theme.text:
        yield
        return
    font = rl.gui_get_font()
    if theme.font_path is not None:
        rl.gui_set_font(theme.font(size))
    rl.gui_set_style(rl.GuiControl.DEFAULT, rl.GuiDefaultProperty.TEXT_SIZE, size)  # after the font: it may set the size
    rl.gui_set_icon_scale(icon_scale(size))
    try:
        yield
    finally:
        rl.gui_set_font(font)
        rl.gui_set_style(rl.GuiControl.DEFAULT, rl.GuiDefaultProperty.TEXT_SIZE, theme.text)
        rl.gui_set_icon_scale(1)


@contextmanager
def _left_aligned_buttons(control: int = rl.GuiControl.BUTTON) -> Iterator[None]:
    """Buttons or toggles drawn inside read from the left, `PAD` in, as a dropdown and its list do."""
    alignment = rl.gui_get_style(control, rl.GuiControlProperty.TEXT_ALIGNMENT)
    padding = rl.gui_get_style(control, rl.GuiControlProperty.TEXT_PADDING)
    rl.gui_set_style(control, rl.GuiControlProperty.TEXT_ALIGNMENT, rl.GuiTextAlignment.TEXT_ALIGN_LEFT)
    rl.gui_set_style(control, rl.GuiControlProperty.TEXT_PADDING, int(PAD))
    try:
        yield
    finally:
        rl.gui_set_style(control, rl.GuiControlProperty.TEXT_ALIGNMENT, alignment)
        rl.gui_set_style(control, rl.GuiControlProperty.TEXT_PADDING, padding)


@contextmanager
def _error_buttons(theme: Theme) -> Iterator[None]:
    """Buttons drawn inside have their border and text in the theme's error colour, hovered and pressed too."""
    error = rl.color_to_int(theme.error)
    properties = [getattr(rl.GuiControlProperty, f"{part}_COLOR_{state}") for part in ("BORDER", "TEXT")
                  for state in ("NORMAL", "FOCUSED", "PRESSED")]
    kept = [rl.gui_get_style(rl.GuiControl.BUTTON, prop) for prop in properties]
    for prop in properties:
        rl.gui_set_style(rl.GuiControl.BUTTON, prop, error)
    try:
        yield
    finally:
        for prop, value in zip(properties, kept, strict=True):
            rl.gui_set_style(rl.GuiControl.BUTTON, prop, value)


def _draw_tooltip(tooltip: Tooltip, theme: Theme, width: float, height: float, mouse: rl.Vector2) -> None:
    """The tooltip's box beside the cursor, kept on screen, its widgets drawn locked: it never takes
    a click."""
    w, h = tooltip_size(tooltip, width, theme.text_width)
    x, y = place_beside((mouse.x, mouse.y), w, h, width, height, TOOLTIP_OFFSET)
    rect = rl.Rectangle(x, y, w, h)
    rl.draw_rectangle_rec(rect, theme.panel)
    rl.draw_rectangle_lines_ex(rect, 1, theme.ink)
    arrange(tooltip.root, Rect(x, y, w, h).inset(PAD), theme.text_width)
    rl.gui_lock()
    _Drawer(theme, "", _TOOLTIP_STATE, []).draw(tooltip.root)
    rl.gui_unlock()


def _draw_ghost(dragging: Dragging, theme: Theme, mouse: rl.Vector2) -> None:
    """The dragged picture, centred on the mouse at its size on screen, over everything; an outline when it has no
    texture yet."""
    w, h = dragging.ghost
    rect = rl.Rectangle(mouse.x - w / 2, mouse.y - h / 2, w, h)
    texture = dragging.texture
    if texture is None:
        rl.draw_rectangle_lines_ex(rect, 2, theme.ink)
        return
    source = rl.Rectangle(0, 0, texture.width, -texture.height if dragging.flipped else texture.height)
    rl.draw_texture_pro(texture, source, rect, rl.Vector2(0, 0), 0.0, rl.fade(rl.WHITE, GHOST_ALPHA))


def _contains(rect: rl.Rectangle, point: rl.Vector2) -> bool:
    return rect.x <= point.x < rect.x + rect.width and rect.y <= point.y < rect.y + rect.height


class _Drawer:
    """Draws one laid-out tree, collecting events and the tooltip of the picture, label or button under the mouse,
    and the menu of the picture there and a press on it that may start a drag (`pressed`). `ox`/`oy` shift every
    rect (a scroll's content); `clip` is the scroll's view: nodes outside it are skipped, nodes half in it are
    locked. `dragged` is the picture being dragged: it draws empty, and a `drop` picture under the mouse is
    outlined. `scale` is the text scale in force where the walk is, as the layout passes had it."""

    def __init__(self, theme: Theme, screen: str, state: UiState, events: list[Event], dragged: str | None = None) -> None:
        self.theme, self.screen, self.state, self.events, self.dragged = theme, screen, state, events, dragged
        self.ox = 0.0
        self.oy = 0.0
        self.clip: Rect | None = None
        self.tooltip: Tooltip | None = None
        self.menu: Menu | None = None
        self.pressed: Dragging | None = None
        self.scale = 1.0

    def draw(self, node: Node) -> None:
        outer = self.scale
        self.scale = scale_in(node, outer)
        self._draw(node)
        self.scale = outer

    def _size(self, node: Node) -> int:
        """The size `node`'s text is drawn at, as the layout measured it but from the theme's text size."""
        return text_size(node, self.scale, self.theme.text)

    def _draw(self, node: Node) -> None:
        rect = rl.Rectangle(node.rect.x + self.ox, node.rect.y + self.oy, node.rect.width, node.rect.height)
        match node:
            case Fill():
                pass
            case Label():
                self._label(node, rect)
            case Text():
                self._text(node, rect)
            case Separator():
                self._separator(node, rect)
            case Button():
                self._button(node, rect)
            case Toggle():
                self._toggle(node, rect)
            case CheckBox():
                self._check_box(node, rect)
            case Slider():
                self._slider(node, rect)
            case TextBox():
                self._text_box(node, rect)
            case Dropdown():
                self._dropdown(node, rect)
            case Progress():
                self._progress(node, rect)
            case ListView():
                self._list_view(node, rect)
            case Picture():
                self._picture(node, rect)
            case Swatch():
                self._swatch(node, rect)
            case Column(children=children) | Row(children=children) | Grid(children=children):
                for child in children:
                    self.draw(child)
            case Table(rows=rows):
                for row in rows:
                    for cell in row:
                        self.draw(cell)
            case Split():
                self.draw(node.left)
                self.draw(node.right)
                self._split(node)
            case Board():
                self.draw(node.background)
                for placed in node.children:
                    self.draw(placed.child)
            case Panel():
                self._panel(node, rect)
            case Scroll():
                self._scroll(node, rect)

    @contextmanager
    def _clipped(self, rect: rl.Rectangle) -> Iterator[bool]:
        """False when the rect is wholly outside the scroll view; a half-visible control is locked."""
        clip = self.clip
        if clip is not None:
            if rect.y + rect.height <= clip.y or rect.y >= clip.y + clip.height:
                yield False
                return
            if rect.y < clip.y or rect.y + rect.height > clip.y + clip.height:
                rl.gui_lock()
                try:
                    yield True
                finally:
                    rl.gui_unlock()
                return
        yield True

    def _emit(self, widget: str, value: bool | float | str | None) -> None:
        self.events.append(Event(self.screen, widget, value))

    def _label(self, spec: Label, rect: rl.Rectangle) -> None:
        with self._clipped(rect) as draw_it:
            if not draw_it:
                return
            color, size = self._tone(spec.tone), self._size(spec)
            if spec.wrap:
                for i, line in enumerate(wrap_text(spec.text, rect.width, size, self.theme.text_width)):
                    self.theme.draw_text(line, rect.x, rect.y + i * (size + 4), size, color)
            else:
                text = elided(spec.text, rect.width, size, self.theme.text_width) if spec.elide else spec.text
                x = rect.x
                if spec.align == "center":
                    x += (rect.width - self.theme.text_width(text, size)) / 2
                self.theme.draw_text(text, x, rect.y + (rect.height - size) / 2, size, color)
            if spec.tooltip is not None and not rl.gui_is_locked() and _contains(rect, rl.get_mouse_position()):
                self.tooltip = spec.tooltip

    def _tone(self, tone: Tone) -> rl.Color:
        theme = self.theme
        return {"ink": theme.ink, "muted": theme.muted, "error": theme.error, "ok": theme.ok, "warning": theme.warning,
                "info": theme.info}[tone]

    def _text(self, spec: Text, rect: rl.Rectangle) -> None:
        with self._clipped(rect) as draw_it:
            if not draw_it:
                return
            size = self._size(spec)
            for i, runs in enumerate(text_lines(spec, rect.width, self.theme.text_width, self.scale)):
                for run in runs:
                    self.theme.draw_text(run.text, rect.x + run.x, rect.y + i * (size + 4), size, self._tone(run.tone))
            if spec.tooltip is not None and not rl.gui_is_locked() and _contains(rect, rl.get_mouse_position()):
                self.tooltip = spec.tooltip

    def _separator(self, spec: Separator, rect: rl.Rectangle) -> None:
        with self._clipped(rect) as draw_it:
            if draw_it:
                y = int(rect.y + rect.height / 2)
                rl.draw_line(int(rect.x), y, int(rect.x + rect.width), y, self.theme.muted)

    def _button(self, spec: Button, rect: rl.Rectangle) -> None:
        with self._clipped(rect) as draw_it:
            if not draw_it:
                return
            with (_disabled(not spec.enabled), _left_aligned_buttons() if spec.align == "left" else nullcontext(),
                  _error_buttons(self.theme) if spec.invalid else nullcontext(), _text_at(self.theme, self._size(spec))):
                clicked = rl.gui_button(rect, spec.text)
            if spec.tooltip is not None and not rl.gui_is_locked() and _contains(rect, rl.get_mouse_position()):
                self.tooltip = spec.tooltip
            if clicked and spec.enabled:
                self._emit(spec.id, None)

    def _toggle(self, spec: Toggle, rect: rl.Rectangle) -> None:
        with self._clipped(rect) as draw_it:
            if not draw_it:
                return
            value = rl.ffi.new("bool *", spec.active)
            left = _left_aligned_buttons(rl.GuiControl.TOGGLE) if spec.align == "left" else nullcontext()
            with _disabled(not spec.enabled), left, _text_at(self.theme, self._size(spec)):
                rl.gui_toggle(rect, spec.text, value)
            if spec.tooltip is not None and not rl.gui_is_locked() and _contains(rect, rl.get_mouse_position()):
                self.tooltip = spec.tooltip
            if spec.enabled and value[0] != spec.active:
                spec.active = value[0]
                self._emit(spec.id, spec.active)

    def _check_box(self, spec: CheckBox, rect: rl.Rectangle) -> None:
        with self._clipped(rect) as draw_it:
            if not draw_it:
                return
            side = CHECK * widget_scale(spec, self.scale)
            box = rl.Rectangle(rect.x, rect.y + (rect.height - side) / 2, side, side)
            value = rl.ffi.new("bool *", spec.checked)
            with _disabled(not spec.enabled), _text_at(self.theme, self._size(spec)):
                rl.gui_check_box(box, spec.text, value)
            if spec.enabled and value[0] != spec.checked:
                spec.checked = value[0]
                self._emit(spec.id, spec.checked)

    def _slider(self, spec: Slider, rect: rl.Rectangle) -> None:
        with self._clipped(rect) as draw_it:
            if not draw_it:
                return
            # raygui draws a slider's texts *outside* its bounds, so label and value are drawn here
            text = self._size(spec)
            label_w = self.theme.text_width(spec.text, text) + GAP if spec.text else 0.0
            widest = max(self.theme.text_width(spec.format.format(end), text) for end in (spec.minimum, spec.maximum))
            value_w = widest + GAP
            value = rl.ffi.new("float *", spec.value)
            before = value[0]  # the value as raygui's float holds it: comparing the spec's double would see a move
            bar = rl.Rectangle(rect.x + label_w, rect.y, rect.width - label_w - value_w, rect.height)
            pressed = rl.is_mouse_button_pressed(LEFT) and not rl.gui_is_locked() and _contains(bar, rl.get_mouse_position())
            if pressed and spec.enabled:
                self.state.sliding = spec.id  # held until the button is let go (`UiState.begin`)
            with _disabled(not spec.enabled):
                rl.gui_slider(bar, "", "", value, spec.minimum, spec.maximum)
            if spec.tooltip is not None and not rl.gui_is_locked() and _contains(rect, rl.get_mouse_position()):
                self.tooltip = spec.tooltip
            middle = rect.y + (rect.height - text) / 2
            if spec.text:
                self.theme.draw_text(spec.text, rect.x, middle, text, self.theme.ink)
            self.theme.draw_text(spec.format.format(value[0]), rect.x + rect.width - value_w + GAP, middle, text, self.theme.muted)
            if spec.enabled and value[0] != before:
                spec.value = value[0]
                self._emit(spec.id, spec.value)

    def _text_box(self, spec: TextBox, rect: rl.Rectangle) -> None:
        """A box showing `text`; the event fires with what was typed once the user leaves the box. An
        invalid box's border is drawn over raygui's in the error colour; a disabled box never edits. A
        submit box fires on Enter instead, clears itself and stays focused; left, it keeps a draft."""
        state = self.state
        with self._clipped(rect) as draw_it:
            if not draw_it:
                return
            if spec.id == state._editing and spec.enabled:
                with _text_at(self.theme, self._size(spec)):
                    entered_box = rl.gui_text_box(rect, state._buffer, BUFFER, True)
                if entered_box:
                    text = rl.ffi.string(state._buffer).decode("utf-8", "replace")
                    entered = rl.is_key_pressed(rl.KeyboardKey.KEY_ENTER) or rl.is_key_pressed(rl.KeyboardKey.KEY_KP_ENTER)
                    if spec.submit and entered:
                        state._buffer[0] = b"\0"
                        state.drafts.pop(spec.id, None)
                        if text.strip():
                            self._emit(spec.id, text)
                        return
                    if state.editing == spec.id:
                        state.editing = None
                    if spec.submit:
                        state.drafts[spec.id] = text
                        if not text:
                            state.drafts.pop(spec.id)
                        return
                    spec.text = text
                    self._emit(spec.id, text)
            else:
                text = state.drafts.get(spec.id, spec.text) if spec.submit else spec.text
                shown = rl.ffi.new(f"char[{BUFFER}]", text.encode()[: BUFFER - 1])
                with _disabled(not spec.enabled), _text_at(self.theme, self._size(spec)):
                    clicked = rl.gui_text_box(rect, shown, BUFFER, False)
                if clicked and spec.enabled:
                    state.edit(spec)
            if spec.invalid:
                rl.draw_rectangle_lines_ex(rect, 2, self.theme.error)

    def _dropdown(self, spec: Dropdown, rect: rl.Rectangle) -> None:
        """A button showing the current choice; the choice comes back from the open list."""
        state = self.state
        with self._clipped(rect) as draw_it:
            if not draw_it:
                return
            is_open = state.open_list is not None and state.open_list.id == spec.id
            current = spec.choices[spec.current] if spec.choices else ""
            # the choice reads from the left and the arrow sits at the right, as in a native dropdown
            size = self._size(spec)
            with _disabled(not spec.enabled), _left_aligned_buttons(), _text_at(self.theme, size):
                clicked = rl.gui_button(rect, current)
            icon = ICON * icon_scale(size)
            icon_x, icon_y = rect.x + rect.width - PAD - icon, rect.y + (rect.height - icon) / 2
            arrow = self.theme.ink if spec.enabled else self.theme.muted
            rl.gui_draw_icon(ARROW_UP if is_open else ARROW_DOWN, int(icon_x), int(icon_y), icon_scale(size), arrow)
            if spec.tooltip is not None and not rl.gui_is_locked() and _contains(rect, rl.get_mouse_position()):
                self.tooltip = spec.tooltip
            if clicked and spec.enabled:
                state.open_list = OpenList(spec.id, Rect(rect.x, rect.y, rect.width, rect.height), spec.choices, spec.current)

    def _progress(self, spec: Progress, rect: rl.Rectangle) -> None:
        """raygui's bar, or, vertical or coloured (raygui's has neither), the theme's panel filled by the value in
        the colour (the theme's info without one), from the bottom when vertical, in a muted frame."""
        with self._clipped(rect) as draw_it:
            if not draw_it:
                return
            if spec.vertical or spec.colour is not None:
                value = min(max(spec.value, 0.0), 1.0)
                colour = rl.Color(*spec.colour, 255) if spec.colour is not None else self.theme.info
                rl.draw_rectangle_rec(rect, self.theme.panel)
                if spec.vertical:
                    filled = rect.height * value
                    rl.draw_rectangle_rec(rl.Rectangle(rect.x, rect.y + rect.height - filled, rect.width, filled), colour)
                else:
                    rl.draw_rectangle_rec(rl.Rectangle(rect.x, rect.y, rect.width * value, rect.height), colour)
                rl.draw_rectangle_lines_ex(rect, 1, self.theme.muted)
            else:
                rl.gui_progress_bar(rect, "", "", rl.ffi.new("float *", spec.value), 0.0, 1.0)
            if spec.tooltip is not None and not rl.gui_is_locked() and _contains(rect, rl.get_mouse_position()):
                self.tooltip = spec.tooltip

    def _list_view(self, spec: ListView, rect: rl.Rectangle) -> None:
        with self._clipped(rect) as draw_it:
            if not draw_it:
                return
            active = rl.ffi.new("int *", spec.selected)
            rl.gui_list_view(rect, ";".join(spec.items), self.state.list_scroll_ptr(spec.id), active)
            if active[0] != spec.selected:
                spec.selected = active[0]
                if 0 <= active[0] < len(spec.items):
                    self._emit(spec.id, spec.items[active[0]])

    def _picture(self, spec: Picture, rect: rl.Rectangle) -> None:
        """The texture fitted into the rect (an empty frame without one, or while it is dragged — with its `caption`
        inside, if it has one); a clickable picture is outlined while the mouse is over it, and a press on it emits
        its event. Its tooltip and menu
        are the drawer's while the mouse is over it, unlocked; a press on a picture with `drag` may start one (its
        click, if clickable, comes on release). While a drag runs, the `drop` picture under the mouse is outlined."""
        with self._clipped(rect) as draw_it:
            if not draw_it:
                return
            frame = self.theme.accent if spec.accent else self.theme.muted
            if spec.texture is None or spec.id == self.dragged:
                rl.draw_rectangle_lines_ex(rect, 1, frame)
                if spec.caption and spec.id != self.dragged:
                    lines = wrap_text(spec.caption, max(rect.width - 2 * GAP, 10.0), self.theme.small, self.theme.text_width)
                    top = rect.y + (rect.height - len(lines) * (self.theme.small + 4)) / 2
                    for i, line in enumerate(lines):
                        x = rect.x + (rect.width - self.theme.text_width(line, self.theme.small)) / 2
                        self.theme.draw_text(line, x, top + i * (self.theme.small + 4) + 2, self.theme.small, self.theme.muted)
            else:
                texture = spec.texture
                source = rl.Rectangle(0, 0, texture.width, -texture.height if spec.flipped else texture.height)
                fitted = picture_rect(spec, Rect(rect.x, rect.y, rect.width, rect.height))
                tint = rl.Color(*spec.tint) if spec.tint is not None else rl.WHITE
                rl.draw_texture_pro(texture, source, rl.Rectangle(*fitted), rl.Vector2(0, 0), 0.0, tint)
                if spec.framed:
                    rl.draw_rectangle_lines_ex(rect, 1, frame)
            mouse = rl.get_mouse_position()
            if not _contains(rect, mouse):
                return
            if self.dragged is not None and spec.drop and (self.clip is None or self.clip.contains(mouse.x, mouse.y)):
                rl.draw_rectangle_lines_ex(rect, 2, self.theme.ink)
            if rl.gui_is_locked():
                return
            if spec.tooltip is not None:
                self.tooltip = spec.tooltip
            if spec.menu is not None:
                self.menu = spec.menu
            if spec.drag is not None:
                if rl.is_mouse_button_pressed(LEFT):
                    self.pressed = Dragging(spec.id, spec.drag, spec.texture, spec.flipped, (rect.width, rect.height),
                                            spec.clickable, (mouse.x, mouse.y))
                if spec.clickable:
                    rl.draw_rectangle_lines_ex(rect, 2, self.theme.ink)
                return
            if not spec.clickable:
                return
            rl.draw_rectangle_lines_ex(rect, 2, self.theme.ink)
            if rl.is_mouse_button_pressed(LEFT):
                self._emit(spec.id, None)

    def _split(self, spec: Split) -> None:
        """The bar: a short grip in its middle. A press on it (when not locked) starts a drag, which moves the
        bar with the mouse while held and emits the new ratio when let go; the cursor shows it can."""
        state, mouse = self.state, rl.get_mouse_position()
        bar = split_bar(spec)
        bar = rl.Rectangle(bar.x + self.ox, bar.y + self.oy, bar.width, bar.height)
        over = _contains(bar, mouse) and not rl.gui_is_locked()
        if over and rl.is_mouse_button_pressed(LEFT):
            state.dragging_split = spec.id
        dragging = state.dragging_split == spec.id
        if dragging:
            if rl.is_mouse_button_down(LEFT):
                spec.ratio = state.splits[spec.id] = split_ratio(spec, mouse.x - self.ox)
            else:
                state.dragging_split = None
                dragging = False
                self._emit(spec.id, spec.ratio)
        if over or dragging:
            rl.set_mouse_cursor(rl.MouseCursor.MOUSE_CURSOR_RESIZE_EW)
            state.split_cursor = True
        elif state.split_cursor and state.dragging_split is None:
            rl.set_mouse_cursor(rl.MouseCursor.MOUSE_CURSOR_DEFAULT)
            state.split_cursor = False
        middle_x, middle_y = bar.x + bar.width / 2, bar.y + bar.height / 2
        colour = self.theme.ink if over or dragging else self.theme.muted
        rl.draw_line_ex(rl.Vector2(middle_x, middle_y - 16), rl.Vector2(middle_x, middle_y + 16), 2.0, colour)

    def _swatch(self, spec: Swatch, rect: rl.Rectangle) -> None:
        with self._clipped(rect) as draw_it:
            if not draw_it:
                return
            box = rl.Rectangle(rect.x, rect.y + (rect.height - spec.side) / 2, spec.side, spec.side)
            rl.draw_rectangle_rec(box, rl.Color(*spec.colour, 255))
            rl.draw_rectangle_lines_ex(box, 1, self.theme.ink)

    def _panel(self, spec: Panel, rect: rl.Rectangle) -> None:
        strip = title_strip(spec, self.scale)
        box = rl.Rectangle(rect.x, rect.y + strip, rect.width, rect.height - strip)
        if spec.fill:  # the title's top half too, or it straddles the fill's edge
            rl.draw_rectangle_rec(rect, self.theme.panel)
        elif spec.backdrop > 0:
            rl.draw_rectangle_rec(rect, rl.fade(self.theme.background, spec.backdrop))
        if spec.title or not spec.backdrop:
            with _text_at(self.theme, self._size(spec)):
                rl.gui_group_box(box, spec.title or rl.ffi.NULL)  # "" would leave a gap in the top line
        self.draw(spec.child)

    def _scroll(self, spec: Scroll, rect: rl.Rectangle) -> None:
        scroll = self.state.scroll_ptr(spec.id)
        child = spec.child
        content = rl.Rectangle(0, 0, child.rect.width + 2 * spec.pad, child.rect.height + 2 * spec.pad)
        view = rl.ffi.new("Rectangle *")
        rl.gui_scroll_panel(rect, rl.ffi.NULL, content, scroll, view)
        mouse = rl.get_mouse_position()
        low = min(0.0, view[0].height - content.height)
        if self.state.open_list is None and _contains(rect, mouse):
            scroll[0].y = min(max(scroll[0].y + rl.get_mouse_wheel_move() * WHEEL_STEP, low), 0.0)
        if spec.follow:
            scroll[0].y = self.state.follow(spec.id, scroll[0].y, low)
        visible = view[0]
        rl.begin_scissor_mode(int(visible.x), int(visible.y), int(visible.width), int(visible.height))
        offset, clip = self.oy, self.clip
        self.oy += scroll[0].y
        self.clip = Rect(visible.x, visible.y, visible.width, visible.height)
        self.draw(child)
        self.oy, self.clip = offset, clip
        rl.end_scissor_mode()
