"""Tests for `KeyboardWindow` and the focusable `TextBox`: typing with the keys, the pad's nav and a physical keyboard,
and moving over the keys. No raylib window needed."""

from rayscreen import (
    Button,
    Column,
    Event,
    KeyboardWindow,
    Nav,
    Rect,
    Screen,
    TextBox,
    Typed,
    arrange,
    dispatch,
    focusables,
    icon_text,
    keyboard_free,
    step,
)
from rayscreen.icons import CAPS_LOCK, SHIFT, SHIFT_ON
from rayscreen.keyboard_window import KEY, LINE
from rayscreen.layout import text_size
from rayscreen.screen import ScreenManager
from rayscreen.specs import GAP, SMALL, TEXT, WINDOW_WIDTH


def measure(text: str, size: int) -> float:
    return len(text) * size * 0.5


def opened(window: KeyboardWindow, box: TextBox | None = None) -> Screen:
    screen = Screen("s", Column(children=[box or TextBox("name", "", keyboard=True)]))
    screen.open(window)
    return screen


def click(screen: Screen, window: KeyboardWindow, *actions: str) -> list[Event]:
    return dispatch(screen, [Event(screen.id, f"{window.id}.{action}", None) for action in actions])


def test_keys_type_and_ok_gives_the_text():
    window = KeyboardWindow("kb", "Your name")
    screen = opened(window)
    assert not window.find("kb.ok").enabled  # nothing typed yet
    assert click(screen, window, "key.1.4", "key.1.0", "space", "key.0.0") == []  # t q _ 1
    assert window.text == "Tq 1"  # the first in capitals
    assert window.find("kb.text").text == "Tq 1_"
    assert window.find("kb.count").text == "4 / 32"
    assert click(screen, window, "backspace") == []
    assert click(screen, window, "ok") == [Event("s", "kb", "Tq ")]
    assert screen.window is None


def test_an_empty_line_is_not_confirmed_unless_allowed():
    window = KeyboardWindow("kb", "Name")
    screen = opened(window)
    assert click(screen, window, "ok") == []
    assert screen.window is window
    allowed = KeyboardWindow("kb", "Seed", allow_empty=True)
    screen = opened(allowed)
    assert click(screen, allowed, "ok") == [Event("s", "kb", "")]


def test_shift_releases_after_one_key_and_locks_when_pressed_twice():
    window = KeyboardWindow("kb", "Name", "a")
    screen = opened(window)
    assert window.find("kb.shift").text == icon_text(SHIFT)
    click(screen, window, "shift")
    assert window.find("kb.key.1.0").text == "Q" and window.find("kb.shift").text == icon_text(SHIFT_ON)
    click(screen, window, "key.1.0", "key.1.0")
    assert window.text == "aQq"
    click(screen, window, "shift", "shift")  # caps lock
    assert window.find("kb.shift").text == icon_text(CAPS_LOCK)
    click(screen, window, "key.1.1", "key.1.2", "key.0.0")
    assert window.text == "aQqWE1"
    click(screen, window, "shift")
    assert window.shift == "off" and window.find("kb.key.1.0").text == "q"


def test_the_first_character_is_shifted_unless_not_capitalizing():
    window = KeyboardWindow("kb", "Name")
    screen = opened(window)
    assert window.shift == "once" and window.find("kb.shift").text == icon_text(SHIFT_ON)
    click(screen, window, "key.1.0", "key.1.0")
    assert window.text == "Qq"
    click(screen, window, "backspace", "backspace")
    assert window.text == "" and window.shift == "once"  # emptied: the next is a capital again
    click(screen, window, "shift", "shift")  # turned off for it (on, locked, off): stays off
    click(screen, window, "key.1.0")
    assert window.text == "q"
    plain = KeyboardWindow("kb", "Seed", capitalize=False)
    opened(plain)
    assert plain.shift == "off"


