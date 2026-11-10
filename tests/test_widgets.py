"""Pictures, grids, validation states, disabled boxes, and replacing a screen's tree. No window needed."""

from typing import get_args

import pyray as rl

from rayscreen.draw import _pointer_free
from rayscreen.geometry import Rect
from rayscreen.icons import ICONS, MOON, SUN, icon_text
from rayscreen.layout import arrange, content_width, elided, grid_columns, measure, natural_width, picture_rect, split_bar, split_ratio, split_widths
from rayscreen.screen import Screen, Window
from rayscreen.specs import (
    GAP,
    ROW,
    Button,
    CheckBox,
    Column,
    Grid,
    Label,
    Picture,
    Row,
    Scroll,
    Split,
    Swatch,
    TextBox,
    Tone,
    Tooltip,
    check_unique_ids,
    walk,
)
from rayscreen.state import OpenList
from rayscreen.theme import Theme

WIDTH, HEIGHT = 1000.0, 700.0


def fake_measure(text: str, size: int) -> float:
    return float(len(text) * 7)


# --- Picture


def test_a_contained_picture_keeps_its_shape_centred():
    wide = Picture("p", size=(200, 100))
    assert picture_rect(wide, Rect(0, 0, 400, 400)) == Rect(0, 100, 400, 200)
    tall = Picture("p", size=(100, 200))
    assert picture_rect(tall, Rect(10, 0, 400, 400)) == Rect(110, 0, 200, 400)


def test_a_stretched_or_unsized_picture_fills_its_rect():
    rect = Rect(5, 5, 300, 100)
    assert picture_rect(Picture("p", size=(10, 10), fit="stretch"), rect) == rect
    assert picture_rect(Picture("p"), rect) == rect


def test_a_weighted_picture_fills_what_its_column_leaves():
    picture = Picture("view", weight=1)
    column = Column(children=[Button("b", "Go"), picture])
    arrange(column, Rect(0, 0, 400, 300), fake_measure)
    assert picture.rect == Rect(0, ROW + GAP, 400, 300 - ROW - GAP)
    assert natural_width(picture, fake_measure) is None  # in a row it takes a share


def test_the_mouse_is_free_over_a_plain_picture_but_not_a_clickable_one():
    view, thumb = Picture("view", weight=1), Picture("thumb", clickable=True)
    screen = Screen("s", Column(children=[view, thumb]))
    arrange(screen.root, Rect(0, 0, WIDTH, HEIGHT), fake_measure)
    theme = Theme()
    assert _pointer_free(screen, theme, WIDTH, HEIGHT, rl.Vector2(view.rect.x + 5, view.rect.y + 5))
    assert not _pointer_free(screen, theme, WIDTH, HEIGHT, rl.Vector2(thumb.rect.x + 5, thumb.rect.y + 5))


# --- Grid


def thumbs(n: int, height: float = 100.0) -> list[Picture]:
    return [Picture(f"t{i}", height=height) for i in range(n)]


def test_a_grid_fits_as_many_columns_as_its_width_allows():
    grid = Grid(thumbs(7), cell=100, gap=10)
    assert grid_columns(grid, 319) == 2
    assert grid_columns(grid, 320) == 3  # 3 x 100 + 2 x 10
    assert grid_columns(grid, 50) == 1  # never fewer than one


def test_a_grid_wraps_its_children_into_rows():
    children = thumbs(7)
    grid = Grid(children, cell=100, gap=10)
    assert measure(grid, 330, fake_measure) == 3 * 100 + 2 * 10  # 3 + 3 + 1
    arrange(grid, Rect(0, 0, 330, 400), fake_measure)
    assert children[0].rect == Rect(0, 0, 100, 100)
    assert children[2].rect == Rect(220, 0, 100, 100)
    assert children[3].rect == Rect(0, 110, 100, 100)
    assert children[6].rect == Rect(0, 220, 100, 100)


def test_a_grid_row_is_as_tall_as_its_tallest_child():
    cells = [Column(children=[Picture("a", height=80), Label("a.l", "1")]), Picture("b", height=40), Picture("c", height=40)]
    grid = Grid(cells, cell=100, gap=10)
    arrange(grid, Rect(0, 0, 220, 400), fake_measure)
    assert cells[2].rect.y == 80 + GAP + ROW + 10  # the second row starts below the tall first cell
    assert content_width(grid, fake_measure) == 3 * 100 + 2 * 10


