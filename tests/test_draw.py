"""The drawing code's geometry rules that need no window: where a window sits, where an open list sits."""

from rayscreen.draw import _open_list_layout, _window_rect
from rayscreen.geometry import Rect
from rayscreen.layout import POPUP_ROW, popup_row
from rayscreen.screen import Window
from rayscreen.specs import PAD, ROW, WINDOW_TITLE, Button
from rayscreen.state import OpenList
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


CHOICES = ("Off", "Low", "Medium", "High")


def test_an_open_list_at_the_theme_s_size_has_popup_rows():
    layout = _open_list_layout(OpenList("shadows", Rect(100, 100, 120, ROW), CHOICES), 700)
    assert (layout.row, layout.shown, layout.cut) == (ROW, CHOICES, False)
    assert (layout.bounds.y, layout.bounds.height) == (100 + ROW + 2, 4 * POPUP_ROW + 2)


def test_an_open_list_under_a_text_scale_grows_its_rows_as_its_button():
    """A dropdown drawn at twice the text has rows as tall as its button, the gap between them kept."""
    layout = _open_list_layout(OpenList("shadows", Rect(100, 100, 240, 2 * ROW), CHOICES, scale=2.0), 700)
    assert layout.row == 2 * ROW
    assert layout.bounds.height == 4 * popup_row(2 * ROW) + 2


def test_an_open_list_under_a_text_scale_is_cut_by_its_grown_rows():
    """Room for the four choices at the theme's size, but not at twice it: three rows show, the last one "..."."""
    anchor = Rect(100, 0, 240, 2 * ROW)
    room = 2 * ROW + 2 + 4 * POPUP_ROW + 2
    assert not _open_list_layout(OpenList("shadows", anchor, CHOICES), room).cut
    layout = _open_list_layout(OpenList("shadows", anchor, CHOICES, scale=2.0), room)
    fits = int((room - 2 * ROW - 4) // popup_row(2 * ROW))
    assert layout.cut and layout.shown == CHOICES[: fits - 1]
    assert layout.bounds.y + layout.bounds.height <= room
