"""The two layout passes, with no raylib: `measure` (the height a node wants at a width) and
`arrange` (every node's rect, top down). Text width is injected, so the passes are tested without a
window. The sizes of the popups (a tooltip, a context menu) are worked out here too.

Both passes, and the widths they use, take the text scale in force (`scale`, 1 at a root): a `Column`'s or a
`Row`'s `text_scale` replaces it for what is under it (`scale_in`), and `text_size`, `widget_scale` and
`leaf_height` say what it makes of a widget. The drawing walk reads them too, so it draws what was measured.
"""

import math
from collections.abc import Callable
from typing import NamedTuple

from rayscreen.geometry import Rect
from rayscreen.specs import (
    CHECK,
    GAP,
    ICON,
    MIN_BUTTON,
    PAD,
    ROW,
    SCROLL_BORDER,
    SCROLLBAR,
    SMALL,
    TEXT,
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
    Span,
    Split,
    Swatch,
    Table,
    Text,
    TextBox,
    Toggle,
    Tone,
    Tooltip,
)

POPUP_ROW = ROW + 2  # a row of a popup list (an open dropdown, a context menu), with its gap
BUTTON_INSET = 2.0  # pixels raygui keeps clear each side of a button's text, inside its padding (measured): or it cuts the text

type MeasureText = Callable[[str, int], float]
SIZED = (Button, Toggle, Slider, TextBox)  # the widgets with a text `size` of their own


def scale_in(node: Node, scale: float) -> float:
    """The text scale under `node`: its own `text_scale` (a column's or a row's), else the one in force."""
    if isinstance(node, Column | Row) and node.text_scale is not None:
        return node.text_scale
    return scale


def scaled(size: float, scale: float) -> int:
    """A text size times a scale, in whole pixels: the font is loaded per size, at whole sizes only."""
    return max(1, round(size * scale))


def text_size(node: Node, scale: float = 1.0, base: int = TEXT, small: int = SMALL) -> int:
    """The size `node`'s text is drawn at under `scale`: a label's or a text's own `size` times it; a picture's caption
    and badge, `small` (the theme's small text) times it; a widget's own `size` when given, else `base` (the theme's
    text) times it."""
    match node:
        case Label() | Text():
            return scaled(node.size, scale)
        case Picture():
            return scaled(small, scale)
        case Button() | Toggle() | Slider() | TextBox() if node.size is not None:
            return node.size
    return scaled(base, scale)


def widget_scale(node: Node, scale: float) -> float:
    """How much larger than `TEXT` a widget's text is: its own `size` over `TEXT`, else the scale in force. Its
    default height, its least width and its icons grow by it, so a larger text still fits."""
    if isinstance(node, SIZED) and node.size is not None:
        return node.size / TEXT
    return scale


def icon_scale(size: int) -> int:
    """raygui's icon scale for text at `size`: whole steps of the icons' 16 px, the nearest to the text (1 at
    `TEXT`), so an icon beside a label stays as tall as its letters."""
    return max(1, round(size / ICON))


def leaf_height(node: Node, scale: float) -> float:
    """A widget's height under `scale`: its `height`, or with none (`None`) a `ROW` grown as its text grows. Other
    leaves (pictures, bars, swatches, lists) keep the height they have."""
    height = getattr(node, "height", None)
    if height is not None:
        return height
    return ROW * widget_scale(node, scale)


def elided(text: str, width: float, size: int, measure_text: MeasureText) -> str:
    """`text` with its start given up to "…" until it fits `width` (all of it while it fits)."""
    if measure_text(text, size) <= width:
        return text
    for start in range(1, len(text)):
        shown = "…" + text[start:]
        if measure_text(shown, size) <= width:
            return shown
    return "…"


