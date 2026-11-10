"""Tooltips, context menus and who owns the mouse: the rules, with no window (fake text width, sized
windows, the mouse passed in)."""

import pyray as rl
import pytest

from rayscreen.draw import _pointer_free, _window_menu_at
from rayscreen.geometry import Rect, place_beside
from rayscreen.layout import BUTTON_INSET, POPUP_ROW, arrange, content_width, menu_size, tooltip_size
from rayscreen.screen import Event, Screen, ScreenManager, Window
from rayscreen.specs import PAD, ROW, TEXT, Button, Column, Fill, Label, Menu, MenuItem, Panel, Progress, Row, Tooltip
from rayscreen.state import OpenList, UiState
from rayscreen.theme import Theme

WIDTH, HEIGHT = 1000.0, 700.0


def fake_measure(text: str, size: int) -> float:
    return float(len(text) * 7)


def game_screen() -> Screen:
    """A HUD over a world: a filled panel on top, a button, a hint label, and empty space between."""
    root = Column(
        children=[
            Panel(Label("gold", "Gold: 12"), fill=True),
            Fill(),
            Button("map", "Map"),
            Label("hint", "Esc: pause"),
        ]
    )
    screen = Screen("game", root)
    arrange(root, Rect(0, 0, WIDTH, HEIGHT), fake_measure)
    return screen


def free(screen: Screen, x: float, y: float) -> bool:
    return _pointer_free(screen, Theme(), WIDTH, HEIGHT, rl.Vector2(x, y))


# --- who owns the mouse


def test_the_mouse_is_free_over_the_screen_itself_and_its_labels():
    screen = game_screen()
    assert free(screen, 500, 300)  # the world, between the HUD's rows
    hint = screen.find("hint")
    assert free(screen, hint.rect.x + 5, hint.rect.y + 5)  # a label takes no click


def test_the_mouse_is_taken_over_a_widget_or_a_filled_panel():
    screen = game_screen()
    button = screen.find("map")
    assert not free(screen, button.rect.x + 5, button.rect.y + 5)
    assert not free(screen, 500, 5)  # the HUD's filled panel hides the world behind it


def test_the_mouse_is_free_over_a_backdrop_panel():
    """A HUD's text on a see-through backdrop is still over the world: the wheel and clicks are the game's."""
    root = Column(children=[Panel(Label("time", "Time: 09:00"), backdrop=0.6), Fill()])
    screen = Screen("game", root)
    arrange(root, Rect(0, 0, WIDTH, HEIGHT), fake_measure)
    assert free(screen, 5, 5)


def test_the_mouse_is_taken_over_a_solid_backdrop_panel_and_its_gaps():
    """A HUD's bar: the world shows faintly through it, but a click on it, between its buttons too, is the bar's."""
    root = Column(children=[Panel(Row(children=[Label("time", "09:00"), Fill()]), backdrop=0.85, solid=True), Fill()])
    screen = Screen("game", root)
    arrange(root, Rect(0, 0, WIDTH, HEIGHT), fake_measure)
    assert not free(screen, 5, 5)
    assert not free(screen, WIDTH - 5, 5)  # beside its label
    assert free(screen, 5, HEIGHT - 5)  # below it: the world


def test_the_mouse_is_taken_over_a_floating_window_even_minimized():
    screen = game_screen()
    window = Window("log", "Log", Button("ok", "OK"), size=(300, 200), modal=False, minimizable=True)
    window.position = (100, 100)
    screen.open(window)
    assert not free(screen, 150, 150)
    assert free(screen, 450, 400)
    window.minimized = True
    assert not free(screen, 150, 110)  # the title bar
    assert free(screen, 150, 150)  # where the window was


def test_a_modal_window_an_open_list_or_a_drag_takes_the_mouse_everywhere():
    screen = game_screen()
    modal = Window("quit", "Quit?", Button("yes", "Yes"), size=(300, 200))
    screen.open(modal)
    assert not free(screen, 10, 600)
    screen.close_window(modal)
    screen.state.open_list = OpenList("d", Rect(0, 0, 10, 10), ("a",))
    assert not free(screen, 10, 600)
    screen.state.open_list = None
    floating = Window("log", "Log", Button("ok", "OK"), size=(100, 100), modal=False)
    screen.open(floating)
    floating.drag_offset = (5, 5)
    assert not free(screen, 900, 600)