def test_a_full_line_greys_the_character_keys_and_moves_the_focus_to_ok():
    window = KeyboardWindow("kb", "Name", "abc", max_length=4)
    screen = opened(window)
    window.state.focused = "kb.key.1.0"
    click(screen, window, "key.1.0")
    assert window.text == "abcq" and window.full
    assert not window.find("kb.key.1.0").enabled and not window.find("kb.space").enabled
    assert window.find("kb.backspace").enabled and window.find("kb.ok").enabled
    assert window.state.focused == "kb.ok"
    click(screen, window, "key.1.1", "space")
    assert window.text == "abcq"
    assert window.find("kb.text").text == "abcq"  # no caret on a full line


def test_cancelling_gives_none_and_leaves_the_box():
    box = TextBox("name", "Ada", keyboard=True)
    window = KeyboardWindow("name.keyboard", "Name", box.text, box="name")
    screen = opened(window, box)
    click(screen, window, "key.1.0")
    screen.close_window(window)  # what the close button and Esc do, with this event
    assert dispatch(screen, [Event("s", "name.keyboard", None)]) == [Event("s", "name.keyboard", None)]
    assert box.text == "Ada"


def test_with_a_box_ok_sets_its_text_and_gives_its_event():
    box = TextBox("name", "Ada", keyboard=True)
    window = KeyboardWindow("name.keyboard", "Name", box.text, box="name")
    screen = opened(window, box)
    assert click(screen, window, "key.1.0", "ok") == [Event("s", "name", "Adaq")]
    assert box.text == "Adaq"


def test_the_pads_buttons_come_in_through_the_nav():
    window = KeyboardWindow("kb", "Name", "ab")
    opened(window)
    steered = window.navigate(Nav(delete=True), Typed())
    assert window.text == "a" and steered.nav == Nav()
    window.navigate(Nav(space=True), Typed())
    window.navigate(Nav(shift=True), Typed())
    assert window.text == "a " and window.shift == "once"
    steered = window.navigate(Nav(confirm=True), Typed())
    assert steered.clicks == ("kb.ok",)
    steered = window.navigate(Nav(move="down", activate=True), Typed())
    assert steered.nav == Nav(move="down", activate=True)  # left for the focus to move and click a key


def test_back_deletes_and_cancels_only_an_empty_line():
    window = KeyboardWindow("kb", "Name", "a")
    opened(window)
    steered = window.navigate(Nav(back=True), Typed())
    assert window.text == "" and not steered.nav.back
    steered = window.navigate(Nav(back=True), Typed())
    assert steered.nav.back  # draw closes the window with Event(screen, kb, None)


def test_a_physical_keyboard_types_only_the_layouts_characters():
    window = KeyboardWindow("kb", "Name", max_length=6)
    opened(window)
    window.navigate(Nav(), Typed("Zoë-1!"))
    assert window.text == "Zo-1"  # no key for ë or !
    window.navigate(Nav(back=True, activate=True), Typed(backspace=True))  # the app's nav for the same Backspace
    assert window.text == "Zo-"
    steered = window.navigate(Nav(activate=True), Typed(enter=True))
    assert steered.clicks == ("kb.ok",) and not steered.nav.activate


def laid_out(window: KeyboardWindow) -> list:
    arrange(window.root, Rect(0, 0, 600, 400), measure)
    return focusables(window.root)


def test_the_focus_moves_over_the_key_rows_and_wraps_at_their_ends():
    window = KeyboardWindow("kb", "Name")
    nodes = laid_out(window)
    assert window.state.focused == "kb.key.0.0"
    assert step(nodes, "kb.key.0.0", "down") == "kb.key.1.0"
    assert step(nodes, "kb.key.1.4", "right") == "kb.key.1.5"
    assert step(nodes, "kb.key.3.0", "down") == "kb.space"  # straight below Z in this layout (Shift ends left of it)
    steered = window.navigate(Nav(move="left"), Typed())
    assert window.state.focused == "kb.key.0.9" and steered.nav.move is None
    window.navigate(Nav(move="right"), Typed())
    assert window.state.focused == "kb.key.0.0"
    window.state.focused = "kb.key.0.4"
    window.navigate(Nav(move="left"), Typed())
    assert window.state.focused == "kb.key.0.3"
    assert window.navigate(Nav(move="up"), Typed()).nav.move == "up"  # up and down: the spatial step's