def wrap_text(text: str, width: float, size: int, measure_text: MeasureText) -> list[str]:
    """`text` broken into lines that fit `width` pixels at `size`."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split():
            candidate = f"{line} {word}" if line else word
            if line and measure_text(candidate, size) > width:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
    return lines


class Run(NamedTuple):
    """A piece of a `Text`'s line in one tone, `x` pixels from the text's left."""

    x: float
    text: str
    tone: Tone


type Word = list[Span]  # the pieces of one word, a piece per tone


def text_lines(text: Text, width: float, measure_text: MeasureText, scale: float = 1.0) -> list[list[Run]]:
    """`text`'s lines at `width`, each its runs of one tone: words wrapped as `wrap_text` wraps them, lines
    after the first `indent` in. A word too long for a line has one to itself. Its text is `text_size` under
    `scale`."""
    size = text_size(text, scale)
    lines: list[list[Run]] = []
    for paragraph in _paragraphs(text.spans):
        line: list[Span] = []
        for word in paragraph:
            candidate = [*line, Span(" ", line[-1].tone), *word] if line else list(word)
            indent = text.indent if lines else 0.0
            if line and indent + measure_text(_joined(candidate), size) > width:
                lines.append(_runs(line, indent, size, measure_text))
                line = list(word)
            else:
                line = candidate
        lines.append(_runs(line, text.indent if lines else 0.0, size, measure_text))
    return lines


def _paragraphs(spans: list[Span]) -> list[list[Word]]:
    """The spans' words by paragraph ("\\n" ends one). Whitespace separates words and is dropped, as
    `wrap_text` drops it; a word whose tone changes inside it has a piece per tone."""
    paragraphs: list[list[Word]] = [[]]
    word: Word = []
    for span in spans:
        piece = ""
        for char in span.text:
            if not char.isspace():
                piece += char
                continue
            if piece:
                word.append(Span(piece, span.tone))
                piece = ""
            if word:
                paragraphs[-1].append(word)
                word = []
            if char == "\n":
                paragraphs.append([])
        if piece:
            word.append(Span(piece, span.tone))
    if word:
        paragraphs[-1].append(word)
    return paragraphs


def _joined(pieces: list[Span]) -> str:
    return "".join(piece.text for piece in pieces)


def _runs(pieces: list[Span], indent: float, size: int, measure_text: MeasureText) -> list[Run]:
    """A line's pieces as runs of one tone each, placed by measuring the line up to each run (so the font's
    spacing between letters is counted as when the line is drawn whole)."""
    runs: list[Run] = []
    before = ""
    for piece in pieces:
        if runs and runs[-1].tone == piece.tone:
            last = runs[-1]
            runs[-1] = Run(last.x, last.text + piece.text, last.tone)
        else:
            runs.append(Run(indent + (measure_text(before, size) if before else 0.0), piece.text, piece.tone))
        before += piece.text
    return runs


def _line_width(runs: list[Run], size: int, measure_text: MeasureText) -> float:
    return runs[-1].x + measure_text(runs[-1].text, size) if runs else 0.0


def table_columns(table: Table, width: float, measure_text: MeasureText, scale: float = 1.0) -> list[float]:
    """The width of each of a table's columns at `width`: its widest cell (a short row's last cell does not
    count), the last column shrunk to what is left when they do not all fit, or given it all when the table
    stretches."""
    count = max((len(row) for row in table.rows), default=0)
    widths = [0.0] * count
    for row in table.rows:
        for i, cell in enumerate(row if len(row) == count else row[:-1]):
            widths[i] = max(widths[i], content_width(cell, measure_text, scale))
    room = width - table.gap * max(0, count - 1)
    if count and (table.stretch or sum(widths) > room):
        widths[-1] = max(0.0, room - sum(widths[:-1]))
    return widths


class Cell(NamedTuple):
    x: float  # from the table's left
    width: float


def table_cells(table: Table, width: float, measure_text: MeasureText, scale: float = 1.0) -> list[list[Cell]]:
    """Where each cell of a table goes across `width`: in its column, or from its column to the table's right
    edge for the last cell of a short row; a right-aligned cell as wide as its content, at the column's right."""
    widths = table_columns(table, width, measure_text, scale)
    starts = [sum(widths[:i]) + table.gap * i for i in range(len(widths))]
    cells: list[list[Cell]] = []
    for row in table.rows:
        placed: list[Cell] = []
        for i, cell in enumerate(row):
            spans = len(row) < len(widths) and i == len(row) - 1
            x, cell_width = starts[i], max(0.0, width - starts[i]) if spans else widths[i]
            if i < len(table.align) and table.align[i] == "right":
                natural = min(content_width(cell, measure_text, scale), cell_width)
                x, cell_width = x + cell_width - natural, natural
            placed.append(Cell(x, cell_width))
        cells.append(placed)
    return cells


def _table_rows(table: Table, cells: list[list[Cell]], measure_text: MeasureText, scale: float) -> list[float]:
    """The height of each row of a table: its tallest cell at the width it is given."""
    return [
        max((measure(node, cell.width, measure_text, scale) for node, cell in zip(row, placed)), default=0.0)
        for row, placed in zip(table.rows, cells)
    ]


