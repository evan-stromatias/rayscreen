"""The demo's screens: a main menu, settings, a load-game list, a fake game with a HUD, and a pause
overlay with a modal quit window. They exercise every widget and both navigation kinds (stack and
window), and they are what `--screenshot` captures. The fake game has stand-in things on its world
(a villager, a chest, a minimap) with tooltips and context menus; the drag scene, a pack's window of boxes whose
things are dragged to another box or out onto the screen.
"""

import json
import math
from pathlib import Path
from typing import NamedTuple

import pyray as rl

from rayscreen.data import data_tree
from rayscreen.file_window import FileWindow, format_size
from rayscreen.keyboard_window import KeyboardWindow
from rayscreen.navigation import Direction, focusables, step
from rayscreen.screen import Drop, Event, Screen, ScreenManager, Window
from rayscreen.specs import (
    CHECK,
    GAP,
    PAD,
    ROW,
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
    MenuItem,
    Node,
    Panel,
    Picture,
    Placed,
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
from rayscreen.state import Dragging

SAVES = tuple(f"Save {i:2d} - Ashford, day {i}" for i in range(1, 13))


def quit_window() -> Window:
    """The modal "Really quit?" dialog: not closeable, so the choice is forced."""
    return Window(
        "quit",
        "Really quit?",
        Column(
            children=[
                Label("quit-text", "Unsaved progress will be lost."),
                Row(children=[Button("quit.yes", "Quit", weight=1), Button("quit.no", "Cancel", weight=1)]),
            ]
        ),
        minimizable=True,
        closeable=False,
        pauses=True,
    )


def intro_window() -> Window:
    """The floating window the game screen opens with: borderless, dragged by clicking anywhere in
    it that is not a widget, and pausing the game behind it."""
    return Window(
        "intro",
        "Ashford - day 1",
        Column(
            children=[
                Label("intro-text", "The sun rises over Ashford. Your journey begins at the plaza, with 12 gold to your name.", wrap=True),
                Button("intro.ok", "Continue"),
            ]
        ),
        borderless=True,
        pauses=True,
    )


QUESTS = (
    ("Sunflowers", "Pick six sunflowers for the innkeeper."),
    ("The lost goat", "Find the miller's goat in the hills."),
    ("Bridge toll", "Pay or charm the bridge keeper."),
    ("Old ruins", "Map the ruins north of Ashford."),
    ("Rat cellar", "Clear the rats out of the tavern's cellar."),
    ("Herb list", "Gather thyme and sage for the healer."),
)


def quests_window() -> Window:
    """A floating quest log beside the game: not modal, so the game keeps running behind it; too
    small for its quests, so it scrolls; resizable by its bottom-right grip. Each description is
    indented under its check box's text."""
    children: list = []
    for i, (title, text) in enumerate(QUESTS):
        children.append(CheckBox(f"track-{i}", title))
        description = Label(f"quest-{i}", text, size=SMALL, wrap=True, tone="muted")
        children.append(Row(children=[Fill(weight=0, size=CHECK + GAP), description], gap=0))
    window = Window("quests", "Quests", Scroll("quests-scroll", Column(children=children), weight=1), size=(360, 170), modal=False, resizable=True, minimizable=True)
    window.position = (40, 90)
    return window


SCENE_GROUPS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "Menus & Stack",
        (
            ("main", "Main menu screen"),
            ("settings", "Settings panels, sliders, toggles & dropdown"),
            ("load", "Save-game ListView selection"),
        ),
    ),
    (
        "Game HUD, Windows & Popups",
        (
            ("game", "Game HUD, compass, quest log & intro modal"),
            ("quests", "Floating resizable quest log over live game"),
            ("pause", "Overlay screen dimming the game below"),
            ("dialog", "Modal confirmation window over pause screen"),
            ("minimized", "Window collapsed to its title bar"),
            ("tooltip", "Dynamic widget tree tooltip on hover"),
            ("menu", "Context menu opened on the world"),
        ),
    ),
    (
        "Widgets & Layouts",
        (
            ("gallery", "Split, validation errors, grid, rich text & bars"),
            ("drag", "Pack grid drag-and-drop & drop onto world"),
            ("drag-held", "Active drag ghost held under cursor"),
            ("chat", "Follow scroll & submit TextBox"),
            ("keyboard", "On-screen keyboard for a pad, from a TextBox"),
            ("keyboard-large", "The keyboard and its form at a TV's text scale"),
            ("nav", "Character form moved through with the keys or a pad"),
            ("board", "Fixed-aspect Board with Placed slots"),
        ),
    ),
    (
        "File & Directory Dialogs",
        (
            ("files", "PNG loader preview & directory bundle saver"),
            ("files-load", "FileWindow in load_file mode (*.png)"),
            ("files-save", "FileWindow in directory mode"),
        ),
    ),
)


def open_scene(manager: ScreenManager, scene: str) -> None:
    """Push the screen(s) for `scene` onto `manager`."""
    if scene == "scenes":
        manager.push(ScenesScreen(manager))
    elif scene == "main":
        manager.push(MainScreen(manager))
    elif scene == "settings":
        manager.push(SettingsScreen(manager))
    elif scene == "load":
        manager.push(LoadScreen(manager))
    elif scene == "gallery":
        manager.push(GalleryScreen(manager))
    elif scene == "board":
        manager.push(BoardScreen(manager))
    elif scene == "chat":
        manager.push(ChatScreen(manager))
    elif scene == "nav":
        manager.push(NavScreen(manager))
    elif scene in ("keyboard", "keyboard-large"):
        keyboard = KeyboardScreen(manager, large=scene == "keyboard-large")
        manager.push(keyboard)
        keyboard.open_keyboard()
    elif scene in ("files", "files-load", "files-save"):
        files = FilesScreen(manager)
        manager.push(files)
        if scene == "files-load":
            files.open_load_window()
        elif scene == "files-save":
            files.open_save_window()
    elif scene in ("drag", "drag-held"):
        manager.push(DragScreen(manager, held=scene == "drag-held"))
    else:
        game = GameScreen(manager)
        manager.push(game)
        if scene in ("quests", "tooltip", "menu"):
            game.close_window()  # dismiss the intro, leaving the quest log floating
        if scene == "tooltip" and rl.is_window_ready():
            x, y = MIRA.centre(rl.get_screen_width(), rl.get_screen_height())
            rl.set_mouse_position(int(x), int(y))
        if scene == "menu":
            width = rl.get_screen_width() if rl.is_window_ready() else 1000
            height = rl.get_screen_height() if rl.is_window_ready() else 700
            x, y = MIRA.centre(width, height)
            menu = game.menu(x, y)
            if menu is not None:
                game.open_menu(menu, x, y)
        if scene in ("pause", "dialog", "minimized"):
            game.close_window()  # as if the intro window had been dismissed
            pause = PauseScreen(manager)
            manager.push(pause)
            if scene == "dialog":
                pause.open(quit_window())
            elif scene == "minimized":
                window = quit_window()
                pause.open(window)
                window.minimized = True