def test_right_along_the_bottom_row_keeps_to_it():
    window = KeyboardWindow("kb", "Name", "a")
    laid_out(window)
    window.state.focused = "kb.shift"
    visited = []
    for _ in range(4):
        steered = window.navigate(Nav(move="right"), Typed())
        assert steered.nav.move is None
        visited.append(window.state.focused)
    assert visited == ["kb.space", "kb.backspace", "kb.ok", "kb.shift"]


def test_the_bottom_row_wraps_past_a_greyed_ok():
    window = KeyboardWindow("kb", "Name")
    window.state.focused = "kb.backspace"
    window.navigate(Nav(move="right"), Typed())
    assert window.state.focused == "kb.shift"  # OK is greyed on an empty line


def test_a_text_box_takes_the_focus_when_enabled():
    root = Column(children=[TextBox("name", ""), TextBox("off", "", enabled=False), Button("go", "Go")])
    arrange(root, Rect(0, 0, 400, 300), measure)
    assert [placed.node.id for placed in focusables(root)] == ["name", "go"]


def test_a_focused_keyboard_window_takes_the_keys():
    manager = ScreenManager()
    screen = Screen("s", Column(children=[TextBox("name", "", keyboard=True)]))
    manager.push(screen)
    assert keyboard_free(manager)
    screen.open(KeyboardWindow("kb", "Name"))
    assert not keyboard_free(manager)


def test_a_scaled_keyboard_doubles_its_keys_labels_line_and_bottom_row():
    window = KeyboardWindow("kb", "Name", scale=2.0)
    key, text, count = window.find("kb.key.0.0"), window.find("kb.text"), window.find("kb.count")
    assert window.root.text_scale == 2.0 and window.width == 2 * WINDOW_WIDTH
    assert (key.width, key.height) == (2 * KEY, 2 * KEY) == (80, 80)
    assert text_size(key, window.root.text_scale) == 32
    assert text_size(text, window.root.text_scale) == 2 * LINE == 64
    assert text_size(count, window.root.text_scale) == 2 * SMALL
    assert [window.find(f"kb.{name}").height for name in ("shift", "space", "backspace", "ok")] == [80] * 4
    arrange(window.root, Rect(0, 0, 1000, 800), measure)
    assert (key.rect.width, key.rect.height) == (80, 80)


def test_an_unscaled_keyboard_lays_out_as_before():
    window = KeyboardWindow("kb", "Name")
    key, text = window.find("kb.key.0.0"), window.find("kb.text")
    assert window.root.text_scale == 1.0 and window.root.gap == GAP and window.width == WINDOW_WIDTH
    assert (key.width, key.height, key.size) == (KEY, KEY, None)
    assert (text.size, text.height) == (LINE, LINE + 2 * GAP)
    assert text_size(key, 1.0) == TEXT


def test_the_focus_moves_over_a_scaled_keyboard_as_over_an_unscaled_one():
    window = KeyboardWindow("kb", "Name", "a", scale=2.0)
    arrange(window.root, Rect(0, 0, 1200, 800), measure)  # twice `laid_out`'s: everything lies where it did, twice as far
    nodes = focusables(window.root)
    assert step(nodes, "kb.key.0.0", "down") == "kb.key.1.0"
    assert step(nodes, "kb.key.1.4", "right") == "kb.key.1.5"
    assert step(nodes, "kb.key.3.0", "down") == "kb.space"
    window.navigate(Nav(move="left"), Typed())
    assert window.state.focused == "kb.key.0.9"
    window.state.focused = "kb.shift"
    visited = []
    for _ in range(4):
        window.navigate(Nav(move="right"), Typed())
        visited.append(window.state.focused)
    assert visited == ["kb.space", "kb.backspace", "kb.ok", "kb.shift"]