def measure(node: Node, width: float, measure_text: MeasureText, scale: float = 1.0) -> float:
    """The height `node` wants at `width`, under the text scale `scale`. Weighted children and `Scroll` take what a
    `Column` gives them, so they measure 0 there."""
    scale = scale_in(node, scale)
    match node:
        case Label(wrap=True):
            size = text_size(node, scale)
            return max(1, len(wrap_text(node.text, width, size, measure_text))) * (size + 4)
        case Label() | Button() | Toggle() | CheckBox() | Slider() | TextBox() | Dropdown() | Progress() | ListView() | Picture() | Swatch():
            return leaf_height(node, scale)
        case Separator():
            return node.height
        case Text():
            return len(text_lines(node, width, measure_text, scale)) * (text_size(node, scale) + 4)
        case Fill():
            return node.size if node.weight <= 0 else 0.0
        case Column():
            if not node.children:
                return 0.0
            natural = sum(measure(child, width, measure_text, scale) for child in node.children if child.weight <= 0)
            return natural + node.gap * (len(node.children) - 1)
        case Row():
            shares = _shares(width, node.gap, node.children, measure_text, scale)
            heights = [measure(child, share, measure_text, scale) for child, share in zip(node.children, shares)]
            return max(heights, default=0.0)
        case Split():
            left, right = split_widths(node, width)
            return max(measure(node.left, left, measure_text, scale), measure(node.right, right, measure_text, scale))
        case Board():
            return width / node.aspect if node.aspect > 0 else 0.0
        case Grid():
            rows = _grid_rows(node, width, measure_text, scale)
            return sum(rows) + node.gap * max(0, len(rows) - 1)
        case Table():
            rows = _table_rows(node, table_cells(node, width, measure_text, scale), measure_text, scale)
            return sum(rows) + node.row_gap * max(0, len(rows) - 1)
        case Panel():
            top = title_strip(node, scale) + panel_top(node, scale)
            return measure(node.child, width - 2 * node.pad, measure_text, scale) + top + node.pad
        case Scroll():
            if node.weight > 0:
                return 0.0
            return measure(node.child, width - SCROLLBAR - 2 * node.pad, measure_text, scale) + 2 * node.pad