def test_a_grid_in_a_scroll_scrolls():
    grid = Grid(thumbs(30), cell=100, gap=10)
    scroll = Scroll("sheet", grid, weight=1)
    arrange(Column(children=[scroll]), Rect(0, 0, 500, 300), fake_measure)
    assert grid.rect.height > 300


# --- problems and disabled widgets


def test_text_boxes_and_check_boxes_start_valid_and_enabled():
    box, check = TextBox("t", "1"), CheckBox("c", "On")
    assert not box.invalid and box.enabled and check.enabled
    assert Label("l", "x").tone == "ink"


# --- replacing a screen's tree


def form(problem: bool) -> Column:
    children = [TextBox("height", "8"), TextBox("width", "3")]
    if problem:
        children.insert(1, Label("height.problem", "must be above 0", tone="error"))
    return Column(children=[Scroll("form", Column(children=children), weight=1)])


def test_set_root_keeps_the_edit_of_a_box_still_there():
    screen = Screen("town", form(problem=False))
    screen.state.editing, screen.state.buffer = "height", rl.ffi.new("char[16]", b"-1")
    scroll = screen.state.scroll_ptr("form")
    scroll[0].y = -40
    screen.set_root(form(problem=True))
    assert screen.state.editing == "height"
    assert rl.ffi.string(screen.state.buffer) == b"-1"
    assert screen.state.scroll_ptr("form") is scroll and scroll[0].y == -40
    assert screen.find("height.problem") is not None


def test_set_root_drops_the_state_of_ids_that_went():
    screen = Screen("town", Column(children=[TextBox("seed", "1"), Scroll("old", Column(children=[]), weight=1)]))
    screen.state.editing = "seed"
    screen.state.open_list = OpenList("size", Rect(0, 0, 10, 10), ("small",))
    old = screen.state.scroll_ptr("old")
    screen.set_root(Column(children=[TextBox("other", "")]))
    assert screen.state.editing is None and screen.state.open_list is None
    assert screen.state.scroll_ptr("old") is not old  # forgotten: a fresh offset


def test_set_root_checks_ids():
    screen = Screen("town", Column(children=[]))
    try:
        screen.set_root(Column(children=[Button("a", "A"), Button("a", "B")]))
    except ValueError:
        return
    raise AssertionError("duplicate ids were accepted")


def test_a_window_can_replace_its_tree_too():
    window = Window("log", "Log", Column(children=[Label("l0", "one")]), modal=False)
    window.state.editing = "l0"
    window.set_root(Column(children=[Label("l0", "one"), Label("l1", "two")]))
    assert window.state.editing == "l0"


# --- Swatch


def test_a_swatch_is_as_wide_as_its_side_in_a_row():
    swatch, label = Swatch("key", (200, 56, 40)), Label("key.text", "gate")
    row = Row(children=[swatch, label])
    arrange(row, Rect(0, 0, 300, ROW), fake_measure)
    assert swatch.rect.width == 16 and label.rect.x == 16 + GAP


# --- a button's width, light and dark


def test_a_button_with_a_width_takes_just_that_in_a_row():
    narrow, wide = Button("prev", "<", width=32), Button("go", "<")
    assert natural_width(narrow, fake_measure) == 32
    assert natural_width(wide, fake_measure) == 80  # MIN_BUTTON


def test_a_theme_switches_between_light_and_dark_in_place():
    theme = Theme()
    font_cache = theme._fonts
    theme.set_dark(True)  # no window: the colours change, raygui is styled once one opens
    dark = Theme.dark_theme()
    assert theme.dark and (theme.background.r, theme.ink.r) == (dark.background.r, dark.ink.r) and theme.raygui
    assert theme.ink.r > theme.background.r  # light text on dark
    theme.set_dark(False)
    light = Theme()
    assert not theme.dark and theme.raygui == {} and theme.title_ink is None
    assert (theme.background.r, theme.ink.r) == (light.background.r, light.ink.r)
    assert theme._fonts is font_cache


# --- icons raygui lacks


