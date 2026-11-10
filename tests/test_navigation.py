"""Moving the focus without a window: which widgets take it, where each move lands in a column, a row and a grid,
from where they are on screen, and how a scroll follows the focus."""

from rayscreen.geometry import Rect
from rayscreen.layout import arrange
from rayscreen.navigation import Nav, Placed, focusables, into_view, list_step, menu_step, slid, step, visible
from rayscreen.specs import (
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