def arrange(node: Node, rect: Rect, measure_text: MeasureText, scale: float = 1.0) -> None:
    """Give every node its rect, top down, under the text scale `scale`. A `Column` hands its leftover height to
    its weighted children; a `Row` gives unweighted children their natural width and shares the rest by weight,
    and its weighted children its whole height."""
    node.rect = rect
    scale = scale_in(node, scale)
    match node:
        case Column():
            if not node.children:
                return
            gaps = node.gap * (len(node.children) - 1)
            naturals = [measure(child, rect.width, measure_text, scale) if child.weight <= 0 else 0.0 for child in node.children]
            leftover = rect.height - gaps - sum(naturals)
            total_weight = sum(child.weight for child in node.children if child.weight > 0)
            y = rect.y
            for child, natural in zip(node.children, naturals):
                height = natural
                if child.weight > 0 and total_weight > 0:
                    height = max(0.0, leftover) * child.weight / total_weight
                arrange(child, Rect(rect.x, y, rect.width, height), measure_text, scale)
                y += height + node.gap
        case Row():
            shares = _shares(rect.width, node.gap, node.children, measure_text, scale)
            x = rect.x
            for child, share in zip(node.children, shares):
                height = measure(child, share, measure_text, scale)
                if child.weight > 0:  # a weighted child fills the row's height too: side-by-side halves
                    height = max(height, rect.height)
                arrange(child, Rect(x, rect.y, share, height), measure_text, scale)
                x += share + node.gap
        case Split():
            left, right = split_widths(node, rect.width)
            arrange(node.left, Rect(rect.x, rect.y, left, rect.height), measure_text, scale)
            arrange(node.right, Rect(rect.x + left + node.bar, rect.y, right, rect.height), measure_text, scale)
        case Board():
            fitted = board_rect(node, rect)
            arrange(node.background, fitted, measure_text, scale)
            for placed in node.children:
                child = placed.child
                child_width = natural_width(child, measure_text, scale)
                if child_width is None:  # a picture with no `width`: square on its height
                    child_width = leaf_height(child, scale) if hasattr(child, "height") else ROW
                child_height = measure(child, child_width, measure_text, scale)
                middle_x = fitted.x + placed.at[0] * fitted.width
                middle_y = fitted.y + placed.at[1] * fitted.height
                arrange(child, Rect(middle_x - child_width / 2, middle_y - child_height / 2, child_width, child_height),
                        measure_text, scale)
        case Grid():
            columns = grid_columns(node, rect.width)
            y = rect.y
            for row, height in enumerate(_grid_rows(node, rect.width, measure_text, scale)):
                for column, child in enumerate(node.children[row * columns : (row + 1) * columns]):
                    x = rect.x + column * (node.cell + node.gap)
                    arrange(child, Rect(x, y, node.cell, measure(child, node.cell, measure_text, scale)), measure_text, scale)
                y += height + node.gap
        case Table():
            cells = table_cells(node, rect.width, measure_text, scale)
            y = rect.y
            for row, placed, height in zip(node.rows, cells, _table_rows(node, cells, measure_text, scale)):
                for child, cell in zip(row, placed):
                    cell_height = measure(child, cell.width, measure_text, scale)
                    arrange(child, Rect(rect.x + cell.x, y, cell.width, cell_height), measure_text, scale)
                y += height + node.row_gap
        case Panel():
            top = title_strip(node, scale) + panel_top(node, scale)
            inner = Rect(rect.x + node.pad, rect.y + top, rect.width - 2 * node.pad, rect.height - top - node.pad)
            arrange(node.child, inner, measure_text, scale)
        case Scroll():
            pad = node.pad
            width = rect.width - SCROLLBAR - 2 * pad
            natural = measure(node.child, width, measure_text, scale)
            # Let the child fill the view when the content fits, so its Fill works; but stop at the
            # bounds minus the border: raygui's view is the bounds inset by the border, and content
            # even a pixel taller scrolls, leaving the bottom row half outside the view (and locked)
            fitted = rect.height - 2 * SCROLL_BORDER - 2 * pad
            arrange(node.child, Rect(rect.x + pad, rect.y + pad, width, max(natural, fitted)), measure_text, scale)
        case _:
            pass  # leaves keep the rect they were given


def split_widths(split: Split, width: float) -> tuple[float, float]:
    """The widths of a split's two sides at `width`: the left gets `ratio` of what the bar leaves, kept
    within the minimums (shared in proportion when the width cannot hold both)."""
    room = max(width - split.bar, 0.0)
    low, high = split.minimum
    if low + high >= room:
        left = room * low / (low + high) if low + high > 0 else room / 2
    else:
        left = min(max(room * split.ratio, low), room - high)
    return left, room - left


def split_bar(split: Split) -> Rect:
    """Where a split's bar is, as last arranged."""
    left, _ = split_widths(split, split.rect.width)
    return Rect(split.rect.x + left, split.rect.y, split.bar, split.rect.height)


def board_rect(board: Board, rect: Rect) -> Rect:
    """The largest rect of the board's aspect inside `rect`, centred: where the background and the children's
    fractions land."""
    if rect.width <= 0 or rect.height <= 0 or board.aspect <= 0:
        return rect
    if rect.width / rect.height > board.aspect:  # the rect is wider than the board: the height limits
        height, width = rect.height, rect.height * board.aspect
    else:
        width, height = rect.width, rect.width / board.aspect
    return Rect(rect.x + (rect.width - width) / 2, rect.y + (rect.height - height) / 2, width, height)


def split_ratio(split: Split, x: float) -> float:
    """The ratio that puts the middle of the bar at `x`, the mouse dragging it."""
    room = max(split.rect.width - split.bar, 1.0)
    return min(max((x - split.rect.x - split.bar / 2) / room, 0.0), 1.0)


