"""The specs a screen's tree is built from: widgets and containers, plain dataclasses with no raylib.

Sizes default to the metrics below, so screens built from defaults line up. Any node's `weight`
shares out the space a `Column` or `Row` has left (0: just its natural size). The layout's arrange
pass fills in every `rect`.

A `Column` or `Row` with a `text_scale` draws everything under it in larger (or smaller) text, until a container
sets its own (a screen's options pane in large type for a TV, the rest as it is):

- Text: a `Label`'s or a `Text`'s `size`, a widget's text (the theme's `TEXT`) and a `Panel`'s title, times the
  scale in force and rounded to whole pixels; a widget's own `size` (`Button`, `Toggle`, `Slider`, `TextBox`) wins
  over it. The font is drawn on a 16 px grid, so whole scales are the crispest. Icons in a widget's text grow by
  whole steps of raygui's icon scale, the nearest to the text's size.
- Rows: a widget's default height (`height=None`: `ROW`) grows with its text, so the text fits, as a check box's
  box (`CHECK`) does; a height given explicitly stays as given. Widths sized to their text (`MIN_BUTTON`) measure
  at its size.
- What stays: the gaps and pads, pictures, bars and swatches, a `ListView`'s rows, and the popups (an open
  dropdown's list, tooltips, menus), drawn at the theme's size.

`Tooltip` and `Menu` are not nodes: a screen's `hover` and `menu` hooks return them for what lies
under the mouse (an entity in the game's world), and rayscreen draws them over everything.
"""

from __future__ import annotations

from collections.abc import Hashable, Iterator
from dataclasses import dataclass, field
from typing import Literal, Self

from rayscreen.geometry import Rect

TEXT = 16  # raygui's 10 px default is hard to read
SMALL = 14  # secondary text
ROW = 26.0  # one row of widgets
GAP = 4.0  # between rows
PAD = 10.0  # inside panels and around screens
CHECK = 18.0  # check box side
ICON = 16.0  # a raygui icon's side
MIN_BUTTON = 80.0  # the narrowest a button sized to its text gets
SCROLLBAR = 14.0
SCROLL_BORDER = 1.0  # raygui's scroll panel border; its view is the bounds inset by this
WINDOW_TITLE = 24.0  # raygui's window title bar
WINDOW_WIDTH = 520.0  # a window sized to its content is never wider than this, unless it says otherwise
TOOLTIP_WIDTH = 280.0  # the widest a tooltip grows before its text wraps
TOOLTIP_OFFSET = 16.0  # from the cursor to the tooltip, clear of the arrow
SPLIT_BAR = 8.0  # the width of a `Split`'s bar, which the mouse drags
DRAG_START = 4.0  # pixels the mouse moves, held down on a picture with `drag`, before it is a drag and not a click

type Tone = Literal["ink", "muted", "error", "ok", "warning", "info"]
type Fit = Literal["contain", "stretch"]
type Align = Literal["left", "right"]


@dataclass(slots=True)
class Label:
    """One line of text, or wrapped to its width; emits nothing. Its `tone` says how it reads: `ink`
    for text, `muted` for secondary text (a description under a title), `error` for a problem (what is
    wrong with the box above it), and `ok`, `warning` and `info` for a state (done, out of date, under
    way). A `tooltip` shows while the mouse rests on the label (what a field's name means), in place of
    the screen's `hover` hook's, as a picture's does. An `elide` label too long for its width gives up its
    start to "…" (a path, whose end says most), drawn where a weighted label would otherwise run over its
    neighbours. Its `size` is multiplied by the `text_scale` in force, and so is its default `height` (`ROW` when None)."""

    id: str
    text: str
    height: float | None = None
    size: int = TEXT
    wrap: bool = False
    align: Literal["left", "center"] = "left"
    tone: Tone = "ink"
    tooltip: Tooltip | None = None
    elide: bool = False
    weight: float = 0.0
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)


@dataclass(frozen=True, slots=True)
class Span:
    """A run of a `Text` in one tone: a value in ink after its muted name, a problem in the error colour."""

    text: str
    tone: Tone = "ink"


