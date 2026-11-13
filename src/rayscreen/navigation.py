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
- A move follows the tree: left and right go along the focus's `Row` (or `Split`), up and down along its `Column`, to
  the next child that way with anything focusable in it, so a row keeps the focus however far its next widget is.
  A `Table` is a column of its rows. Inside a `Grid` or `Board`, and on entering a child, it is spatial, from where
  the widgets are on screen (moved by the scrolls they are in). The focus's scroll then moves to show it
  (`into_view`).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, NamedTuple

from rayscreen.geometry import Rect
from rayscreen.specs import (
    SCROLL_BORDER,
    Board,
    Button,
    CheckBox,
    Column,
    Dropdown,
    Grid,
    MenuItem,
    Node,
    Picture,
    Row,
    Scroll,
    Slider,
    Split,
    Table,
    TextBox,
    Toggle,
    children,
)

type Direction = Literal["up", "down", "left", "right"]
type Focusable = Button | Toggle | CheckBox | Dropdown | Slider | TextBox | Picture
type ScrollOffset = Callable[[str], float]  # a scroll's offset by its id (`UiState.scroll_offset`)
type Axis = Literal["row", "column", "free", "none"]  # which moves a container takes: see `step`
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
    """A widget that can take the focus (not a `Board`'s `specs.Placed`), where it is on screen, the innermost scroll
    it is in, and where it is in the tree: `path` holds the child index taken at each container from the root down,
    and `axes` the kind of each of those containers (`container_axis`), so `path[:depth]` names the container at
    `depth` and `path[depth]` the child of it the widget is in."""

    node: Focusable
    rect: Rect
    scroll: Scroll | None
    path: tuple[int, ...] = ()
    axes: tuple[Axis, ...] = ()


def container_axis(node: Node) -> Axis:
    """Which moves a container takes between its children: a `Row` or `Split` left and right, a `Column` up and down,
    a `Grid` or `Board` any way by where its widgets are (`free`), and a `Panel` or `Scroll` none. A `Table` is
    walked as a column of rows (`focusables`), so it takes both, each along its own line."""
    match node:
        case Row() | Split():
            return "row"
        case Column():
            return "column"
        case Grid() | Board():
            return "free"
    return "none"


def focusables(root: Node, offset: ScrollOffset = lambda _: 0.0) -> list[Placed]:
    """The widgets that can take the focus, in tree order, each moved by the offsets of the scrolls it is in."""
    found: list[Placed] = []

    def visit(node: Node, oy: float, scroll: Scroll | None, path: tuple[int, ...], axes: tuple[Axis, ...]) -> None:
        if (isinstance(node, (Button, Toggle, CheckBox, Dropdown, Slider, TextBox)) and node.enabled) or (
                isinstance(node, Picture) and (node.clickable or node.menu is not None)):
            x, y, width, height = node.rect
            found.append(Placed(node, Rect(x, y + oy, width, height), scroll, path, axes))
        if isinstance(node, Scroll):
            oy, scroll = oy + offset(node.id), node
        if isinstance(node, Table):  # a column of rows, so a form's names and boxes move as its lines look
            for r, cells in enumerate(node.rows):
                for c, cell in enumerate(cells):
                    visit(cell, oy, scroll, (*path, r, c), (*axes, "column", "row"))
            return
        axis = container_axis(node)
        for index, child in enumerate(children(node)):
            visit(child, oy, scroll, (*path, index), (*axes, axis))

    visit(root, 0.0, None, (), ())
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


def _gap(low: float, size: float, other_low: float, other_size: float) -> float:
    """How far apart two spans are along one axis: 0 where they overlap."""
    return max(0.0, other_low - (low + size), low - (other_low + other_size))


def _score(current: Rect, other: Rect, move: Direction) -> tuple[float, float]:
    """How far `other` lies along `move` from `current` (between the centres; negative when behind) and how far to
    the side (the gap between the edges, none where they overlap: a wide widget straight below, a text box beside its
    label, is not passed over for a small one whose centre happens to be nearer)."""
    x, y = _centre(current)
    nx, ny = _centre(other)
    along = {"up": y - ny, "down": ny - y, "left": x - nx, "right": nx - x}[move]
    across = (_gap(current.x, current.width, other.x, other.width) if move in ("up", "down")
              else _gap(current.y, current.height, other.y, other.height))
    return along, across