def grid_columns(grid: Grid, width: float) -> int:
    """How many `cell`-wide columns fit across `width`, at least one; the grid's `columns`, when it fixes them."""
    if grid.columns > 0:
        return grid.columns
    return max(1, int((width + grid.gap) // (grid.cell + grid.gap)))


def _grid_rows(grid: Grid, width: float, measure_text: MeasureText, scale: float) -> list[float]:
    """The height of each row of a grid at `width`: its tallest child at the cell's width."""
    columns = grid_columns(grid, width)
    children = grid.children
    return [
        max(measure(child, grid.cell, measure_text, scale) for child in children[start : start + columns])
        for start in range(0, len(children), columns)
    ]


def picture_rect(picture: Picture, rect: Rect) -> Rect:
    """Where a picture's texture is drawn in `rect`: all of it for `stretch`; for `contain`, the
    largest rect of the texture's shape that fits, centred (all of `rect` while its size is unknown)."""
    width, height = picture.size
    if picture.fit == "stretch" or width <= 0 or height <= 0:
        return rect
    scale = min(rect.width / width, rect.height / height)
    w, h = width * scale, height * scale
    return Rect(rect.x + (rect.width - w) / 2, rect.y + (rect.height - h) / 2, w, h)


BADGE_INSET = 3.0  # pixels between a picture's badge and the box's bottom right corner
BADGE_PAD = 3.0  # pixels of the badge's plate either side of its text


def badge_rect(rect: Rect, text_width: float, size: int) -> Rect:
    """The plate of a picture's badge in `rect`: its text (`text_width` wide at `size`) padded, in the bottom right
    corner inset by `BADGE_INSET`, and kept inside the box's left and top edges when the box is too small for it."""
    w, h = min(text_width + 2 * BADGE_PAD, rect.width), min(size + 4.0, rect.height)
    x = max(rect.x + rect.width - BADGE_INSET - w, rect.x)
    y = max(rect.y + rect.height - BADGE_INSET - h, rect.y)
    return Rect(x, y, w, h)


def title_strip(panel: Panel, scale: float = 1.0) -> float:
    """The height a panel's title adds above its box: raygui draws the title centred on the box's
    top line, so half of it sticks out above; the lower half fits inside the panel's `pad`."""
    return scaled(TEXT, scale) / 2 if panel.title else 0.0


TITLE_CLEARANCE = 2.0  # pixels between a panel's title and its content, below the title's lower half


def panel_top(panel: Panel, scale: float = 1.0) -> float:
    """How far below its box's top line a panel's content starts: its `pad`, or under a large `text_scale` far
    enough to clear the lower half of the title raygui draws across that line (the pad is the same at every scale,
    the title is not). At a scale of 1 the pad already clears it, and nothing moves."""
    if not panel.title:
        return panel.pad
    return max(panel.pad, scaled(TEXT, scale) / 2 + TITLE_CLEARANCE)


def natural_width(node: Node, measure_text: MeasureText, scale: float = 1.0) -> float | None:
    """The width a leaf needs for its content in a `Row`, its text at its size under `scale`; None when it has none
    (sliders, text boxes, bars but a vertical one, lists, pictures without a `width`, containers but a `fit` panel and
    a column with a `width`, weighted fills, wrapped labels) and takes a share instead."""
    match node:
        case Label(wrap=False):
            return measure_text(node.text, text_size(node, scale))
        case Button(width=width) if width is not None:
            return width
        case Button() | Toggle():
            return max(MIN_BUTTON * widget_scale(node, scale), measure_text(node.text, text_size(node, scale)) + 2 * PAD)
        case CheckBox():
            return CHECK * scale + GAP + measure_text(node.text, text_size(node, scale))
        case Dropdown():
            size = text_size(node, scale)
            widest = max((measure_text(choice, size) for choice in node.choices), default=0.0)
            return widest + ICON * icon_scale(size) + GAP + 2 * PAD
        case Swatch():
            return node.side
        case Picture(width=width) if width is not None:
            return width
        case Fill(weight=weight) if weight <= 0:
            return node.size
        case Panel(fit=True):
            return content_width(node, measure_text, scale)
        case Progress(vertical=True):
            return node.width
        case Column(width=width) if width is not None:
            return width
    return None


def _fixed_width(node: Node) -> bool:
    """A column with a `width` keeps it in a row even when weighted: its weight then only fills the row's height."""
    return isinstance(node, Column) and node.width is not None


def _shares(width: float, gap: float, children: list[Node], measure_text: MeasureText, scale: float) -> list[float]:
    """The widths of a `Row`'s children: unweighted children with a natural width get it, and the
    rest share what is left by weight (0 counts as 1). When the natural widths alone do not fit they
    shrink in proportion and the sharing children get nothing."""
    if not children:
        return []
    available = max(0.0, width - gap * (len(children) - 1))
    naturals = [natural_width(child, measure_text, scale) if child.weight <= 0 or _fixed_width(child) else None
                for child in children]
    fixed = sum(natural for natural in naturals if natural is not None)
    if fixed > available:
        return [natural * available / fixed if natural is not None else 0.0 for natural in naturals]
    rest = available - fixed
    total = sum(child.weight if child.weight > 0 else 1.0 for child, natural in zip(children, naturals) if natural is None)
    shares: list[float] = []
    for child, natural in zip(children, naturals):
        if natural is not None:
            shares.append(natural)
        else:
            shares.append(rest * (child.weight if child.weight > 0 else 1.0) / total)
    return shares


def content_width(node: Node, measure_text: MeasureText, scale: float = 1.0) -> float:
    """The width a tree wants when nothing constrains it (a tooltip's box), under the text scale `scale`: a wrapped
    label as one line, a column its widest child, a row its children side by side. Widgets with no natural width
    (bars, sliders) want none and take what the box gives them."""
    scale = scale_in(node, scale)
    match node:
        case Label(wrap=True):
            return max(measure_text(line, text_size(node, scale)) for line in node.text.split("\n"))
        case Text():
            size = text_size(node, scale)
            return max(_line_width(runs, size, measure_text) for runs in text_lines(node, math.inf, measure_text, scale))
        case Table():
            widths = table_columns(node, math.inf, measure_text, scale)
            widest = sum(widths) + node.gap * max(0, len(widths) - 1)
            for row in node.rows:
                if 0 < len(row) < len(widths):  # its last cell spans the rest
                    start = sum(widths[: len(row) - 1]) + node.gap * (len(row) - 1)
                    widest = max(widest, start + content_width(row[-1], measure_text, scale))
            return widest
        case Column(width=width) if width is not None:
            return width
        case Column():
            return max((content_width(child, measure_text, scale) for child in node.children), default=0.0)
        case Row():
            widths = [content_width(child, measure_text, scale) for child in node.children]
            return sum(widths) + node.gap * max(0, len(widths) - 1)
        case Split():
            return content_width(node.left, measure_text, scale) + node.bar + content_width(node.right, measure_text, scale)
        case Grid():
            across = min(len(node.children), node.columns) if node.columns > 0 else len(node.children)
            return node.cell * across + node.gap * max(0, across - 1)
        case Panel():
            return content_width(node.child, measure_text, scale) + 2 * node.pad
        case Scroll():
            return content_width(node.child, measure_text, scale) + SCROLLBAR + 2 * node.pad
    return natural_width(node, measure_text, scale) or 0.0


def tooltip_size(tooltip: Tooltip, screen_width: float, measure_text: MeasureText) -> tuple[float, float]:
    """The tooltip's box: its content's width plus `PAD` each side, at most `tooltip.width` (and the
    screen), and the height its content measures at that width."""
    width = min(content_width(tooltip.root, measure_text) + 2 * PAD, tooltip.width, screen_width)
    return width, measure(tooltip.root, width - 2 * PAD, measure_text) + 2 * PAD


class MenuSize(NamedTuple):
    width: float
    height: float
    shown: int  # how many items fit
    cut: bool  # some did not: the last row reads "..."
    info: float = 0.0  # the height of the info under the title, its padding included


def menu_size(menu: Menu, screen_height: float, measure_text: MeasureText) -> MenuSize:
    """A context menu's box: as wide as its widest item (or title, or its info, up to `menu.width`), the item's
    padding and raygui's inset around it; its info under the title's row, `PAD` around it, then a `POPUP_ROW` per
    item, inside a 1 px border. A menu taller than the screen is cut, its last row "...", as an open dropdown
    list is."""
    texts = [item.text for item in menu.items] + ([menu.title] if menu.title is not None else [])
    width = max(MIN_BUTTON, max((measure_text(text, TEXT) for text in texts), default=0.0) + 2 * (PAD + BUTTON_INSET)) + 2
    info = 0.0
    if menu.info is not None:
        width = max(width, min(content_width(menu.info, measure_text) + 2 * PAD, menu.width) + 2)
        info = measure(menu.info, width - 2 - 2 * PAD, measure_text) + 2 * PAD
    title = POPUP_ROW if menu.title is not None else 0.0
    fits = max(2, int((screen_height - 2 - title - info) // POPUP_ROW))
    cut = len(menu.items) > fits
    shown = fits - 1 if cut else len(menu.items)
    return MenuSize(width, title + info + (shown + cut) * POPUP_ROW + 2, shown, cut, info)