class ScenesScreen(Screen):
    """The launcher screen shown when `rayscreen-demo` starts without `--screen`: buttons for every demo scene."""

    def __init__(self, manager: ScreenManager) -> None:
        self.manager = manager
        left_panels = [self._group_panel(*group) for group in SCENE_GROUPS[:2]]
        right_panels = [self._group_panel(*group) for group in SCENE_GROUPS[2:]]
        columns = Row(
            children=[
                Column(children=left_panels, gap=2 * GAP, weight=1),
                Column(children=right_panels, gap=2 * GAP, weight=1),
            ],
            gap=2 * PAD,
        )
        super().__init__(
            "scenes",
            Column(
                children=[
                    Label("heading", "RAYSCREEN DEMO", size=32, height=40),
                    Label(
                        "subtitle",
                        "Pick a scene below (Esc or Back returns here).",
                        size=SMALL,
                        tone="muted",
                    ),
                    Scroll("scenes.scroll", columns, weight=1),
                    Row(children=[Fill(), Button("quit", "Quit")]),
                ],
                gap=2 * GAP,
            ),
            margin=2 * PAD,
        )

    @staticmethod
    def _group_panel(title: str, items: tuple[tuple[str, str], ...]) -> Panel:
        rows: list[list[Node]] = [
            [
                Button(f"scene.{name}", name, width=116, align="left"),
                Label(f"scene.{name}.desc", desc, size=SMALL, tone="muted", elide=True),
            ]
            for name, desc in items
        ]
        return Panel(title=title, child=Table(rows, gap=PAD, row_gap=GAP, stretch=True))

    def handle(self, event: Event) -> bool:
        if event.widget.startswith("scene."):
            scene = event.widget.removeprefix("scene.")
            open_scene(self.manager, scene)
            return True
        return False


class MainScreen(Screen):
    def __init__(self, manager: ScreenManager) -> None:
        self.manager = manager
        super().__init__(
            "main",
            Column(
                children=[
                    Fill(weight=2),
                    Label("title", "RAYSCREEN DEMO", size=48, height=64, align="center"),
                    Fill(),
                    Row(
                        children=[
                            Fill(weight=3),
                            Column(
                                children=[
                                    Button("new", "New Game"),
                                    Button("load", "Load Game"),
                                    Button("files", "Files"),
                                    Button("settings", "Settings"),
                                    Button("quit", "Quit"),
                                ],
                                weight=2,
                            ),
                            Fill(weight=3),
                        ]
                    ),
                    Fill(weight=3),
                ]
            ),
        )

    def handle(self, event: Event) -> bool:
        if event.widget == "new":
            self.manager.replace(GameScreen(self.manager))
        elif event.widget == "load":
            self.manager.push(LoadScreen(self.manager))
        elif event.widget == "files":
            self.manager.push(FilesScreen(self.manager))
        elif event.widget == "settings":
            self.manager.push(SettingsScreen(self.manager))
        else:
            return False  # "quit" is the app's call
        return True


def setting(label: str, control: Toggle | Dropdown) -> Row:
    """A setting's name on the left and its control, at its natural width, on the right."""
    return Row(children=[Label(f"{control.id}-label", label), Fill(), control])


class SettingsScreen(Screen):
    """The panels scroll; the heading and the Back button stay put above and below them."""

    def __init__(self, manager: ScreenManager) -> None:
        self.manager = manager
        super().__init__(
            "settings",
            Column(
                children=[
                    Label("heading", "Settings", size=32, height=48),
                    Scroll(
                        "settings-scroll",
                        Column(
                            children=[
                                Panel(
                                    title="Audio",
                                    child=Column(
                                        children=[
                                            Slider("volume", "Volume", 70.0, 0.0, 100.0),
                                            setting("Music", Toggle("music", "On", True)),
                                        ]
                                    ),
                                ),
                                Panel(
                                    title="Video",
                                    child=Column(
                                        children=[
                                            CheckBox("fullscreen", "Fullscreen", False),
                                            setting("VSync", Toggle("vsync", "On", True)),
                                            setting("Quality", Dropdown("quality", ("Low", "Medium", "High"), 1)),
                                        ]
                                    ),
                                ),
                                Panel(
                                    title="Player",
                                    child=Column(children=[TextBox("player", "Evan")]),
                                ),
                            ],
                            gap=2 * GAP,
                        ),
                        weight=1,
                    ),
                    Row(children=[Fill(), Button("back", "Back")]),
                ],
                gap=2 * GAP,
            ),
            margin=2 * PAD,
        )

    def handle(self, event: Event) -> bool:
        if event.widget == "back":
            self.manager.pop()
            return True
        toggle = self.find(event.widget)
        if isinstance(toggle, Toggle):
            toggle.text = "On" if event.value else "Off"
        return False


class LoadScreen(Screen):
    """Load is greyed until a save is picked."""

    def __init__(self, manager: ScreenManager) -> None:
        self.manager = manager
        self._saves = ListView("saves", SAVES, weight=1)
        self._load = Button("load", "Load", enabled=False)
        super().__init__(
            "load",
            Column(
                children=[
                    Label("heading", "Load Game", size=32, height=48),
                    self._saves,
                    Row(children=[Fill(), Button("back", "Back"), self._load]),
                ],
                gap=2 * GAP,
            ),
            margin=2 * PAD,
        )

    def update(self, dt: float) -> None:
        self._load.enabled = self._saves.selected >= 0

    def handle(self, event: Event) -> bool:
        if event.widget == "back":
            self.manager.pop()
        elif event.widget == "load":
            self.manager.replace(GameScreen(self.manager))
        else:
            return False
        return True


class Thing(NamedTuple):
    """A stand-in for an entity of the game's world: where it is, as fractions of the window, and its
    half-size in pixels. The game would pick its entities with a ray instead."""

    key: str
    name: str
    x: float
    y: float
    half: float

    def centre(self, width: float, height: float) -> tuple[float, float]:
        return self.x * width, self.y * height

    def contains(self, px: float, py: float, width: float, height: float) -> bool:
        cx, cy = self.centre(width, height)
        return abs(px - cx) <= self.half and abs(py - cy) <= self.half