@dataclass(slots=True)
class Text:
    """A paragraph of `spans`, each in its own tone, wrapped to its width as one flow (a word is not broken
    where the tone changes, and a "\\n" starts a new line); emits nothing. Lines after the first start
    `indent` pixels in: a hanging indent, for a list item whose text wraps under its first word ("• "). A `tooltip`
    shows while the mouse rests on the text, as a label's does."""

    id: str
    spans: list[Span]
    size: int = TEXT
    indent: float = 0.0
    weight: float = 0.0
    tooltip: Tooltip | None = None
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)

    @classmethod
    def of(cls, id: str, *parts: str | Span, size: int = TEXT, indent: float = 0.0, tooltip: Tooltip | None = None) -> Self:
        """A text from strings (in ink) and spans: `Text.of("walls", "walls ", Span("no", "muted"))`."""
        return cls(id, [part if isinstance(part, Span) else Span(part) for part in parts], size, indent, tooltip=tooltip)


@dataclass(slots=True)
class Button:
    """Emits an event (value None) when clicked; a button that is not `enabled` is greyed and emits
    nothing. In a row it is as wide as its text (at least `MIN_BUTTON`), or `width` when given (a
    narrow "<" in a crowded row). Its text is centred, or reads from the left with `align="left"` (a
    section's header in a long form, its titles down one edge). A `tooltip` says what an icon's button does,
    while the mouse rests on it. An `invalid` button (its value clashes with another's: a key bound twice) has
    its border and text in the theme's error colour, and still clicks.

    Its text is the theme's size (times the `text_scale` in force), or `size` when given (a key's large label); a
    larger text makes its default height (`ROW` when None), its least width and its icons larger with it."""

    id: str
    text: str
    enabled: bool = True
    invalid: bool = False
    width: float | None = None
    align: Literal["left", "center"] = "center"
    tooltip: Tooltip | None = None
    height: float | None = None
    size: int | None = None
    weight: float = 0.0
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)


@dataclass(slots=True)
class Toggle:
    """A pressed/released switch; emits the new `active`. Its text is centred, or reads from the left with
    `align="left"`. A `tooltip` shows while the mouse rests on it, as a button's (the key that does the same). One
    that is not `enabled` is greyed and emits nothing (a setting the environment fixes). Its text `size` and
    default `height` are a button's."""

    id: str
    text: str
    active: bool = False
    align: Literal["left", "center"] = "center"
    tooltip: Tooltip | None = None
    height: float | None = None
    size: int | None = None
    weight: float = 0.0
    enabled: bool = True
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)


@dataclass(slots=True)
class CheckBox:
    """A box with a label; emits the new `checked`. One that is not `enabled` is greyed and cannot be
    changed. Its box (`CHECK`), its text and its default height (`ROW` when None) grow with the `text_scale`."""

    id: str
    text: str
    checked: bool = False
    enabled: bool = True
    height: float | None = None
    weight: float = 0.0
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)


@dataclass(slots=True)
class Slider:
    """A value between `minimum` and `maximum`; emits the new value while dragged. `format` shows
    the value beside the bar (`"{:.2f}"` for a 0-1 value; `""` for none, when a box beside it shows it). While
    the mouse holds it, its screen's or window's `UiState.sliding` is its id: an app that moves the range to
    follow the value leaves it alone until then. One that is not `enabled` is greyed and emits nothing (a setting
    the environment fixes); a `tooltip` shows while the mouse rests on it. `step` is how far left or right moves it
    while it has the keys' or the pad's focus (a twentieth of its range when None; 1 for a whole number). Its text
    `size` and default `height` are a button's."""

    id: str
    text: str
    value: float
    minimum: float
    maximum: float
    format: str = "{:.0f}"
    height: float | None = None
    weight: float = 0.0
    enabled: bool = True
    tooltip: Tooltip | None = None
    step: float | None = None
    size: int | None = None
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)


@dataclass(slots=True)
class TextBox:
    """One line of text; emits the text when the user leaves the box, not per keystroke. An `invalid`
    box (its text has a problem, said by an error `Label` beside it) has its border in the theme's
    error colour; one that is not `enabled` is greyed and cannot be edited.

    A `submit` box is a chat's: Enter emits the text, clears the box and keeps it focused; leaving it
    emits nothing and keeps what was typed as its draft (`UiState.take_draft`, for a Send button), and
    `text` is only shown while there is no draft.

    An enabled box takes the keys' or the pad's focus (`navigation`). Activating it starts editing in
    place, as a click does (Enter on a keyboard); a `keyboard` box instead emits `Event(screen, id, None)`,
    for the app to open a `KeyboardWindow` (a pad has no keys to type with). A click still edits in place.

    Its text `size` and default `height` are a button's."""

    id: str
    text: str
    invalid: bool = False
    enabled: bool = True
    submit: bool = False
    keyboard: bool = False
    height: float | None = None
    size: int | None = None
    weight: float = 0.0
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)


