"""The drawing code's geometry rules that need no window: where a window sits."""

from rayscreen.draw import _window_rect
from rayscreen.screen import Window
from rayscreen.specs import PAD, WINDOW_TITLE, Button
from rayscreen.theme import FONT, Theme


def test_minimizing_a_centred_window_keeps_its_title_bar_in_place():
    window = Window("w", "W", Button("ok", "OK"), size=(300, 200))
    open_rect = _window_rect(window, Theme(), 1000, 700)
    window.minimized = True
    minimized = _window_rect(window, Theme(), 1000, 700)
    assert (minimized.x, minimized.y, minimized.width) == (open_rect.x, open_rect.y, open_rect.width)
    assert minimized.height == WINDOW_TITLE


def test_the_default_font_is_bundled():
    assert FONT.is_file()
    assert Theme().font_path == FONT


def test_a_placed_window_stays_on_a_screen_that_shrinks():
    window = Window("map", "Map", Button("ok", "OK"), size=(200, 200), borderless=True)
    window.position = (780.0, 10.0)  # the top-right corner of a 1000-wide screen
    assert _window_rect(window, Theme(), 1000, 700).x == 780.0
    shrunk = _window_rect(window, Theme(), 800, 300)
    assert (shrunk.x, shrunk.y) == (600.0, 10.0)  # its right edge on the screen's
    assert _window_rect(window, Theme(), 800, 150).y + 150 - 2 * PAD <= 150  # sized down, then moved up