MIRA = Thing("mira", "Mira", 0.62, 0.5, 22.0)
CHEST = Thing("chest", "Old chest", 0.35, 0.72, 18.0)
MINIMAP = (140.0, 100.0)  # its size, in the bottom-right corner above the hint
WORLD_SIZE = 4096.0  # metres the minimap spans
COMPASS = 96  # pixels across the round compass, a see-through window dragged anywhere


def compass_window(width: float) -> Window:
    """A round picture in a borderless window with no backdrop, so the world shows round it; dragged by
    any point of it. Its texture is drawn by `GameScreen.draw_world`, as a game renders its minimap."""
    side = COMPASS + 2 * PAD
    window = Window("compass", "Compass", Picture("compass.picture", size=(COMPASS, COMPASS), flipped=True),
                    size=(side, side), borderless=True, backdrop=False, modal=False, closeable=False)
    window.position = (width - side - PAD, ROW + 3 * PAD)  # under the HUD bar, at the right
    return window


class GameScreen(Screen):
    """A green stand-in for the game, with a HUD bar on top, so overlays and windows have something
    to float over, and things on its world: a villager, a chest and a minimap, each with a tooltip,
    and context menus on them and on bare ground."""

    def __init__(self, manager: ScreenManager) -> None:
        self.manager = manager
        self._time = 0.0
        self._hp = Progress("hp", 0.8, weight=3)
        self._hint = Label("hint", "Esc: pause menu. Rest the mouse on the villager, the chest or the map; right-click.", size=SMALL, align="center")
        super().__init__(
            "game",
            Column(
                children=[
                    Panel(
                        child=Row(
                            children=[
                                Label("hp-label", "HP"),
                                self._hp,
                                Label("gold", "Gold: 12"),
                            ],
                            gap=PAD,
                        ),
                        fill=True,
                    ),
                    Fill(),
                    Panel(self._hint, backdrop=0.6),
                ]
            ),
            margin=PAD,
        )
        self._compass: rl.RenderTexture | None = None
        self.open(compass_window(rl.get_screen_width()), focus=False)
        # the quest log opens in the background: Esc pauses the game until the log is clicked
        self.open(quests_window(), focus=False)  # below the intro: the modal dialog is on top until dismissed
        self.open(intro_window())

    def update(self, dt: float) -> None:
        self._time += dt
        self._hp.value = 0.5 + 0.4 * math.sin(self._time)

    def handle(self, event: Event) -> bool:
        if event.widget in ("intro.ok", "intro"):  # Continue, the close button, or Esc
            self.close_window()
            return True
        if event.widget in ("npc", "chest", "ground"):  # a context menu's choice, or None: dismissed
            if event.value is not None:
                self._hint.text = f"Chose {event.value!r} on {event.target}"
            return True
        return False

    def draw_world(self) -> None:
        """What the game's render system would draw under the screen: a field and its things."""
        width, height = rl.get_screen_width(), rl.get_screen_height()
        rl.draw_rectangle(0, 0, width, height, rl.Color(122, 140, 110, 255))  # light enough for ink labels
        x, y = MIRA.centre(width, height)
        rl.draw_circle(int(x), int(y), MIRA.half, rl.Color(196, 120, 90, 255))
        x, y = CHEST.centre(width, height)
        rl.draw_rectangle(int(x - CHEST.half), int(y - CHEST.half), int(2 * CHEST.half), int(2 * CHEST.half), rl.Color(120, 84, 50, 255))
        map_rect = self._minimap(width, height)
        rl.draw_rectangle_rec(map_rect, rl.Color(80, 104, 80, 255))
        rl.draw_rectangle_lines_ex(map_rect, 1, rl.Color(38, 42, 50, 255))
        self._draw_compass()

    def _draw_compass(self) -> None:
        """A disc with a needle, into the compass window's texture, its corners left transparent."""
        if self._compass is None:
            self._compass = rl.load_render_texture(COMPASS, COMPASS)
        half = COMPASS / 2
        rl.begin_texture_mode(self._compass)
        rl.clear_background(rl.BLANK)
        rl.draw_circle(int(half), int(half), half - 1, rl.Color(38, 42, 50, 230))
        rl.draw_ring(rl.Vector2(half, half), half - 4, half - 1, 0, 360, 48, rl.Color(230, 235, 240, 255))
        angle = self._time * 0.5
        tip = rl.Vector2(half + math.sin(angle) * (half - 12), half - math.cos(angle) * (half - 12))
        tail = rl.Vector2(half - math.sin(angle) * (half - 12), half + math.cos(angle) * (half - 12))
        rl.draw_line_ex(tail, tip, 4, rl.Color(230, 235, 240, 255))
        rl.draw_circle_v(tip, 6, rl.Color(200, 60, 50, 255))
        rl.end_texture_mode()
        window = next(window for window in self.windows if window.id == "compass")
        window.root.texture = self._compass.texture

    def unload(self) -> None:
        if self._compass is not None:
            rl.unload_render_texture(self._compass)
            self._compass = None

    def _minimap(self, width: float, height: float) -> rl.Rectangle:
        w, h = MINIMAP
        return rl.Rectangle(width - w - PAD, height - h - 3 * PAD - TEXT - 10, w, h)  # above the hint's panel

    def _thing_at(self, x: float, y: float) -> Thing | None:
        width, height = rl.get_screen_width(), rl.get_screen_height()
        return next((thing for thing in (MIRA, CHEST) if thing.contains(x, y, width, height)), None)

    def hover(self, x: float, y: float) -> Tooltip | None:
        thing = self._thing_at(x, y)
        if thing is MIRA:
            # the HP bar moves while the mouse rests: the content follows, the key keeps the box up
            root = Column(
                children=[
                    Label("name", "Mira", height=TEXT + 4),
                    Label("about", "The miller's daughter. She is looking for her goat.", size=SMALL, wrap=True, tone="muted"),
                    Progress("hp", self._hp.value, height=12),
                ]
            )
            return Tooltip("mira", root, width=220)
        if thing is CHEST:
            return Tooltip.text("chest", "Old chest", "Locked. Something rattles inside.")
        map_rect = self._minimap(rl.get_screen_width(), rl.get_screen_height())
        if rl.check_collision_point_rec(rl.Vector2(x, y), map_rect):
            east = (x - map_rect.x) / map_rect.width * WORLD_SIZE
            south = (y - map_rect.y) / map_rect.height * WORLD_SIZE
            return Tooltip.text("minimap", "Map", f"x {east:.0f} m, z {south:.0f} m")
        return None

    def menu(self, x: float, y: float) -> Menu | None:
        thing = self._thing_at(x, y)
        if thing is MIRA:
            items = [MenuItem("talk", "Talk"), MenuItem("trade", "Trade", enabled=False), MenuItem("inspect", "Inspect")]
            return Menu("npc", items, title="Mira", target="mira")
        if thing is CHEST:
            return Menu("chest", [MenuItem("open", "Open"), MenuItem("take", "Take all")], title="Old chest", target="chest")
        return Menu("ground", [MenuItem("walk", "Walk here")], target=(round(x), round(y)))


