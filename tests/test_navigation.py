"""Moving the focus without a window: which widgets take it, where each move lands in a column, a row and a grid,
from where they are on screen, and how a scroll follows the focus."""

from rayscreen.geometry import Rect
from rayscreen.layout import arrange
from rayscreen.navigation import Nav, Placed, focusables, into_view, list_step, menu_step, slid, step, visible
from rayscreen.specs import (
    GAP,
    Button,
    CheckBox,
    Column,
    Dropdown,
    Grid,
    Label,
    Menu,
    MenuItem,
    Picture,
    Row,
    Scroll,
    Slider,
    Table,
    TextBox,
    Toggle,
)


def measure(text: str, size: int) -> float:
    return len(text) * size * 0.5


def laid_out(root: Column | Row | Grid) -> Column | Row | Grid:
    arrange(root, Rect(0, 0, 400, 300), measure)
    return root


def test_only_enabled_buttons_and_toggles_take_the_focus():
    root = Column(children=[Label("title", "Title"), Button("new", "New"), Button("load", "Load", enabled=False),
                            Toggle("tab", "Tab")])
    assert [placed.node.id for placed in focusables(root)] == ["new", "tab"]


def test_an_options_column_of_dropdowns_sliders_and_check_boxes_is_walked_down_to_its_buttons():
    root = laid_out(Column(children=[Toggle("full", "Full screen"), Dropdown("size", ("800 x 600", "1024 x 768")),
                                     Slider("pixel", "", 4.0, 1.0, 16.0), CheckBox("vsync", "Vsync"),
                                     Dropdown("view", ("Top",), enabled=False), Slider("off", "", 1.0, 0.0, 2.0, enabled=False),
                                     Button("save", "Save")]))
    nodes = focusables(root)
    assert [placed.node.id for placed in nodes] == ["full", "size", "pixel", "vsync", "save"]
    assert step(nodes, "full", "down") == "size" and step(nodes, "size", "down") == "pixel"
    assert step(nodes, "pixel", "down") == "vsync" and step(nodes, "vsync", "down") == "save"


def test_left_and_right_move_a_slider_by_its_step_within_its_range():
    slider = Slider("pixel", "", 4.0, 1.0, 16.0, step=1.0)
    assert slid(slider, "right") == 5.0 and slid(slider, "left") == 3.0 and slid(slider, "down") is None
    assert slid(Slider("top", "", 16.0, 1.0, 16.0, step=1.0), "right") == 16.0
    assert slid(Slider("unit", "", 0.5, 0.0, 1.0), "left") == 0.45  # without a step, a twentieth of the range


def test_an_open_list_s_focus_steps_up_and_down_its_choices_and_stays_at_its_ends():
    assert list_step(3, None, "down") == 0 and list_step(3, 0, "down") == 1 and list_step(3, 2, "down") == 2
    assert list_step(3, 0, "up") == 0 and list_step(3, 1, "left") == 1 and list_step(0, None, "down") is None


def test_the_first_move_focuses_the_first_widget_then_moves_go_down_and_up_a_column():
    nodes = focusables(laid_out(Column(children=[Button("a", "A"), Button("b", "B"), Button("c", "C")])))
    assert step(nodes, None, "down") == "a" and step(nodes, "gone", "up") == "a"
    assert step(nodes, "a", "down") == "b" and step(nodes, "c", "up") == "b"
    assert step(nodes, "c", "down") == "c" and step(nodes, "a", "left") == "a"  # an edge: the focus stays


def test_a_row_moves_left_and_right():
    nodes = focusables(laid_out(Row(children=[Button("save", "Save"), Button("back", "Back")])))
    assert step(nodes, "save", "right") == "back" and step(nodes, "back", "left") == "save"


def test_a_move_takes_the_widget_straight_that_way_over_a_nearer_one_aside():
    root = laid_out(Column(children=[Row(children=[Button("a", "A", weight=1.0), Button("b", "B", weight=1.0)]),
                                     Row(children=[Button("c", "C", weight=1.0), Button("d", "D", weight=1.0)])]))
    nodes = focusables(root)
    assert step(nodes, "b", "down") == "d" and step(nodes, "c", "up") == "a" and step(nodes, "c", "right") == "d"


def test_nav_says_whether_anything_was_asked():
    assert not Nav().any and Nav(move="up").any and Nav(activate=True).any and Nav(back=True).any
    assert Nav(delete=True).any and Nav(space=True).any and Nav(shift=True).any and Nav(confirm=True).any


