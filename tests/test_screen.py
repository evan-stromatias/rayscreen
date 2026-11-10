"""The navigation model: the stack, visible screens under overlays, windows. No window needed."""

from rayscreen.geometry import Rect
from rayscreen.screen import Event, Screen, ScreenManager, Window, keyboard_free, paused_through
from rayscreen.specs import Button, Column, Fill, TextBox
from rayscreen.state import OpenList


def plain(id: str) -> Screen:
    return Screen(id, Column(children=[Fill()]))


def test_stack_push_pop_replace():
    manager = ScreenManager()
    assert manager.top is None
    main, settings = plain("main"), plain("settings")
    manager.push(main)
    manager.push(settings)
    assert manager.top is settings
    assert manager.pop() is settings
    assert manager.top is main
    game = plain("game")
    manager.replace(game)
    assert manager.top is game
    manager.reset(main)
    assert manager.visible() == [main]


def test_visible_is_only_the_top_unless_overlays():
    manager = ScreenManager()
    main, game = plain("main"), plain("game")
    pause = Screen("pause", Column(children=[Fill()]), overlay=True)
    manager.push(main)
    manager.push(game)
    assert manager.visible() == [game]  # a plain top covers what is below
    manager.push(pause)
    assert manager.visible() == [game, pause]  # an overlay lets the screen below draw


def test_overlay_chain_reaches_down_to_the_first_plain_screen():
    manager = ScreenManager()
    main, game = plain("main"), plain("game")
    one = Screen("one", Column(children=[Fill()]), overlay=True)
    two = Screen("two", Column(children=[Fill()]), overlay=True)
    for screen in (main, game, one, two):
        manager.push(screen)
    assert manager.visible() == [game, one, two]


def test_open_window_drops_half_finished_interactions():
    screen = plain("main")
    screen.state.editing = "player"
    screen.state.open_list = OpenList("quality", Rect(0, 0, 100, 26), ("Low",))
    window = Window("quit", "Really quit?", Column(children=[Button("yes", "Quit")]))
    screen.open(window)
    assert screen.window is window
    assert screen.state.editing is None
    assert screen.state.open_list is None
    screen.close_window()
    assert screen.window is None


def test_windows_stack_and_close():
    screen = plain("main")
    bottom = Window("a", "A", Column(children=[Button("a.b", "B")]))
    top = Window("b", "B", Column(children=[Button("b.b", "B")]), modal=False)
    screen.open(bottom)
    screen.open(top)
    assert screen.window is top  # the last one opened is on top
    screen.close_window(bottom)  # close a specific one
    assert screen.window is top and screen.windows == [top]
    screen.close_window()  # and the topmost when not given
    assert screen.window is None


def test_paused_through_with_several_windows():
    screen = plain("game")
    screen.open(Window("quests", "Quests", Column(children=[Button("q", "Q")]), modal=False))
    assert paused_through([screen]) == -1  # a non-pausing floating window pauses nothing
    screen.open(Window("intro", "Hi", Column(children=[Button("ok", "OK")]), pauses=True))
    assert paused_through([screen]) == 0


def test_window_ids_are_checked():
    window = Window("w", "Title", Column(children=[Button("b", "B")]))
    assert window.id == "w"


def test_window_flags():
    window = Window("w", "T", Column(children=[Button("b", "B")]), minimizable=True, closeable=False)
    assert window.minimizable and not window.closeable
    assert window.minimized is False  # runtime state starts expanded
    borderless = Window("w2", "T", Column(children=[Button("b2", "B")]), borderless=True)
    assert borderless.borderless
    default = Window("w3", "T", Column(children=[Button("b3", "B")]))
    assert default.draggable and default.closeable and not default.minimizable and not default.borderless
    assert default.modal and not default.resizable and default.backdrop
    see_through = Window("w5", "T", Column(children=[Button("b5", "B")]), borderless=True, backdrop=False)
    assert not see_through.backdrop
    resizable = Window("w4", "T", Column(children=[Button("b4", "B")]), resizable=True)
    assert resizable.resizable and resizable.resize_offset is None