def _nearest_that_way(candidates: list[Placed], current: Placed, move: Direction) -> str | None:
    """The candidate whose centre lies `move` of the focus's with the least distance that way plus `ACROSS_WEIGHT`
    times the gap to the side, ties to the first in tree order (the left one of a row); None when none lies that way."""
    best, best_score = None, float("inf")
    for placed in candidates:
        if placed is current:
            continue
        along, across = _score(current.rect, placed.rect, move)
        if along <= 0:
            continue
        score = along + ACROSS_WEIGHT * across
        if score < best_score:
            best, best_score = placed.node.id, score
    return best


def _entered(candidates: list[Placed], current: Placed, depth: int, move: Direction) -> str:
    """Where the focus lands in the child of a row or a column that the move goes into (the `candidates` are its
    widgets, the child at `depth + 1` of their paths).

    - The tree first: a container in it that runs the way of the move (a `Column`, or a `Table`'s lines, moving down)
      is entered at its first child that way with anything focusable in it, so a move down into a form lands on its
      top line and not on a widget further down that lies nearer to the side. A `Panel` or `Scroll` is passed through.
    - Then the most level: once the child runs across the move (a `Row` moving down, a column of buttons moving
      right) or is the widget itself, its widget with the least gap to the side of the focus, then the nearest along
      the move, ties to the first in tree order. Level first, because the gaps between lines are small beside the
      widths along them: scored as `_nearest_that_way` does, left into a form from beside its second line would land
      at the end of its first. Its centre need not lie that way: the tree has chosen the way already."""
    wanted: Axis = "row" if move in ("left", "right") else "column"
    forward = move in ("right", "down")
    level = depth + 1
    while all(len(placed.path) > level for placed in candidates) and candidates[0].axes[level] in (wanted, "none"):
        indices = {placed.path[level] for placed in candidates}
        child = min(indices) if forward else max(indices)
        candidates = [placed for placed in candidates if placed.path[level] == child]
        level += 1
    best, best_score = candidates[0].node.id, (float("inf"), float("inf"))
    for placed in candidates:
        along, across = _score(current.rect, placed.rect, move)
        score = (across, abs(along))
        if score < best_score:
            best, best_score = placed.node.id, score
    return best


def _next_child(inside: list[Placed], current: Placed, depth: int, move: Direction) -> str | None:
    """Where a row or a column takes the focus: into its next child that way (right and down go up the child
    indices) that has anything focusable in it; None past its last."""
    at = current.path[depth]
    forward = move in ("right", "down")
    indices = {placed.path[depth] for placed in inside if (placed.path[depth] > at if forward else placed.path[depth] < at)}
    if not indices:
        return None
    child = min(indices) if forward else max(indices)
    return _entered([placed for placed in inside if placed.path[depth] == child], current, depth, move)


def step(nodes: list[Placed], focused: str | None, move: Direction) -> str | None:
    """Where `move` takes the focus from `focused`: the first widget when nothing has it (or what had it is gone).

    - The tree first: from the focus's innermost container outwards, the first that takes the move and has a widget
      that way decides. A `Row` or `Split` takes left and right, a `Column` up and down, into the next child that way
      with anything focusable in it (`_entered`: its first line that way, then its widget most level with the
      focus); a `Table` is a `Column` of `Row`s, one a line. A `Grid` or `Board` takes any move, to its nearest widget
      that way on screen. A `Panel` or `Scroll` passes the move outwards.
    - The tree has the last word: when a container around the focus takes that kind of move but none has a widget
      that way (the end of a row), the focus stays, and does not jump to a widget that only looks nearer.
    - On screen only where the tree says nothing: when no container around the focus takes that kind of move, the
      nearest widget that way among all of them, or `focused` itself at an edge.
    - Nearest: the distance that way between the centres plus `ACROSS_WEIGHT` times the gap to the side between the
      two widgets' edges (`_score`); ties go to the first in tree order."""
    if not nodes:
        return None
    current = next((placed for placed in nodes if placed.node.id == focused), None)
    if current is None:
        return nodes[0].node.id
    wanted: Axis = "row" if move in ("left", "right") else "column"
    taken = False
    for depth in range(len(current.path) - 1, -1, -1):
        axis = current.axes[depth]
        if axis not in (wanted, "free"):
            continue
        taken = True
        prefix = current.path[:depth]
        inside = [placed for placed in nodes if placed is not current and placed.path[:depth] == prefix and len(placed.path) > depth]
        target = _nearest_that_way(inside, current, move) if axis == "free" else _next_child(inside, current, depth, move)
        if target is not None:
            return target
    if taken:
        return current.node.id
    target = _nearest_that_way(nodes, current, move)
    return target if target is not None else current.node.id


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