def scrolled_list(offset: float) -> list[Placed]:
    """Ten buttons in a scroll showing about four, scrolled by `offset`, over a Save button."""
    root = Column(children=[Scroll("list", Column(children=[Button(f"row{i}", f"Row {i}") for i in range(10)]),
                                   weight=1.0),
                            Button("save", "Save")])
    arrange(root, Rect(0, 0, 400, 160), measure)
    return focusables(root, lambda scroll_id: offset if scroll_id == "list" else 0.0)


def test_a_widget_in_a_scroll_is_placed_where_the_scroll_shows_it():
    top, scrolled = scrolled_list(0.0), scrolled_list(-50.0)
    assert scrolled[3].rect.y == top[3].rect.y - 50 and scrolled[3].scroll is not None and scrolled[-1].scroll is None


def test_down_a_scrolled_list_steps_to_the_next_row_then_out_of_it():
    nodes = scrolled_list(0.0)
    assert step(nodes, "row2", "down") == "row3" and step(nodes, "save", "up") != "save"
    assert step(scrolled_list(-1000.0), "row9", "down") == "save"


def test_the_scroll_moves_just_enough_to_show_the_focus():
    nodes = scrolled_list(0.0)
    hidden = next(placed for placed in nodes if not visible(placed))
    shown = into_view(hidden, 0.0)
    assert shown < 0.0
    moved = hidden._replace(rect=hidden.rect._replace(y=hidden.rect.y + shown))
    assert visible(moved) and into_view(moved, shown) == shown  # already shown: the scroll stays
    assert into_view(scrolled_list(-40.0)[0], -40.0) == 0.0  # back up to the top, never past it


def test_a_picture_that_does_something_takes_the_focus():
    item = Menu("items", [MenuItem("drop", "Drop")])
    root = Row(children=[Picture("bread", menu=item), Picture("button", clickable=True), Picture("empty", drop=True)])
    assert [placed.node.id for placed in focusables(root)] == ["bread", "button"]


def test_a_menu_s_focus_steps_over_the_disabled_items_and_stays_at_its_ends():
    items = [MenuItem("wear", "Wear"), MenuItem("trade", "Trade", enabled=False), MenuItem("drop", "Drop")]
    assert menu_step(items, None, "down") == 0
    assert menu_step(items, 0, "down") == 2 and menu_step(items, 2, "down") == 2 and menu_step(items, 2, "up") == 0
    assert menu_step(items, 0, "left") == 0 and menu_step([MenuItem("x", "X", enabled=False)], None, "down") is None


def test_down_from_a_tab_lands_on_the_wide_box_below_it_before_a_small_button_further_down():
    # a creation screen's top: two tabs, then a name box beside its label, then a < > row
    root = laid_out(Column(children=[
        Row(children=[Toggle("tab.a", "Appearance", weight=1), Toggle("tab.b", "Outfit", weight=1)]),
        Row(children=[Column(children=[Label("name.label", "Name")], width=120), TextBox("name", "", weight=1)]),
        Row(children=[Column(children=[Label("gender.label", "Gender")], width=120), Button("gender.prev", "<", width=40), Label("gender", "Female", weight=1),
                      Button("gender.next", ">", width=40)]),
    ]))
    nodes = focusables(root)
    assert step(nodes, "tab.a", "down") == "name"  # its centre is far right of the tab's, but it lies straight below
    assert step(nodes, "name", "down") == "gender.prev"  # both arrows lie below the box: the first in the row
    assert step(nodes, "gender.next", "up") == "name"


EXPRESSIONS = ("neutral", "happy", "sad", "angry", "surprised", "blink")


def chooser(name: str) -> Row:
    """A `<  value  >` chooser: the value's label takes the width between its two narrow buttons."""
    return Row(children=[Button(f"{name}.prev", "<", width=40), Label(f"{name}.value", "Value", align="center", weight=1),
                         Button(f"{name}.next", ">", width=40)])


def swatches(name: str, count: int) -> Row:
    return Row(children=[Picture(f"{name}.{i}", clickable=True, width=30, height=30) for i in range(1, count + 1)])