@dataclass(slots=True)
class Dropdown:
    """A button showing the current choice that opens a list; emits the choice. `current` is an
    index into `choices`, updated when a choice is made. One that is not `enabled` is greyed and does
    not open; a `tooltip` shows while the mouse rests on it (why it is not enabled). Its text and default height
    (`ROW` when None) grow with the `text_scale`; its open list stays at the theme's size."""

    id: str
    choices: tuple[str, ...]
    current: int = 0
    height: float | None = None
    weight: float = 0.0
    enabled: bool = True
    tooltip: Tooltip | None = None
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)


@dataclass(slots=True)
class Progress:
    """A bar from 0 to 1; emits nothing. A `vertical` one fills from the bottom and is `width` wide in a row (a HUD's
    health bar); a `colour` (RGB, 0-255) fills it instead of raygui's. A `tooltip` shows while the mouse rests on it
    (the numbers behind the bar)."""

    id: str
    value: float
    vertical: bool = False
    width: float = ROW
    colour: tuple[int, int, int] | None = None
    tooltip: Tooltip | None = None
    height: float = ROW
    weight: float = 0.0
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)


@dataclass(slots=True)
class ListView:
    """A scrollable list of items; emits the selected item. Item texts must not contain ";"."""

    id: str
    items: tuple[str, ...]
    selected: int = -1
    height: float = 5 * ROW
    weight: float = 0.0
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)


@dataclass(slots=True)
class Picture:
    """A texture shown in its rect: a rendered view, a thumbnail. `texture` is opaque to the specs (a
    raylib `Texture` when drawn; None draws an empty frame) and `size` is its pixel size, which `fit`
    uses: `contain` shows it whole, centred, at the largest scale that fits; `stretch` fills the rect.
    `flipped` draws it upside down, as a render texture is stored; `framed` outlines it even with a texture
    (a box of a grid), in the theme's accent instead of muted with `accent` (the slots most items go in).
    A `caption` is written inside the box while it has no texture (an empty slot's name); a `tint` (RGBA,
    0-255) colours the texture (a blocked slot's dimmed picture). A `clickable` picture emits an event
    (value None) when clicked; otherwise it takes no
    mouse, so the screen's `hover` and `menu` hooks, and the app's own pan and zoom, work over it. A `tooltip`
    shows while the mouse rests on the picture (a thumbnail's details), in place of the `hover` hook's; a
    `menu` opens on a right-click on it (an item's actions), as a screen's `menu` hook does over the screen.

    Drag and drop: a picture with `drag` (what it carries: an item's id) is dragged when the mouse presses on it
    and moves `DRAG_START` pixels before letting go; meanwhile its texture follows the mouse and the picture shows
    empty. On release its screen emits `Event(screen, id, Drop(...))`, naming the `drop` picture under the mouse,
    in any window of the screen (`screen.Drop`). A press and release without moving is a click, when `clickable`.

    In a `Row` a picture takes a share of the width, or `width` when given (a portrait's square beside a fill).
    """

    id: str
    texture: object = None
    size: tuple[float, float] = (0.0, 0.0)
    fit: Fit = "contain"
    flipped: bool = False
    clickable: bool = False
    tooltip: Tooltip | None = None
    drag: Hashable | None = None
    drop: bool = False
    menu: Menu | None = None
    framed: bool = False
    caption: str = ""
    tint: tuple[int, int, int, int] | None = None
    accent: bool = False
    height: float = 5 * ROW
    width: float | None = None
    weight: float = 0.0
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)


@dataclass(slots=True)
class Separator:
    """A thin rule across its width, between sections of a tooltip or a panel, in the muted tone."""

    height: float = 2 * GAP + 1
    weight: float = 0.0
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)


@dataclass(slots=True)
class Swatch:
    """A square of colour (RGB, 0-255) beside a label: a legend's key. Emits nothing."""

    id: str
    colour: tuple[int, int, int]
    side: float = ICON
    height: float = ROW
    weight: float = 0.0
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)


@dataclass(slots=True)
class Fill:
    """Empty space: in a `Column` or `Row` it shares what is left with the other weighted children,
    which is how centered layouts are made. With `weight=0` it is a fixed gap of `size` pixels
    along its container (an indent in a row)."""

    weight: float = 1.0
    size: float = 0.0
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)


