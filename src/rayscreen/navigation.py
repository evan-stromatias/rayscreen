"""Moving through a screen without the mouse: one widget has the focus, a move takes it to the next widget that way,
and activating it does what a click would. No raylib: the app says what was asked this frame (`Nav`), from its own
keys and pad, and `draw.frame` applies it.

- Only enabled buttons, toggles, check boxes, dropdowns, sliders and text boxes take the focus, and the pictures that do something
  (`clickable`, or with a `menu`: an item in a grid, whose activation opens its menu by the picture). An open context
  menu takes every move first: up and down its enabled items (`menu_step`), activating chooses one, back dismisses it.
- Activating a dropdown opens its list, which then takes every move as a menu does (`list_step`); left and right move
  a focused slider by its step (`slid`) instead of the focus. Activating a text box edits it in place, or, for a
  `keyboard` box, emits its event for the app to open a `KeyboardWindow`.
- The focused window sees the nav first (`Window.navigate`): an on-screen keyboard reads `delete`, `space`, `shift`
  and `confirm` from it, and what was typed on a physical keyboard (`Typed`), before the rest moves the focus.
- A move is spatial, from where the widgets are on screen (moved by the scrolls they are in), so a column, a row and
  a grid move as they look; the focus's scroll then moves to show it (`into_view`).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, NamedTuple

from rayscreen.geometry import Rect
from rayscreen.specs import SCROLL_BORDER, Button, CheckBox, Dropdown, MenuItem, Node, Picture, Scroll, Slider, TextBox, Toggle, children

type Direction = Literal["up", "down", "left", "right"]
type Focusable = Button | Toggle | CheckBox | Dropdown | Slider | TextBox | Picture
type ScrollOffset = Callable[[str], float]  # a scroll's offset by its id (`UiState.scroll_offset`)
ACROSS_WEIGHT = 2.0  # a step off to the side counts double: the widget straight that way wins
SLIDER_STEPS = 20  # a slider without its own step moves a twentieth of its range a press


@dataclass(frozen=True, slots=True)
class Nav:
    """What the keys or the pad asked of the menus this frame: a `move`, a click on the focused widget (`activate`),
    or Esc (`back`). The rest are for an on-screen keyboard (`KeyboardWindow`), which a pad types with: `delete`
    the last character, type a `space`, `shift` the keys, `confirm` the text. Elsewhere they do nothing, so an app
    can fill them from its pad every frame."""

    move: Direction | None = None
    activate: bool = False
    back: bool = False
    delete: bool = False
    space: bool = False
    shift: bool = False
    confirm: bool = False

    @property
    def any(self) -> bool:
        return self.move is not None or self.activate or self.back or self.delete or self.space or self.shift or self.confirm


class Typed(NamedTuple):
    """What was typed on a physical keyboard this frame, for the focused window that takes typing (`Window.typing`):
    the characters, and whether Backspace and Enter were pressed. `draw.frame` reads it from raylib."""

    text: str = ""
    backspace: bool = False
    enter: bool = False

    @property
    def any(self) -> bool:
        return bool(self.text) or self.backspace or self.enter


class Steered(NamedTuple):
    """What a focused window made of the nav (`Window.navigate`): the nav left for moving and clicking its focus, and
    the ids of its own widgets to click, as if the mouse had (an on-screen keyboard's OK for the pad's Start)."""

    nav: Nav
    clicks: tuple[str, ...] = ()


class Placed(NamedTuple):
    """A widget that can take the focus, where it is on screen, and the innermost scroll it is in."""

    node: Focusable
    rect: Rect
    scroll: Scroll | None


def focusables(root: Node, offset: ScrollOffset = lambda _: 0.0) -> list[Placed]:
    """The widgets that can take the focus, in tree order, each moved by the offsets of the scrolls it is in."""
    found: list[Placed] = []

    def visit(node: Node, oy: float, scroll: Scroll | None) -> None:
        if (isinstance(node, (Button, Toggle, CheckBox, Dropdown, Slider, TextBox)) and node.enabled) or (
                isinstance(node, Picture) and (node.clickable or node.menu is not None)):
            x, y, width, height = node.rect
            found.append(Placed(node, Rect(x, y + oy, width, height), scroll))
        if isinstance(node, Scroll):
            oy, scroll = oy + offset(node.id), node
        for child in children(node):
            visit(child, oy, scroll)

    visit(root, 0.0, None)
    return found


def _view(scroll: Scroll) -> Rect:
    """A scroll's view on screen: its bounds inset by raygui's border. Where it was arranged: a scroll inside another
    is not followed (no screen nests them)."""
    return Rect(*scroll.rect).inset(SCROLL_BORDER)


def visible(placed: Placed) -> bool:
    """Whether the widget lies wholly inside its scroll's view (always, outside a scroll)."""
    if placed.scroll is None:
        return True
    view = _view(placed.scroll)
    return view.y <= placed.rect.y and placed.rect.y + placed.rect.height <= view.y + view.height