def creation_form(width: float) -> list[Placed]:
    """A character creation form as an app builds one: names beside their controls in a stretch table, choosers with
    rows of small swatches between them, a slider, and a full-width row of expression toggles. The swatches lie
    nearer a chooser's `<` than its `>` does, and the toggles grow with the width while the gaps between lines do
    not: where a move went by distance on screen alone, both left their row."""
    face = Table([[Label("gender.label", "Gender"), chooser("gender")],
                  [Label("skin.label", "Skin"), swatches("skin", 8)],
                  [Label("eyes.label", "Eyes"), chooser("eyes")],
                  [Label("eye_height.label", "Eye height"), Slider("eye_height", "", 0.5, 0.0, 1.0, weight=1)]],
                 row_gap=GAP, stretch=True)
    expression = Row(children=[Toggle(f"expression.{name}", name.title(), weight=1) for name in EXPRESSIONS])
    hair = Table([[Label("hair.label", "Hair"), chooser("hair")],
                  [Label("hair_colour.label", "Colour"), swatches("hair_colour", 10)]], row_gap=GAP, stretch=True)
    root = Column(children=[face, Label("expression.label", "Try an expression"), expression, hair])
    arrange(root, Rect(0, 0, width, width * 9 / 16), measure)
    return focusables(root)


def test_left_and_right_keep_to_a_chooser_s_row_over_the_swatches_beside_it():
    for width in (1280, 1920, 2560):
        nodes = creation_form(width)
        for name in ("gender", "eyes", "hair"):
            assert step(nodes, f"{name}.prev", "right") == f"{name}.next", (width, name)
            assert step(nodes, f"{name}.next", "left") == f"{name}.prev", (width, name)


def test_left_and_right_walk_a_wide_row_of_toggles_in_order():
    ids = [f"expression.{name}" for name in EXPRESSIONS]
    for width in (1280, 2000, 2560):
        nodes = creation_form(width)
        assert [step(nodes, ids[i], "right") for i in range(len(ids) - 1)] == ids[1:], width
        assert [step(nodes, ids[i], "left") for i in range(1, len(ids))] == ids[:-1], width


def test_at_a_row_s_end_the_focus_stays_rather_than_jump_to_a_row_that_looks_nearer():
    nodes = creation_form(1920)
    assert step(nodes, "skin.8", "right") == "skin.8"  # the gender row's `>` lies up and to the right
    assert step(nodes, "skin.1", "left") == "skin.1"
    assert step(nodes, "expression.blink", "right") == "expression.blink"


def test_up_and_down_go_line_by_line_to_the_nearest_widget_in_the_next_line():
    nodes = creation_form(1920)
    assert step(nodes, "gender.next", "down") == "skin.8"  # no swatch under it: still the swatch row
    assert step(nodes, "gender.prev", "down") == "skin.1"
    assert step(nodes, "skin.3", "up") == "gender.prev" and step(nodes, "skin.3", "down") == "eyes.prev"
    assert step(nodes, "eye_height", "down") == "expression.neutral"  # out of the table into the row below it
    assert step(nodes, "expression.angry", "up") == "eye_height" and step(nodes, "expression.angry", "down") == "hair.next"
    assert step(nodes, "expression.happy", "down") == "hair.prev"  # the hair line first, not a colour swatch nearer aside


def test_right_from_a_column_beside_another_goes_across_not_to_its_top():
    root = laid_out(Row(children=[Column(children=[Button("a", "A"), Button("b", "B")], weight=1),
                                  Column(children=[Button("c", "C"), Button("d", "D")], weight=1)]))
    nodes = focusables(root)
    assert step(nodes, "b", "right") == "d" and step(nodes, "d", "left") == "b"
    assert step(nodes, "a", "right") == "c" and step(nodes, "a", "down") == "b"


def test_at_a_row_s_end_the_focus_leaves_it_for_the_panel_beside_it():
    form = Column(children=[Row(children=[Button("a", "A"), Button("b", "B")]), Row(children=[Button("c", "C")])], weight=1)
    root = laid_out(Row(children=[form, Column(children=[Button("side", "Side"), Button("lower", "Lower")], width=100)]))
    nodes = focusables(root)
    assert step(nodes, "b", "right") == "side" and step(nodes, "c", "right") == "lower"  # the nearest, level with it
    assert step(nodes, "side", "left") == "b" and step(nodes, "lower", "left") == "c"


def test_a_grid_moves_by_where_its_cells_are():
    root = laid_out(Grid([Picture(f"cell.{i}", clickable=True, height=40) for i in range(6)], cell=60, columns=3))
    nodes = focusables(root)
    assert step(nodes, "cell.0", "right") == "cell.1" and step(nodes, "cell.1", "down") == "cell.4"
    assert step(nodes, "cell.5", "up") == "cell.2" and step(nodes, "cell.2", "right") == "cell.2"


def test_a_column_asked_to_move_sideways_with_nothing_beside_it_stays():
    nodes = focusables(laid_out(Column(children=[Button("a", "A"), Button("b", "B")])))
    assert step(nodes, "a", "right") == "a" and step(nodes, "b", "left") == "b"