@dataclass(slots=True)
class Column:
    """Stacks children top to bottom, each at its measured height; weighted children share the
    height that is left. Content taller than the column overflows the bottom (a `Scroll` clips). In a
    `Row`, a column with a `width` is that wide, like a label, instead of taking a share (a strip of bars
    or buttons beside a log that takes the rest); weighted as well, it keeps that width and fills the row's height (a
    pane of a fixed width whose scroll reaches the bottom). A `text_scale` scales the text under it (see the
    module's docstring)."""

    children: list[Node]
    gap: float = GAP
    width: float | None = None
    weight: float = 0.0
    text_scale: float | None = None
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)


@dataclass(slots=True)
class Row:
    """Lays its children left to right, each top-aligned at its natural height. An unweighted child
    with a natural width (a label, button, toggle, check box or dropdown) gets just that; the
    weighted children, and unweighted ones with no natural width (counted as weight 1), share what is
    left. Natural widths that do not fit shrink in proportion, so a row never overflows. A weighted
    child also gets the row's whole height (a row given more than its natural height, as a weighted
    row in a column is): two columns side by side, each filling the window's height. A `text_scale` scales the
    text under it, as a column's does."""

    children: list[Node]
    gap: float = GAP
    weight: float = 0.0
    text_scale: float | None = None
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)


@dataclass(slots=True)
class Grid:
    """Wraps its children into rows of as many `cell`-wide columns as fit (at least one), left to
    right, then top to bottom: a sheet of thumbnails. With `columns`, rows of exactly that many, whatever
    the width (a backpack's boxes, 8 across). Each row is as tall as its tallest child at the cell's width;
    columns are `gap` apart, rows too."""

    children: list[Node]
    cell: float
    gap: float = GAP
    columns: int = 0
    weight: float = 0.0
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)


@dataclass(slots=True)
class Table:
    """Rows of cells in columns that line up, as a key/value list or a table of counts: each column is as
    wide as its widest cell, `gap` apart, its cells aligned by `align` (per column; left past its end), and
    each row as tall as its tallest cell. A row shorter than the widest gives its last cell all the width
    left (a note under its key), and that cell widens no column. When the columns do not fit, the last
    one shrinks to what is left: a wrapped label or a `Text` there wraps. A label centres its line in its
    height and a `Text` starts at its top, so labels beside texts take a text's line (`size + 4`) to sit
    level with them. A `stretch` table's last column takes all the width the others leave, as a form's
    boxes do beside their names (a text box has no width of its own to give the column)."""

    rows: list[list[Node]]
    align: tuple[Align, ...] = ()
    gap: float = PAD
    row_gap: float = 0.0
    stretch: bool = False
    weight: float = 0.0
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)


@dataclass(slots=True)
class Split:
    """Two children side by side, each the split's full height, with a bar between them that the mouse
    drags left and right. `ratio` is the left child's share of the width the bar leaves; each side
    keeps at least its `minimum` (pixels, left and right). A drag is kept in the screen's interaction
    state by `id`, so it outlives the tree being rebuilt; releasing the bar emits the new ratio."""

    id: str
    left: Node
    right: Node
    ratio: float = 0.5
    minimum: tuple[float, float] = (160.0, 160.0)
    bar: float = SPLIT_BAR
    weight: float = 0.0
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)


@dataclass(slots=True)
class Placed:
    """A child of a `Board`, its middle at `at`: fractions of the board's width and height, (0, 0) its top-left
    corner. The child keeps its own size: its natural width (a picture's `width`, a label's text), else square on
    its height."""

    child: Node
    at: tuple[float, float]


@dataclass(slots=True)
class Board:
    """A canvas of a fixed `aspect` (width over height): its `background` picture fills it, and each `Placed`
    child sits by its middle at a fraction of it (a paperdoll's slots on their figure). Measured as wide as it is
    given and `width / aspect` tall; arranged, it keeps its aspect inside what it is given, centred. `Placed` is a
    wrapper, not a node: `walk` yields the background and the children."""

    background: Picture
    children: list[Placed]
    aspect: float
    weight: float = 0.0
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)