def into_view(placed: Placed, offset: float) -> float:
    """The offset (at most 0) its scroll needs, from `offset`, to show the widget whole with the scroll's `pad`
    around it: as little a move as does it, so stepping down a list moves it a row at a time."""
    scroll = placed.scroll
    if scroll is None:
        return offset
    view = _view(scroll)
    top, bottom = placed.rect.y - scroll.pad, placed.rect.y + placed.rect.height + scroll.pad
    if top < view.y:
        offset += view.y - top
    elif bottom > view.y + view.height:
        offset -= bottom - (view.y + view.height)
    lowest = min(0.0, view.height - (scroll.child.rect.height + 2 * scroll.pad))
    return min(max(offset, lowest), 0.0)


def _centre(rect: Rect) -> tuple[float, float]:
    return rect.x + rect.width / 2, rect.y + rect.height / 2


def step(nodes: list[Placed], focused: str | None, move: Direction) -> str | None:
    """Where `move` takes the focus from `focused`: the first widget when nothing has it (or what had it is gone);
    else the nearest widget whose centre lies that way on screen, or `focused` itself at an edge."""
    if not nodes:
        return None
    current = next((placed for placed in nodes if placed.node.id == focused), None)
    if current is None:
        return nodes[0].node.id
    x, y = _centre(current.rect)
    best, best_score = current.node.id, float("inf")
    for placed in nodes:
        if placed is current:
            continue
        nx, ny = _centre(placed.rect)
        along, across = {"up": (y - ny, nx - x), "down": (ny - y, nx - x),
                         "left": (x - nx, ny - y), "right": (nx - x, ny - y)}[move]
        if along <= 0:
            continue
        score = along + ACROSS_WEIGHT * abs(across)
        if score < best_score:
            best, best_score = placed.node.id, score
    return best


def menu_step(items: list[MenuItem], focused: int | None, move: Direction) -> int | None:
    """Where a move takes the focus in a context menu's items: up or down to the next enabled item, staying at the
    ends; the first enabled one when nothing has it. Left and right stay. None when no item is enabled."""
    enabled = [i for i, item in enumerate(items) if item.enabled]
    if not enabled:
        return None
    if focused not in enabled:
        return enabled[0]
    at = enabled.index(focused)
    if move == "up":
        return enabled[max(0, at - 1)]
    if move == "down":
        return enabled[min(len(enabled) - 1, at + 1)]
    return focused



def list_step(count: int, focused: int | None, move: Direction) -> int | None:
    """Where a move takes the focus in an open dropdown's `count` choices: up or down one, staying at the ends; the
    first when nothing has it. Left and right stay. None when there is no choice."""
    if count == 0:
        return None
    if focused is None or not 0 <= focused < count:
        return 0
    if move == "up":
        return max(0, focused - 1)
    if move == "down":
        return min(count - 1, focused + 1)
    return focused


def slid(slider: Slider, move: Direction) -> float | None:
    """The value left or right takes a focused slider to, one step (its own, or a `SLIDER_STEPS`th of its range) and
    kept in its range; None for up and down, which move the focus."""
    if move not in ("left", "right"):
        return None
    by = slider.step if slider.step is not None else (slider.maximum - slider.minimum) / SLIDER_STEPS
    value = slider.value + (by if move == "right" else -by)
    return min(max(value, slider.minimum), slider.maximum)