# --- placement


def test_a_box_sits_below_right_of_the_cursor():
    assert place_beside((100, 100), 50, 40, WIDTH, HEIGHT, 16) == (116, 116)


def test_a_box_flips_at_the_right_and_bottom_edges():
    assert place_beside((990, 690), 50, 40, WIDTH, HEIGHT, 16) == (990 - 16 - 50, 690 - 16 - 40)


def test_a_box_is_clamped_onto_a_screen_too_small_for_it():
    assert place_beside((20, 20), 300, 200, 250, 150, 16) == (0.0, 0.0)
    assert place_beside((30, 140), 50, 40, 250, 150, 16) == (46, 140 - 16 - 40)  # flipped above


# --- tooltips


def test_a_tooltip_is_as_wide_as_its_widest_line():
    tooltip = Tooltip.text("mira", "Mira", "Miller")
    width, height = tooltip_size(tooltip, WIDTH, fake_measure)
    assert width == 2 * PAD + 6 * 7  # "Miller" is wider than "Mira"
    assert height == 2 * PAD + (TEXT + 4) + 4 + (14 + 4)  # the title, the gap, one wrapped line


def test_a_long_line_wraps_at_the_tooltips_width():
    tooltip = Tooltip.text("mira", "Mira", "word " * 40)
    width, height = tooltip_size(tooltip, WIDTH, fake_measure)
    assert width == tooltip.width
    assert height > 2 * PAD + (TEXT + 4) + 4 + 2 * (14 + 4)


def test_a_bar_has_no_width_of_its_own():
    assert content_width(Column(children=[Label("name", "Mira"), Progress("hp", 0.5)]), fake_measure) == 4 * 7


def test_tooltip_ids_must_be_unique():
    with pytest.raises(ValueError):
        Tooltip("k", Column(children=[Label("a", "A"), Label("a", "B")]))


def test_the_tooltip_shows_after_the_delay():
    state = UiState()
    assert not state.hover("mira", 0.0, 0.3, pressed=False)
    assert not state.hover("mira", 0.2, 0.3, pressed=False)
    assert state.hover("mira", 0.3, 0.3, pressed=False)
    assert state.hover("mira", 5.0, 0.3, pressed=False)  # the content may change; the key holds it


def test_a_new_key_restarts_the_delay_and_nothing_hides_at_once():
    state = UiState()
    state.hover("mira", 0.0, 0.3, pressed=False)
    assert state.hover("mira", 1.0, 0.3, pressed=False)
    assert not state.hover("chest", 1.1, 0.3, pressed=False)
    assert state.hover("chest", 1.5, 0.3, pressed=False)
    assert not state.hover(None, 1.6, 0.3, pressed=False)
    assert not state.hover("chest", 1.7, 0.3, pressed=False)  # back on it: the delay again


def test_a_press_hides_the_tooltip_until_the_mouse_moves_on():
    state = UiState()
    state.hover("mira", 0.0, 0.0, pressed=False)
    assert not state.hover("mira", 0.1, 0.0, pressed=True)
    assert not state.hover("mira", 2.0, 0.0, pressed=False)
    assert state.hover("chest", 2.1, 0.0, pressed=False)


# --- context menus


def villager_menu() -> Menu:
    return Menu("npc", [MenuItem("talk", "Talk"), MenuItem("trade", "Trade", enabled=False)], title="Mira", target=42)


def test_choosing_an_item_closes_the_menu_and_hands_back_its_target():
    screen = game_screen()
    screen.open_menu(villager_menu(), 300, 300)
    assert screen.close_menu("talk") == Event("game", "npc", "talk", target=42)
    assert screen.state.menu is None
    assert screen.close_menu() is None  # nothing left to close


def test_dismissing_the_menu_says_so_with_no_choice():
    screen = game_screen()
    screen.open_menu(villager_menu(), 300, 300)
    assert screen.close_menu() == Event("game", "npc", None, target=42)