@dataclass(slots=True)
class Panel:
    """A titled group box around one child. The group box is lines only; `fill` paints the box with
    the theme's panel colour, for a panel over a busy or dimmed screen (a pause menu). `backdrop` (0 to 1)
    paints it instead with the theme's background at that opacity, for text over a picture that must
    still show through (a game's HUD over its world); an untitled one draws no lines, and the mouse over
    it stays free, as over the picture, unless it is `solid`: then, as over a filled panel, the mouse is
    the panel's (a HUD's bar of buttons and meters, the world faintly showing through it). In a `Row`, a
    `fit` panel is as wide as its content (as a tooltip measures it) instead of taking a share, like a
    label: a HUD's box round its text."""

    child: Node
    title: str = ""
    pad: float = PAD
    fill: bool = False
    backdrop: float = 0.0
    solid: bool = False
    fit: bool = False
    weight: float = 0.0
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)


@dataclass(slots=True)
class Scroll:
    """Scrolls one child (usually a `Column`) whose content is taller than the space it gets. Give
    it a `weight` in a `Column`, or it takes its content's full height and never scrolls. `pad` keeps
    the content off the border (left, right, and at the content's top and bottom). A `follow` scroll
    stays at the bottom while its content grows (a chat's), unless the user has scrolled up; scrolled
    back to the bottom, it follows again."""

    id: str  # the scroll offset hangs off this id
    child: Node
    pad: float = PAD
    follow: bool = False
    weight: float = 0.0
    rect: Rect = field(default=Rect(0, 0, 0, 0), init=False, repr=False)


type Node = (
    Label | Text | Button | Toggle | CheckBox | Slider | TextBox | Dropdown | Progress | ListView | Picture | Swatch | Separator | Fill
    | Column | Row | Grid | Table
    | Split | Board
    | Panel | Scroll
)


def children(node: Node) -> list[Node]:
    """A node's direct children, in drawing order; none for a leaf."""
    match node:
        case Column(children=nodes) | Row(children=nodes) | Grid(children=nodes):
            return list(nodes)
        case Table(rows=rows):
            return [cell for row in rows for cell in row]
        case Split(left=left, right=right):
            return [left, right]
        case Board(background=background, children=placed):
            return [background, *(each.child for each in placed)]
        case Panel(child=child) | Scroll(child=child):
            return [child]
    return []


def walk(root: Node) -> Iterator[Node]:
    """Every node in the tree, root first."""
    yield root
    for child in children(root):
        yield from walk(child)


def check_unique_ids(root: Node) -> None:
    """Fail fast when two widgets in the tree share an id: events and the interaction state key on ids."""
    seen: set[str] = set()
    for node in walk(root):
        node_id = getattr(node, "id", None)
        if node_id is None:
            continue
        if node_id in seen:
            raise ValueError(f"duplicate widget id: {node_id!r}")
        seen.add(node_id)


@dataclass(slots=True)
class Tooltip:
    """What a screen's `hover` shows for the thing under the mouse: any spec tree (labels, an HP
    bar), drawn locked in a box beside the cursor. `key` says what is hovered (an entity id, "minimap";
    never None): the box shows once the same key has been hovered a moment, and a new key starts
    over, while the content may change every frame. The box is as wide as its content, at most
    `width`; wrapped text wraps there."""

    key: Hashable
    root: Node
    width: float = TOOLTIP_WIDTH

    def __post_init__(self) -> None:
        check_unique_ids(self.root)

    @classmethod
    def text(cls, key: Hashable, title: str, *lines: str) -> Self:
        """The common case: a title over muted, wrapped lines."""
        children: list[Node] = [Label("tooltip.title", title, height=TEXT + 4)]
        children += [Label(f"tooltip.{i}", line, size=SMALL, wrap=True, tone="muted") for i, line in enumerate(lines)]
        return cls(key, Column(children=children))


@dataclass(frozen=True, slots=True)
class MenuItem:
    """One option of a context menu; one that is not `enabled` is shown greyed and cannot be chosen
    ("Trade" with nobody to trade)."""

    id: str
    text: str
    enabled: bool = True


@dataclass(slots=True)
class Menu:
    """What a screen's `menu` offers for a right-click on the thing under the mouse. The choice comes
    back as an event from `id` with the item's id as its value (None: dismissed) and `target`, what
    the menu is about (an entity id), so the app needs no memory of which menu it built. `title`
    heads the list (the entity's name) and cannot be chosen. `info` is what there is to know about
    the thing (a villager's stats, a place's facts): any spec tree, drawn locked under the title and
    above the items, at most `width` wide, its wrapped text wrapping there."""

    id: str
    items: list[MenuItem]
    title: str | None = None
    target: Hashable = None
    info: Node | None = None
    width: float = TOOLTIP_WIDTH

    def __post_init__(self) -> None:
        if self.info is not None:
            check_unique_ids(self.info)