class PauseScreen(Screen):
    def __init__(self, manager: ScreenManager) -> None:
        self.manager = manager
        super().__init__(
            "pause",
            Column(
                children=[
                    Fill(),
                    Row(
                        children=[
                            Fill(weight=2),
                            Panel(
                                title="Paused",
                                fill=True,
                                child=Column(
                                    children=[
                                        Button("resume", "Resume"),
                                        Button("settings", "Settings"),
                                        Button("quit-menu", "Quit to Menu"),
                                    ]
                                ),
                            ),
                            Fill(weight=2),
                        ]
                    ),
                    Fill(),
                ]
            ),
            overlay=True,
        )

    def handle(self, event: Event) -> bool:
        if event.widget == "resume":
            self.manager.pop()
        elif event.widget == "settings":
            self.manager.push(SettingsScreen(self.manager))
        elif event.widget == "quit-menu":
            self.open(quit_window())
        elif event.widget == "quit.no" or (event.widget == "quit" and event.value is None):
            self.close_window()  # Cancel, the window's close button, or Esc
        else:
            return False  # "quit.yes" is the app's call
        return True


def pattern(size: int, hue: int) -> rl.Texture:
    """A checkered stand-in for a rendered view, made on the GPU (call with the window open)."""
    image = rl.gen_image_checked(size, size, size // 8, size // 8, rl.color_from_hsv(hue, 0.35, 0.85), rl.color_from_hsv(hue, 0.5, 0.6))
    texture = rl.load_texture_from_image(image)
    rl.unload_image(image)
    return texture


class GalleryScreen(Screen):
    """A gallery with a picture filling the left, a box with a problem under it, disabled boxes, and a grid of
    clickable thumbnails that wraps to the width; the two halves are a split, its bar dragged left and right."""

    def __init__(self, manager: ScreenManager) -> None:
        self.manager = manager
        self.textures = [pattern(256, 120), *(pattern(64, 30 * i) for i in range(12))]
        view = Picture("view", self.textures[0], (256, 256), weight=1)
        thumbs = [
            Column(children=[Picture(f"thumb-{i}", texture, (64, 64), clickable=True, height=88), Label(f"thumb-{i}.seed", f"seed {i + 1}", size=SMALL, align="center")], gap=0)
            for i, texture in enumerate(self.textures[1:])
        ]
        self._status = Label("status", "Click a thumbnail.", size=SMALL, tone="muted")
        form = Column(
            children=[
                Panel(
                    title="Problems",
                    child=Column(
                        children=[
                            Row(children=[Label("height-label", "Wall height"), TextBox("height", "-2", invalid=True, weight=1)]),
                            Label("height.problem", "towns.layout.walls.height: must be above 0", size=SMALL, tone="error"),
                        ]
                    ),
                ),
                Panel(
                    title="Disabled",
                    child=Column(
                        children=[
                            Row(children=[CheckBox("temple.on", "temple", False), TextBox("temple", "14.0", enabled=False, weight=1)]),
                            Row(children=[CheckBox("castle.on", "castle", True), TextBox("castle", "12.0", weight=1)]),
                            Row(children=[CheckBox("locked", "locked", True, enabled=False), Button("build", "Build", enabled=False)]),
                        ]
                    ),
                ),
                Panel(title="Seeds", child=Grid(thumbs, cell=88, gap=GAP)),
                Panel(title="Text", child=formatted_text()),
                Panel(title="Stages", child=stages()),
                Panel(title="Bars", child=bars()),
                self._status,
            ]
        )
        super().__init__(
            "gallery",
            Split("gallery-split", Column(children=[Label("heading", "Gallery", size=32, height=48), view]), Scroll("gallery-scroll", form, weight=1),
                  minimum=(200.0, 360.0)),
            margin=2 * PAD,
        )

    def handle(self, event: Event) -> bool:
        if event.widget.startswith("thumb-"):
            self._status.text = f"Opened {event.widget}."
            return True
        box = self.find(event.widget.removesuffix(".on"))
        if event.widget.endswith(".on") and isinstance(box, TextBox):  # a check box turns its box on and off
            box.enabled = bool(event.value)
            return True
        if event.widget == "height" and isinstance(box, TextBox):
            box.invalid = not _positive(str(event.value))
            return True
        return False

    def unload(self) -> None:
        for texture in self.textures:
            rl.unload_texture(texture)


def formatted_text() -> Column:
    """Spans in tones, a separator, a key/value table with a right-aligned column and a note spanning it, a
    bulleted list whose items wrap under their own text, and plain data as a tree (`data_tree`)."""
    def fact(i: int, name: str, value: str) -> list[Node]:
        return [Label(f"fact.{i}", name, height=SMALL + 4, size=SMALL, tone="muted"), Label(f"fact.{i}.value", value, height=SMALL + 4, size=SMALL)]

    facts = Table([fact(0, "radius", "130 m"), fact(1, "buildings", "246"), fact(2, "gates", "2"),
                   [Text.of("fact.note", Span("walls ", "muted"), "yes", Span(", citadel ", "muted"), "no", size=SMALL)]],
                  align=("left", "right"))
    items = [("Bad walled area shape!", 1), ("Bad citadel shape, which is a longer cause and wraps under itself", 3)]
    bullets = Table([[Label(f"item.{i}.bullet", "–", height=SMALL + 4, size=SMALL, tone="muted"), Text.of(f"item.{i}", Span(f"{count} × ", "muted"), cause, size=SMALL)]
                     for i, (cause, count) in enumerate(items)], gap=GAP)
    return Column(children=[
        Text.of("spans", "A text of spans: ", Span("muted", "muted"), ", ink and ", Span("an error", "error"), ", wrapped as one flow."),
        Separator(),
        facts,
        Separator(),
        bullets,
        Separator(),
        data_tree("data", {"reply": "Safe enough.", "feeling": {"mood": "content", "intensity": "very"}, "turns": 3,
                           "ended": None, "tools": ["end_conversation(reason='rude')"]}),
    ])


def bars() -> Panel:
    """A HUD's bar: vertical bars in their own colours, each with its tooltip, and toggles with theirs, on a solid
    backdrop panel (the mouse over it, between the widgets too, is the panel's)."""
    meters = [Column(children=[Progress(f"bar.{name}", value, vertical=True, width=22, height=72, colour=colour,
                                        tooltip=Tooltip.text(f"bar.{name}", name, f"{round(value * 40)} of 40")),
                               Label(f"bar.{name}.label", name[:2].upper(), size=SMALL, height=SMALL + 4)], gap=GAP)
              for name, value, colour in (("health", 0.85, (200, 60, 50)), ("stamina", 0.4, (150, 190, 60)),
                                          ("mana", 1.0, (70, 120, 220)))]
    toggles = Column(children=[Toggle("bar.inventory", "Inventory", tooltip=Tooltip.text("bar.inventory", "Inventory (I)")),
                               Toggle("bar.map", "Map", True, tooltip=Tooltip.text("bar.map", "Map (M)"))], width=120)
    return Panel(Row(children=[*meters, Fill(), toggles]), backdrop=0.85, solid=True)


def stages() -> Column:
    """A form with stage headers (left-aligned buttons, an arrow saying whether the section is open) whose status
    reads in its tone, a field whose name gives its help as a tooltip, and a rule card with buttons and colour."""
    def header(i: int, title: str, status: str, tone: Tone, opened: bool) -> Row:
        arrow = "#116#" if opened else "#115#"  # raygui's down and right arrows
        return Row(children=[
            Button(f"stage.{i}", f"{arrow}{i} {title}", align="left", weight=1),
            Label(f"stage.{i}.status", status, size=SMALL, tone=tone),
            Button(f"stage.{i}.reset", "#56#", width=ROW),
            Button(f"stage.{i}.run", "#131#Run"),
        ])

    help_tip = Tooltip.text("help.flow", "min_flow", "Cells draining at least this many cells become rivers (at least 1).")
    return Column(children=[
        header(1, "elevation", "done 5.66 s", "ok", False),
        header(2, "hydrology", "running 4.0 s", "info", True),
        Row(children=[Label("flow.label", "min_flow", weight=1, tooltip=help_tip), TextBox("flow", "400", weight=1)]),
        Row(children=[
            Button("rule.2", "#115#2. temperate_forest", align="left", weight=1),
            Button("rule.2.up", "#117#", width=ROW),
            Button("rule.2.down", "#116#", width=ROW),
            Button("rule.2.remove", "#143#", width=ROW),
            Swatch("rule.2.colour", (70, 120, 60)),
        ]),
        header(3, "climate", "stale", "warning", False),
        header(4, "biomes", "failed", "error", False),
        header(5, "towns", "not run", "muted", False),
    ])


def _positive(text: str) -> bool:
    try:
        return float(text) > 0
    except ValueError:
        return False


DRAG_BOX = 48.0  # pixels: a box of the drag scene's pack
DRAG_COLUMNS = 6
THINGS = ("Apple", "Loaf", "Cheese", "Pumpkin", "Rope", "Lamp", "Key")


class DragScreen(Screen):
    """Drag and drop: a pack's window, 6 boxes across in a scroll, the things in it laid out in their order and
    empty boxes after. A thing dragged onto another box moves to that place (onto an empty one: last); let go off
    the window, it is dropped onto the screen, where the mouse let go; a right-click on it offers Drop; Esc cancels
    a drag. `held` keeps a drag of the second thing going, for a screenshot: the mouse cannot be held down from a
    script."""

    def __init__(self, manager: ScreenManager, held: bool = False) -> None:
        self.manager = manager
        self.held = held
        self.textures = {name: pattern(64, 50 * i) for i, name in enumerate(THINGS)}
        self.pack = list(THINGS)
        self.dropped: list[tuple[str, tuple[float, float]]] = []
        self._status = Label("status", "Drag a thing to another box, or out of the window.", size=SMALL, tone="muted")
        super().__init__("drag", Column(children=[Fill(), self._status]), margin=2 * PAD)
        width = DRAG_COLUMNS * (DRAG_BOX + GAP) - GAP + SCROLLBAR + 2 * PAD + 2 * PAD + 2
        self.pack_window = Window("pack", "Pack", self._grid(), size=(width, 3 * (DRAG_BOX + GAP) + 2 * PAD + 2 * PAD + 26),
                             modal=False, resizable=True)
        self.pack_window.position = (60.0, 60.0)
        self.open(self.pack_window)

    def _grid(self) -> Scroll:
        rows = max(4, -(-len(self.pack) // DRAG_COLUMNS))
        boxes = []
        for i in range(rows * DRAG_COLUMNS):
            name = self.pack[i] if i < len(self.pack) else None
            tooltip = Tooltip.text(name, name, f"Box {i + 1}") if name is not None else None
            menu = Menu("box.menu", [MenuItem("drop", "Drop")], title=name, target=name) if name is not None else None
            boxes.append(Picture(f"box.{i}", self.textures.get(name or ""), (64, 64), drag=name, drop=True, framed=True,
                                 tooltip=tooltip, menu=menu, height=DRAG_BOX))
        return Scroll("pack.scroll", Grid(boxes, cell=DRAG_BOX, columns=DRAG_COLUMNS), weight=1)

    def update(self, dt: float) -> None:
        if self.held and self.state.dragging is None:
            self.state.dragging = Dragging("box.1", self.pack[1], self.textures[self.pack[1]], False, (DRAG_BOX, DRAG_BOX),
                                           False, (0.0, 0.0), started=True)

    def handle(self, event: Event) -> bool:
        if isinstance(event.value, Drop):
            if not self.held:
                self._dropped(event.value)
            return True
        if event.widget == "box.menu" and event.value == "drop" and isinstance(event.target, str):
            self._drop(event.target, (300.0, 400.0))
            return True
        return False

    def _dropped(self, drop: Drop) -> None:
        name = str(drop.dragged)
        if drop.target is not None:
            self.pack.remove(name)
            self.pack.insert(min(int(drop.target.removeprefix("box.")), len(self.pack)), name)
            self._status.text = f"Moved {name} to box {self.pack.index(name) + 1}."
        elif not drop.over_window:
            self._drop(name, drop.at)
        else:
            self._status.text = f"{name} stays: let go between boxes."
        self.pack_window.set_root(self._grid())

    def _drop(self, name: str, at: tuple[float, float]) -> None:
        if name in self.pack:
            self.pack.remove(name)
            self.dropped.append((name, at))
            self._status.text = f"Dropped {name} at {at[0]:.0f}, {at[1]:.0f}."
            self.pack_window.set_root(self._grid())

    def draw_world(self) -> None:
        """What was dropped, where it was let go."""
        for name, (x, y) in self.dropped:
            texture = self.textures[name]
            rl.draw_texture_pro(texture, rl.Rectangle(0, 0, texture.width, texture.height),
                                rl.Rectangle(x - 16, y - 16, 32, 32), rl.Vector2(0, 0), 0.0, rl.WHITE)
            rl.draw_text(name, int(x - 16), int(y + 18), 10, rl.DARKGRAY)

    def unload(self) -> None:
        for texture in self.textures.values():
            rl.unload_texture(texture)


class BoardScreen(Screen):
    """A fixed-aspect `Board` over a background picture, its children placed by their middle at fractions of it:
    an empty captioned box, a tinted picture, an accent-framed one, and a label, staying on their spots as the
    window resizes the board."""

    def __init__(self, manager: ScreenManager) -> None:
        self.manager = manager
        self.textures = [pattern(256, 210), pattern(64, 30), pattern(64, 160)]
        background = Picture("board.bg", self.textures[0], (256, 256))
        children = [
            Placed(Picture("board.caption", caption="Empty", drop=True, framed=True, width=64, height=64), (0.25, 0.25)),
            Placed(Picture("board.tint", self.textures[1], (64, 64), tint=(255, 255, 255, 110), framed=True,
                           width=64, height=64), (0.75, 0.25)),
            Placed(Picture("board.accent", self.textures[2], (64, 64), accent=True, framed=True, width=64, height=64),
                   (0.5, 0.6)),
            Placed(Label("board.label", "each keeps its place"), (0.5, 0.9)),
        ]
        board = Board(background, children, aspect=1.0, weight=1)
        super().__init__("board", Column(children=[Label("heading", "Board", size=32, height=48), board]), margin=2 * PAD)

    def unload(self) -> None:
        for texture in self.textures:
            rl.unload_texture(texture)


CHAT_LINES = 24  # lines the chat scene starts with, more than fit, so it shows the scroll following its newest


class ChatScreen(Screen):
    """A chat with lines in a scroll that follows the newest, unless scrolled up; a box where Enter sends and keeps
    the focus; Send sends what was typed, from the box's draft."""

    def __init__(self, manager: ScreenManager) -> None:
        self.manager = manager
        self.lines = [("Mira" if i % 2 else "You", f"Line {i + 1} of the talk so far.") for i in range(CHAT_LINES)]
        super().__init__("chat", self.tree(), margin=2 * PAD)

    def tree(self) -> Column:
        lines = [Text.of(f"line.{i}", Span(f"{who}: ", "muted"), said) for i, (who, said) in enumerate(self.lines)]
        return Column(children=[
            Label("heading", "Chat", size=32, height=48),
            Scroll("chat.lines", Column(children=lines), follow=True, weight=1),
            Row(children=[TextBox("chat.say", "", weight=1, submit=True), Button("chat.send", "Send"), Button("back", "Back")]),
        ], gap=2 * GAP)

    def say(self, text: str) -> None:
        if text.strip():
            self.lines += [("You", text.strip()), ("Mira", f"You said {text.strip()!r}.")]
            self.set_root(self.tree())

    def handle(self, event: Event) -> bool:
        if event.widget == "chat.say" and isinstance(event.value, str):
            self.say(event.value)
        elif event.widget == "chat.send":
            self.say(self.state.take_draft("chat.say"))
        elif event.widget == "back":
            self.manager.pop()
        else:
            return False
        return True


NAME_LENGTH = 16  # the character creation screen's name field
PAD_HINT = "Pad: A types, B deletes (cancels when empty), Y space, X shift, Start OK. Arrows and Enter work too."
LARGE_FORM, LARGE_KEYBOARD = 1.5, 2.0  # the text scales of the form and of the keyboard, played from a sofa


class KeyboardScreen(Screen):
    """A character creation screen's name field: a `keyboard` text box that a click edits in place and the pad's A
    (or Enter) opens an on-screen keyboard for; the keyboard's OK sets the box and gives the box's own event. The
    Large toggle shows the form at a `text_scale` (the heading, the hint and Back stay as they are) and the keyboard
    at twice its size, as a game played on a TV would."""

    def __init__(self, manager: ScreenManager, large: bool = False) -> None:
        self.manager = manager
        self.name = ""
        self.large = large
        super().__init__("keyboard", self.tree(), margin=2 * PAD)

    def tree(self) -> Column:
        form = Column(children=[
            Row(children=[Label("name.label", "Name"), TextBox("name", self.name, keyboard=True, weight=1)]),
            Label("name.shown", f"You will be called {self.name}." if self.name else "You have no name yet.", tone="muted"),
            Row(children=[Toggle("large", "Large (TV)", active=self.large), Fill()]),
        ], gap=2 * GAP, text_scale=LARGE_FORM if self.large else None)
        return Column(children=[
            Label("heading", "New character", size=32, height=48),
            form,
            Label("hint", PAD_HINT, size=SMALL, tone="muted", wrap=True),
            Fill(),
            Row(children=[Fill(), Button("back", "Back")]),
        ], gap=2 * GAP)

    def open_keyboard(self) -> None:
        scale = LARGE_KEYBOARD if self.large else 1.0
        self.open(KeyboardWindow("name.keyboard", "Your name", self.name, max_length=NAME_LENGTH, box="name", scale=scale))

    def handle(self, event: Event) -> bool:
        if event.widget == "name" and event.value is None:  # the pad's A on the box
            self.open_keyboard()
        elif event.widget == "name" and isinstance(event.value, str):  # typed in place, or the keyboard's OK
            self.name = event.value.strip()[:NAME_LENGTH]
            self.set_root(self.tree())
        elif event.widget == "name.keyboard":  # cancelled: the name stays
            pass
        elif event.widget == "large" and isinstance(event.value, bool):
            self.large = event.value
            self.set_root(self.tree())
        elif event.widget == "back":
            self.manager.pop()
        else:
            return False
        return True


SKIN = ((246, 216, 192), (240, 196, 160), (224, 172, 132), (198, 136, 98), (166, 108, 70), (124, 80, 48), (88, 56, 32),
        (60, 38, 24))
HAIR_COLOUR = ((28, 24, 22), (58, 42, 34), (102, 72, 46), (164, 116, 64), (220, 178, 108), (232, 220, 190), (138, 138, 138),
               (160, 56, 42), (64, 96, 160), (216, 136, 176))
CHOICES = {
    "gender": ("Female", "Male"),
    "eyes": ("Dev eyes 1", "Round", "Narrow"),
    "nose": ("Dot", "Button", "Long"),
    "mouth": ("Simple", "Wide", "Small"),
    "hair": ("Long", "Short", "Bun", "Bald"),
}
FACE_SLIDERS = (("eye_spacing", "Eye spacing"), ("eye_height", "Eye height"), ("eye_size", "Eye size"), ("mouth_height", "Mouth height"))
EXPRESSIONS = ("Neutral", "Happy", "Sad", "Angry", "Surprised", "Blink")
SWATCH_SIDE = 34.0
MOVES: tuple[Direction, ...] = ("left", "right", "up", "down")


def colour_texture(colour: tuple[int, int, int]) -> rl.Texture:
    """A one-colour square, a swatch's picture (call with the window open)."""
    image = rl.gen_image_color(int(SWATCH_SIDE), int(SWATCH_SIDE), rl.Color(*colour, 255))
    texture = rl.load_texture_from_image(image)
    rl.unload_image(image)
    return texture


class NavScreen(Screen):
    """A character creation form to move through with the keys or a pad, laid out as a game's: names beside their
    controls in one stretch table, `<  value  >` choosers with rows of small swatches between them, sliders, and a
    full-width row of expression toggles.

    - The swatches lie nearer a chooser's `<` than its `>` does, and the toggles grow with the window while the gaps
      between lines do not: a move chosen by distance on screen alone left both rows. The tree keeps it to them.
    - The muted line at the bottom says where each move goes from the focus, so a screenshot taken with `--focus`
      checks the rule without pressing a key."""

    def __init__(self, manager: ScreenManager) -> None:
        self.manager = manager
        self.choice = dict.fromkeys(CHOICES, 0)
        self.colour = {"skin": 1, "hair_colour": 1}
        self.textures = {"skin": [colour_texture(colour) for colour in SKIN],
                         "hair_colour": [colour_texture(colour) for colour in HAIR_COLOUR]}
        self.where = Label("nav.where", "", size=SMALL, tone="muted")
        super().__init__("nav", self.tree(), margin=2 * PAD)

    def chooser(self, name: str) -> Row:
        value = CHOICES[name][self.choice[name]]
        return Row(children=[Button(f"{name}.prev", "<", width=44), Label(f"{name}.value", value, align="center", weight=1),
                             Button(f"{name}.next", ">", width=44)])

    def swatches(self, name: str) -> Row:
        return Row(children=[
            Picture(f"{name}.{i}", texture, (SWATCH_SIDE, SWATCH_SIDE), clickable=True, framed=i == self.colour[name],
                    accent=True, width=SWATCH_SIDE, height=SWATCH_SIDE)
            for i, texture in enumerate(self.textures[name], start=1)
        ])

    def tree(self) -> Column:
        def line(name: str, label: str, control: Node) -> list[Node]:
            return [Label(f"{name}.label", label, size=SMALL), control]

        def heading(name: str, text: str) -> list[Node]:
            return [Label(f"{name}.heading", text, size=SMALL, tone="muted")]

        sliders = [line(name, label, Slider(name, "", 1.0, 0.0, 2.0, format="{:.2f}", weight=1)) for name, label in FACE_SLIDERS]
        expressions = Row(children=[Toggle(f"expression.{name.lower()}", name, active=name == "Neutral", weight=1) for name in EXPRESSIONS])
        form = Table([
            line("name", "Name", TextBox("name", "Evan", weight=1)),
            line("gender", "Gender", self.chooser("gender")),
            line("skin", "Skin", self.swatches("skin")),
            [Separator()],
            heading("face", "Face"),
            line("eyes", "Eyes", self.chooser("eyes")),
            line("nose", "Nose", self.chooser("nose")),
            line("mouth", "Mouth", self.chooser("mouth")),
            *sliders,
            heading("expression", "Try an expression (not saved)"),
            [expressions],
            [Separator()],
            heading("hair", "Hair"),
            line("hair", "Hair", self.chooser("hair")),
            line("hair_colour", "Colour", self.swatches("hair_colour")),
        ], gap=PAD, row_gap=GAP, stretch=True)
        return Column(children=[
            Scroll("nav.scroll", form, weight=1),
            self.where,
            Row(children=[Fill(), Button("back", "Back")]),
        ], gap=2 * GAP)

    def update(self, dt: float) -> None:
        focused = self.state.focused
        if focused is None:
            self.where.text = "Press an arrow key or the d-pad to show the focus."
            return
        nodes = focusables(self.root, self.state.scroll_offset)
        self.where.text = f"From {focused}:  " + "   ".join(f"{move} {step(nodes, focused, move)}" for move in MOVES)

    def handle(self, event: Event) -> bool:
        name, _, part = event.widget.rpartition(".")
        if name in CHOICES and part in ("prev", "next"):
            count = len(CHOICES[name])
            self.choice[name] = (self.choice[name] + (1 if part == "next" else -1)) % count
            value = self.find(f"{name}.value")
            if isinstance(value, Label):
                value.text = CHOICES[name][self.choice[name]]
        elif name in self.colour:
            self.colour[name] = int(part)
            for i in range(1, len(self.textures[name]) + 1):
                swatch = self.find(f"{name}.{i}")
                if isinstance(swatch, Picture):
                    swatch.framed = i == self.colour[name]
        elif name == "expression":  # one expression at a time, and always one
            for expression in EXPRESSIONS:
                toggle = self.find(f"expression.{expression.lower()}")
                if isinstance(toggle, Toggle):
                    toggle.active = toggle.id == event.widget
        elif event.widget == "back":
            self.manager.pop()
        else:
            slider = self.find(event.widget)
            if not isinstance(slider, Slider) or not isinstance(event.value, float):
                return False
            slider.value = event.value
        return True

    def unload(self) -> None:
        for textures in self.textures.values():
            for texture in textures:
                rl.unload_texture(texture)


BUNDLE_FILES = ("preview.png", "manifest.json", "readme.txt")


class FilesScreen(Screen):
    """File and directory selection (`FileWindow`): loads a `.png` image into the preview (`mode="load_file"`) and
    writes a bundle of files (`preview.png`, `manifest.json`, `readme.txt`) into a chosen folder (`mode="directory"`).
    """

    def __init__(
        self,
        manager: ScreenManager,
        *,
        image_path: Path | None = None,
        export_dir: Path | None = None,
    ) -> None:
        self.manager = manager
        self.image_path = image_path if image_path is not None else Path.cwd()
        self.export_dir = export_dir if export_dir is not None else Path.cwd() / "var" / "files-demo"
        self._image: rl.Image = rl.gen_image_checked(
            256,
            256,
            32,
            32,
            rl.color_from_hsv(200, 0.35, 0.85),
            rl.color_from_hsv(200, 0.5, 0.6),
        )
        self.texture: rl.Texture | None = rl.load_texture_from_image(self._image) if rl.is_window_ready() else None
        self.image_name = "sample.png"
        self.image_source = "procedural sample (generated)"
        self.image_size = (256, 256)
        self.saved_dir: Path | None = None
        self.saved_files: list[tuple[str, int]] = []
        self.status_text = "Pick a PNG image to load or a folder to save the bundle into."
        self.status_tone: Tone = "muted"
        super().__init__("files", self.tree(), margin=2 * PAD)

    def tree(self) -> Column:
        w, h = self.image_size
        left = Column(
            children=[
                Label("heading", "Files", size=32, height=48),
                Picture("files.preview", self.texture, (float(w), float(h)), framed=True, weight=1),
                Label("files.caption", f"{self.image_name} ({w} × {h} px)", size=SMALL, tone="muted", align="center"),
            ]
        )
        load_table = Table(
            [
                [
                    Label("files.info.file.k", "file", height=SMALL + 4, size=SMALL, tone="muted"),
                    Label("files.info.file.v", self.image_name, height=SMALL + 4, size=SMALL),
                ],
                [
                    Label("files.info.size.k", "size", height=SMALL + 4, size=SMALL, tone="muted"),
                    Label("files.info.size.v", f"{w} × {h} px", height=SMALL + 4, size=SMALL),
                ],
            ],
            align=("left", "right"),
        )
        load_panel = Panel(
            title="Load PNG",
            child=Column(
                children=[
                    Label("files.source", self.image_source, size=SMALL, tone="muted", elide=True),
                    load_table,
                    Row(children=[Fill(), Button("files.open-png", "Load PNG...")]),
                ]
            ),
        )

        bundle_rows: list[list[Node]] = []
        if self.saved_dir is not None:
            bundle_rows.append(
                [
                    Label("files.saved.dir.k", "folder", height=SMALL + 4, size=SMALL, tone="muted"),
                    Label("files.saved.dir.v", str(self.saved_dir), height=SMALL + 4, size=SMALL, elide=True),
                ]
            )
            for i, (name, num_bytes) in enumerate(self.saved_files):
                bundle_rows.append(
                    [
                        Label(f"files.saved.{i}.k", name, height=SMALL + 4, size=SMALL, tone="muted"),
                        Label(f"files.saved.{i}.v", format_size(num_bytes), height=SMALL + 4, size=SMALL),
                    ]
                )
        else:
            for i, (name, desc) in enumerate(
                (
                    ("preview.png", "current preview image as PNG"),
                    ("manifest.json", "image dimensions and file list"),
                    ("readme.txt", "short text note"),
                )
            ):
                bundle_rows.append(
                    [
                        Label(f"files.bundle.{i}.k", name, height=SMALL + 4, size=SMALL, tone="muted"),
                        Label(f"files.bundle.{i}.v", desc, height=SMALL + 4, size=SMALL),
                    ]
                )

        save_panel = Panel(
            title="Save directory of files",
            child=Column(
                children=[
                    Label(
                        "files.save.desc",
                        "Writes preview.png, manifest.json and readme.txt into the chosen directory.",
                        size=SMALL,
                        wrap=True,
                        tone="muted",
                    ),
                    Table(bundle_rows, align=("left", "right")),
                    Row(children=[Fill(), Button("files.save-dir", "Save directory...")]),
                ]
            ),
        )
        right = Scroll(
            "files.scroll",
            Column(children=[load_panel, save_panel], gap=2 * GAP),
            weight=1,
        )
        return Column(
            children=[
                Split("files-split", left, right, ratio=0.45, minimum=(240.0, 360.0), weight=1),
                Row(
                    children=[
                        Label("files.status", self.status_text, size=SMALL, tone=self.status_tone, elide=True, weight=1),
                        Button("back", "Back"),
                    ]
                ),
            ],
            gap=2 * GAP,
        )

    def open_load_window(self) -> FileWindow:
        window = FileWindow(
            "files.load",
            "Load PNG image",
            path=self.image_path,
            mode="load_file",
            suffixes=(".png",),
            prompt="Pick a .png file to display in the preview.",
        )
        self.open(window)
        return window

    def open_save_window(self) -> FileWindow:
        window = FileWindow(
            "files.save",
            "Save directory of files",
            path=self.export_dir,
            mode="directory",
            ok="Save",
            prompt="Pick a folder (or type a new folder name) to write preview.png, manifest.json and readme.txt into.",
        )
        self.open(window)
        return window

    def load_png(self, path: Path) -> bool:
        image = rl.load_image(str(path))
        if not image.data or image.width <= 0 or image.height <= 0:
            self.status_text = f"Could not read PNG image: {path}"
            self.status_tone = "error"
            self.set_root(self.tree())
            return False
        if self.texture is not None:
            rl.unload_texture(self.texture)
            self.texture = None
        rl.unload_image(self._image)
        self._image = image
        if rl.is_window_ready():
            self.texture = rl.load_texture_from_image(self._image)
        self.image_path = path
        self.image_name = path.name
        self.image_source = str(path)
        self.image_size = (image.width, image.height)
        self.status_text = f"Loaded {path.name} ({image.width} × {image.height} px)."
        self.status_tone = "ok"
        self.set_root(self.tree())
        return True

    def save_directory(self, directory: Path) -> None:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            preview_path = directory / "preview.png"
            rl.export_image(self._image, str(preview_path))
            w, h = self.image_size
            manifest = {
                "source": self.image_source,
                "width": w,
                "height": h,
                "files": list(BUNDLE_FILES),
            }
            (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            (directory / "readme.txt").write_text(
                f"Exported by rayscreen FilesScreen.\nImage: {self.image_name} ({w}x{h} px)\n",
                encoding="utf-8",
            )
        except OSError as exc:
            self.status_text = f"Could not save directory: {exc}"
            self.status_tone = "error"
            self.set_root(self.tree())
            return
        self.export_dir = directory
        self.saved_dir = directory
        self.saved_files = [(name, (directory / name).stat().st_size) for name in BUNDLE_FILES]
        self.status_text = f"Saved {len(BUNDLE_FILES)} files to {directory}."
        self.status_tone = "ok"
        self.set_root(self.tree())

    def handle(self, event: Event) -> bool:
        if event.widget == "files.open-png":
            self.open_load_window()
            return True
        if event.widget == "files.save-dir":
            self.open_save_window()
            return True
        if event.widget == "files.load":
            if isinstance(event.value, str):
                self.load_png(Path(event.value))
            return True
        if event.widget == "files.save":
            if isinstance(event.value, str):
                self.save_directory(Path(event.value))
            return True
        if event.widget == "back":
            self.unload()
            self.manager.pop()
            return True
        return False

    def unload(self) -> None:
        if self.texture is not None:
            rl.unload_texture(self.texture)
            self.texture = None
        if self._image.data:
            rl.unload_image(self._image)
            self._image.data = rl.ffi.NULL