def test_screen_finds_widgets_by_id():
    screen = Screen("s", Column(children=[Button("go", "Go")]))
    assert isinstance(screen.find("go"), Button)
    assert screen.find("missing") is None


def test_handle_defaults_to_not_consuming():
    assert plain("s").handle(Event("s", "go", None)) is False


def test_paused_through():
    game, pause = plain("game"), plain("pause")
    assert paused_through([game, pause]) == -1  # no windows: nothing paused
    pause.open(Window("quit", "Quit?", Column(children=[Button("yes", "Quit")]), pauses=True))
    assert paused_through([game, pause]) == 1  # the window pauses its own screen and all below
    pause.window.minimized = True
    assert paused_through([game, pause]) == -1  # a minimized window pauses nothing


def test_paused_through_only_reaches_up_to_the_window():
    game, settings = plain("game"), plain("settings")
    game.open(Window("intro", "Hi", Column(children=[Button("ok", "OK")]), pauses=True))
    # settings was pushed over the pausing window: it is in front of it and keeps running
    assert paused_through([game, settings]) == 0
    game.window.pauses = False
    assert paused_through([game, settings]) == -1


def floating(id: str) -> Window:
    return Window(id, id, Button(f"{id}.ok", "OK"), modal=False)


def test_opening_a_window_focuses_it_unless_asked_not_to():
    screen = plain("game")
    quests = floating("quests")
    screen.open(quests, focus=False)
    assert screen.focus is None
    inventory = floating("inventory")
    screen.open(inventory)
    assert screen.focus is inventory


def test_a_modal_window_always_takes_the_focus_and_keeps_it():
    screen = plain("game")
    quests, dialog = floating("quests"), Window("dialog", "Dialog", Button("ok", "OK"))
    screen.open(quests)
    screen.open(dialog, focus=False)
    assert screen.focus is dialog
    screen.focus_window(quests)
    screen.focus_window(None)
    assert screen.focus is dialog


def test_closing_the_focused_window_hands_the_focus_back():
    # the game screen's case: the quest log opens in the background, the intro over it; once the
    # intro closes, the screen has the focus again, so Esc pauses instead of closing the quest log
    screen = plain("game")
    quests, intro = floating("quests"), Window("intro", "Intro", Button("ok", "OK"))
    screen.open(quests, focus=False)
    screen.open(intro)
    screen.close_window(intro)
    assert screen.focus is None
    screen.focus_window(quests)
    dialog = Window("dialog", "Dialog", Button("yes", "Yes"))
    screen.open(dialog)
    screen.close_window()
    assert screen.focus is quests


def test_closing_a_window_skips_it_in_the_chain_of_focuses():
    screen = plain("game")
    one, two, three = floating("one"), floating("two"), floating("three")
    screen.open(one)
    screen.open(two)
    screen.open(three)
    screen.close_window(two)
    screen.close_window(three)
    assert screen.focus is one


def test_focusing_a_window_raises_it():
    screen = plain("game")
    one, two = floating("one"), floating("two")
    screen.open(one)
    screen.open(two)
    screen.focus_window(one)
    assert screen.windows == [two, one]
    screen.focus_window(None)
    assert screen.focus is None and screen.windows == [two, one]


def test_the_keyboard_is_the_apps_unless_a_box_is_being_typed_in():
    manager = ScreenManager()
    game = Screen("game", Column(children=[TextBox("name", "")]))
    manager.push(game)
    assert keyboard_free(manager)
    game.state.editing = "name"
    assert not keyboard_free(manager)
    game.state.editing = None
    window = Window("w", "Window", TextBox("box", ""), modal=False)
    game.open(window)
    window.state.editing = "box"
    assert not keyboard_free(manager)
    manager.push(Screen("map", Column(children=[])))  # the game is not drawn under it: its box does not count
    assert keyboard_free(manager)