def test_opening_a_menu_drops_the_tooltip_the_edit_and_the_open_list():
    screen = game_screen()
    screen.state.hover("mira", 0.0, 0.0, pressed=False)
    screen.state.editing = "name"
    screen.state.open_list = OpenList("d", Rect(0, 0, 10, 10), ("a",))
    screen.open_menu(villager_menu(), 300, 300)
    assert (screen.state.hovered, screen.state.editing, screen.state.open_list) == (None, None, None)


def test_a_window_or_a_screen_over_the_menu_closes_it():
    screen = game_screen()
    screen.open_menu(villager_menu(), 300, 300)
    screen.open(Window("log", "Log", Button("ok", "OK"), size=(100, 100), modal=False))
    assert screen.state.menu is None
    manager = ScreenManager()
    manager.push(screen)
    screen.open_menu(villager_menu(), 300, 300)
    manager.push(Screen("pause", Column(children=[Fill()]), overlay=True))
    assert screen.state.menu is None


def test_events_without_a_target_are_unchanged():
    assert Event("game", "map", None) == Event("game", "map", None, target=None)


def test_a_menu_is_as_wide_as_its_widest_item_or_title():
    menu = Menu("m", [MenuItem("a", "Inspect the strange thing")], title="Mira")
    size = menu_size(menu, HEIGHT, fake_measure)
    assert size.width == len("Inspect the strange thing") * 7 + 2 * (PAD + BUTTON_INSET) + 2  # raygui cuts text that leaves no room
    assert size.height == 2 * POPUP_ROW + 2  # the title's row and one item
    assert (size.shown, size.cut) == (1, False)


def test_a_menus_info_sits_between_its_title_and_items_and_wraps_at_its_width():
    stats = Column(children=[Label("hp", "HP 12 of 20"), Label("about", "word " * 40, wrap=True)])
    menu = Menu("m", [MenuItem("a", "Trade")], title="Mira", info=stats, width=200.0)
    size = menu_size(menu, HEIGHT, fake_measure)
    assert size.width == 200.0 + 2  # the info's widest text, cut at the menu's width
    assert size.info > ROW + 2 * PAD  # the wrapped label takes several lines
    assert size.height == POPUP_ROW + size.info + POPUP_ROW + 2  # title, info, one item
    with pytest.raises(ValueError, match="duplicate widget id"):
        Menu("m", [], info=Column(children=[Label("x", "a"), Label("x", "b")]))


def test_a_menu_taller_than_the_screen_is_cut():
    menu = Menu("m", [MenuItem(f"i{i}", f"Item {i}") for i in range(40)])
    size = menu_size(menu, 300, fake_measure)
    assert size.cut
    assert size.height <= 300
    assert size.shown == int((300 - 2) // POPUP_ROW) - 1


def window_menu(screen: Screen, x: float, y: float) -> Menu | None:
    return _window_menu_at(screen, Theme(), WIDTH, HEIGHT, rl.Vector2(x, y))


def test_a_window_with_a_menu_offers_it_off_its_widgets_and_only_there():
    screen = game_screen()
    menu = Menu("minimap.menu", [MenuItem("close", "Close")])
    window = Window("minimap", "Minimap", Column(children=[Button("zoom", "Zoom"), Fill()]), size=(200, 200),
                    borderless=True, modal=False, menu=menu)
    window.position = (700.0, 20.0)
    screen.open(window, focus=False)
    arrange(window.root, Rect(700 + PAD, 20 + PAD, 200 - 2 * PAD, 200 - 2 * PAD), fake_measure)
    assert window_menu(screen, 800, 180) is menu  # the window itself
    zoom = window.root.children[0]
    assert window_menu(screen, zoom.rect.x + 5, zoom.rect.y + 5) is None  # its button keeps its click
    assert window_menu(screen, 500, 300) is None  # off the window: the screen's own hook answers there
    screen.open(Window("ask", "Sure?", Label("q", "Sure?")))  # a modal window over everything
    assert window_menu(screen, 800, 180) is None