def pixel(icon: int, x: int, y: int) -> bool:
    return bool(ICONS[icon][y // 2] >> (x + 16 * (y % 2)) & 1)


def test_the_sun_and_the_moon_are_drawn_where_they_should_be():
    assert pixel(SUN, 7, 7) and pixel(SUN, 7, 0) and not pixel(SUN, 0, 0)  # a disc with a ray up
    assert pixel(MOON, 2, 7) and not pixel(MOON, 10, 5)  # lit on the left, cut away at the upper right
    assert icon_text(SUN) == "#250#"



# --- Split


def halves(ratio: float = 0.5) -> Split:
    return Split("halves", Column(children=[Button("a", "A")]), Column(children=[Button("b", "B")]), ratio=ratio, minimum=(100, 200))


def test_a_split_shares_its_width_by_ratio_and_fills_its_height():
    split = halves(0.25)
    split.weight = 1
    arrange(Column(children=[split]), Rect(0, 0, 808, 400), fake_measure)
    left, right = split.left.rect, split.right.rect
    assert (left.width, right.x, right.width) == (200, 208, 600)  # 800 left by the bar: a quarter, the rest
    assert left.height == right.height == 400


def test_a_split_keeps_each_side_its_minimum():
    assert split_widths(halves(0.0), 808) == (100, 700)
    assert split_widths(halves(1.0), 808) == (600, 200)
    assert split_widths(halves(0.5), 158) == (50, 100)  # too narrow for both: shared as the minimums are


def test_dragging_the_bar_sets_the_ratio_it_shows_at():
    split = halves()
    arrange(split, Rect(0, 0, 808, 300), fake_measure)
    assert split_bar(split) == Rect(400, 0, 8, 300)
    assert split_ratio(split, 404 + 200) == 0.75  # the bar's middle under the mouse
    assert split_ratio(split, -50) == 0.0


def test_the_mouse_over_a_splits_bar_is_taken_but_not_over_its_sides():
    split = halves()
    screen = Screen("s", split)
    arrange(split, Rect(0, 0, WIDTH, HEIGHT), fake_measure)
    bar = split_bar(split)
    theme = Theme()
    assert not _pointer_free(screen, theme, WIDTH, HEIGHT, rl.Vector2(bar.x + 2, 300))
    assert _pointer_free(screen, theme, WIDTH, HEIGHT, rl.Vector2(bar.x - 50, 300))
    screen.state.dragging_split = "halves"
    assert not _pointer_free(screen, theme, WIDTH, HEIGHT, rl.Vector2(bar.x - 50, 300))  # a drag owns the mouse


def test_a_dragged_ratio_outlives_the_tree():
    screen = Screen("s", halves())
    screen.state.splits["halves"] = 0.3
    screen.set_root(halves())  # rebuilt at its default ratio
    screen.state.apply_splits(screen.root)
    assert screen.root.ratio == 0.3
    screen.set_root(Column(children=[]))
    assert "halves" not in screen.state.splits


# --- state tones and help on a label


def test_every_tone_has_a_colour_in_both_themes_and_they_differ():
    for theme in (Theme(), Theme.dark_theme()):
        colours = {tone: getattr(theme, tone) for tone in get_args(Tone.__value__)}
        assert len({(c.r, c.g, c.b) for c in colours.values()}) == len(colours)


def test_switching_to_dark_and_back_restores_the_state_tones():
    theme = Theme()
    light = [(c.r, c.g, c.b) for c in (theme.ok, theme.warning, theme.info)]
    theme.set_dark(True)
    assert [(c.r, c.g, c.b) for c in (theme.ok, theme.warning, theme.info)] != light
    theme.set_dark(False)
    assert [(c.r, c.g, c.b) for c in (theme.ok, theme.warning, theme.info)] == light


def test_a_labels_tooltip_is_a_tree_of_its_own_and_does_not_lay_out_with_the_label():
    tip = Tooltip.text("help", "name", "a long description " * 5)
    plain, helped = Label("name", "name"), Label("name", "name", tooltip=tip)
    assert measure(plain, 300, fake_measure) == measure(helped, 300, fake_measure)
    tree = Column(children=[helped, Label("help", "help")])  # the tooltip's ids do not clash with the tree's
    check_unique_ids(tree)
    assert [getattr(node, "id", None) for node in walk(tree)] == [None, "name", "help"]


def test_an_elided_label_gives_up_its_start_to_fit():
    path = "/tmp/a/long/folder/world"
    assert elided(path, 1000, 16, fake_measure) == path
    shown = elided(path, 7 * 12, 16, fake_measure)
    assert shown == "…older/world" and fake_measure(shown, 16) <= 7 * 12
    assert elided(path, 3, 16, fake_measure) == "…"
