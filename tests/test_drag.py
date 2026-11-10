"""Drag and drop between pictures, with no window: when a press becomes a drag, which target a release finds
(in a window's scrolled grid, between its boxes, on the screen), the click that is not a drag, and the drag outliving
a rebuilt tree but not a screen pushed over it."""

import pyray as rl

from rayscreen.draw import _pointer_free, drop_target, release_drag
from rayscreen.geometry import Rect
from rayscreen.layout import arrange, grid_columns, measure
from rayscreen.screen import Drop, Event, Screen, ScreenManager, Window
from rayscreen.specs import DRAG_START, GAP, Column, Fill, Grid, Picture, Scroll
from rayscreen.state import Dragging
from rayscreen.theme import Theme

WIDTH, HEIGHT = 1000.0, 700.0
BOX = 40.0


def fake_measure(text: str, size: int) -> float:
    return float(len(text) * 7)


def boxes(n: int, full: int) -> list[Picture]:
    """`n` boxes, the first `full` carrying an item each (its index plus 100), every one a target."""
    return [Picture(f"box.{i}", drag=100 + i if i < full else None, drop=True, height=BOX) for i in range(n)]


def pack_screen() -> tuple[Screen, Window]:
    """A world with a pack's window over it: 4 columns of boxes, 3 rows, in a scroll shorter than them."""
    window = Window("pack", "Pack", Scroll("pack.scroll", Grid(boxes(12, 5), cell=BOX, columns=4), weight=1),
                    size=(300.0, 150.0), modal=False)
    window.position = (100.0, 100.0)
    screen = Screen("game", Column(children=[Fill()]))
    screen.open(window)
    arrange(screen.root, Rect(0, 0, WIDTH, HEIGHT), fake_measure)
    arrange(window.root, Rect(110, 134, 280, 106), fake_measure)  # where `_draw_window` puts its content
    return screen, window


def held(screen: Screen, source: str, value: object, clickable: bool = False) -> Dragging:
    screen.state.dragging = Dragging(source, value, None, True, (BOX, BOX), clickable, (0.0, 0.0))
    return screen.state.dragging


def middle(picture: Picture, scrolled: float = 0.0) -> tuple[float, float]:
    return picture.rect.x + picture.rect.width / 2, picture.rect.y + picture.rect.height / 2 + scrolled


def test_a_press_becomes_a_drag_only_once_the_mouse_has_moved_far_enough():
    dragging = Dragging("box.0", 100, None, True, (BOX, BOX), False, (50.0, 50.0))
    dragging.move(50.0 + DRAG_START - 1, 50.0)
    assert not dragging.started
    dragging.move(50.0, 50.0 + DRAG_START)
    assert dragging.started
    dragging.move(50.0, 50.0)  # back where it began: still a drag
    assert dragging.started


def test_a_grid_with_columns_keeps_that_many_whatever_its_width():
    grid = Grid(boxes(12, 0), cell=BOX, columns=4)
    assert grid_columns(grid, 1000.0) == 4 and grid_columns(grid, 50.0) == 4
    assert measure(grid, 1000.0, fake_measure) == 3 * BOX + 2 * GAP
    assert grid_columns(Grid(boxes(12, 0), cell=BOX), 1000.0) == 22  # without: as many as fit


def test_a_release_over_a_box_names_it_scrolled_as_it_is_drawn():
    screen, window = pack_screen()
    grid = window.root.child
    target = grid.children[6]
    held(screen, "box.1", 101).started = True
    event = release_drag(screen, Theme(), WIDTH, HEIGHT, middle(target))
    assert event == Event("game", "box.1", Drop(101, "box.6", middle(target), over_window=True))
    assert screen.state.dragging is None  # over

    window.state.scroll_ptr("pack.scroll")[0].y = -(BOX + GAP)  # scrolled down a row
    assert drop_target(screen, Theme(), WIDTH, HEIGHT, middle(target)) == ("box.10", True)
    assert drop_target(screen, Theme(), WIDTH, HEIGHT, middle(target, -(BOX + GAP))) == ("box.6", True)
    hidden = grid.children[0]
    assert drop_target(screen, Theme(), WIDTH, HEIGHT, middle(hidden, -(BOX + GAP))) == (None, True)  # above the view


def test_a_release_between_boxes_is_over_the_window_and_off_it_over_the_screen():
    screen, window = pack_screen()
    first = window.root.child.children[0]
    between = (first.rect.x + BOX + GAP / 2, first.rect.y + BOX / 2)
    assert drop_target(screen, Theme(), WIDTH, HEIGHT, between) == (None, True)
    held(screen, "box.0", 100).started = True
    event = release_drag(screen, Theme(), WIDTH, HEIGHT, (600.0, 500.0))
    assert event.value == Drop(100, None, (600.0, 500.0), over_window=False)  # onto the world


def test_a_press_and_release_without_moving_is_a_click_and_no_drop():
    screen, _ = pack_screen()
    held(screen, "box.0", 100, clickable=True)
    assert release_drag(screen, Theme(), WIDTH, HEIGHT, (600.0, 500.0)) == Event("game", "box.0", None)
    held(screen, "box.0", 100)
    assert release_drag(screen, Theme(), WIDTH, HEIGHT, (600.0, 500.0)) is None  # not clickable: nothing
    assert release_drag(screen, Theme(), WIDTH, HEIGHT, (600.0, 500.0)) is None  # no drag at all


def test_a_drag_takes_the_mouse_from_the_screen_and_a_dragged_picture_is_a_widget():
    screen, window = pack_screen()
    assert _pointer_free(screen, Theme(), WIDTH, HEIGHT, rl.Vector2(600, 500))
    held(screen, "box.0", 100)
    assert not _pointer_free(screen, Theme(), WIDTH, HEIGHT, rl.Vector2(600, 500))  # letting go is not the world's click

    root = Column(children=[Picture("thing", drag="thing", height=BOX), Fill()])
    on_screen = Screen("s", root)
    arrange(root, Rect(0, 0, WIDTH, HEIGHT), fake_measure)
    assert not _pointer_free(on_screen, Theme(), WIDTH, HEIGHT, rl.Vector2(5, 5))


def test_the_drag_outlives_a_rebuilt_tree_but_not_a_screen_pushed_over_it():
    screen, window = pack_screen()
    dragging = held(screen, "box.0", 100)
    screen.set_root(Column(children=[Fill()]))
    window.set_root(Scroll("pack.scroll", Grid(boxes(12, 4), cell=BOX, columns=4), weight=1))  # the item went
    assert screen.state.dragging is dragging  # it carries the item, not its box: the app asks, the rules decide
    manager = ScreenManager()
    manager.push(screen)
    manager.push(Screen("pause", Column(children=[Fill()]), overlay=True))
    assert screen.state.dragging is None
