"""rayscreen-demo: the library's checking harness. Navigates the demo's screens; screenshots of
each scene are how the visual work is checked (`--screen NAME --screenshot out.png`). `--mouse X,Y`
holds the mouse at a point, for a tooltip; the `tooltip` and `menu` scenes put it on the villager, and `drag-held`
over a box of the pack, its second thing dragged there. A pad (and the arrow keys and Enter, while no box is being
edited) moves the focus (`read_nav`).
"""

import argparse
from pathlib import Path

import pyray as rl

from rayscreen.demo.screens import (
    MIRA,
    BoardScreen,
    DragScreen,
    FilesScreen,
    GalleryScreen,
    GameScreen,
    PauseScreen,
    ScenesScreen,
    open_scene,
)
from rayscreen.draw import frame
from rayscreen.navigation import Direction, Nav
from rayscreen.screen import Screen, ScreenManager
from rayscreen.theme import Theme

SCENES = (
    "scenes",
    "main",
    "settings",
    "load",
    "game",
    "quests",
    "pause",
    "dialog",
    "minimized",
    "tooltip",
    "menu",
    "gallery",
    "drag",
    "drag-held",
    "chat",
    "keyboard",
    "board",
    "files",
    "files-load",
    "files-save",
)
DRAG_MOUSE = (250, 175)  # over the fourth box of the second row of `drag-held`


def _unload_screen(screen: Screen) -> None:
    if isinstance(screen, (DragScreen, GalleryScreen, BoardScreen, GameScreen, FilesScreen)):
        screen.unload()


def _pop_to_scenes(manager: ScreenManager) -> None:
    while len(manager._stack) > 1 and not isinstance(manager.top, ScenesScreen):
        _unload_screen(manager.pop())


_PAD = rl.GamepadButton
_PAD_MOVES: tuple[tuple[int, Direction], ...] = (
    (_PAD.GAMEPAD_BUTTON_LEFT_FACE_UP, "up"), (_PAD.GAMEPAD_BUTTON_LEFT_FACE_DOWN, "down"),
    (_PAD.GAMEPAD_BUTTON_LEFT_FACE_LEFT, "left"), (_PAD.GAMEPAD_BUTTON_LEFT_FACE_RIGHT, "right"),
)
_KEY_MOVES: tuple[tuple[int, Direction], ...] = (
    (rl.KeyboardKey.KEY_UP, "up"), (rl.KeyboardKey.KEY_DOWN, "down"),
    (rl.KeyboardKey.KEY_LEFT, "left"), (rl.KeyboardKey.KEY_RIGHT, "right"),
)


def _editing(manager: ScreenManager) -> bool:
    """A text box is being edited: the arrow keys and Enter are its."""
    return any(screen.state.editing is not None or any(window.state.editing is not None for window in screen.windows)
               for screen in manager.visible())


def read_nav(manager: ScreenManager) -> Nav:
    """The demo's bindings: the first pad's d-pad, face buttons and Start; and the arrow keys and Enter unless a box is
    being edited. raylib names face buttons by where they sit on an Xbox pad (A bottom, B right, X left, Y top), so
    the buttons go by the labels on such a pad: A activates, B goes back, Y types a space, X shifts."""
    move: Direction | None = None
    activate = back = space = shift = confirm = False
    if rl.is_gamepad_available(0):
        move = next((direction for button, direction in _PAD_MOVES if rl.is_gamepad_button_pressed(0, button)), None)
        activate = rl.is_gamepad_button_pressed(0, _PAD.GAMEPAD_BUTTON_RIGHT_FACE_DOWN)
        back = rl.is_gamepad_button_pressed(0, _PAD.GAMEPAD_BUTTON_RIGHT_FACE_RIGHT)
        space = rl.is_gamepad_button_pressed(0, _PAD.GAMEPAD_BUTTON_RIGHT_FACE_UP)
        shift = rl.is_gamepad_button_pressed(0, _PAD.GAMEPAD_BUTTON_RIGHT_FACE_LEFT)
        confirm = rl.is_gamepad_button_pressed(0, _PAD.GAMEPAD_BUTTON_MIDDLE_RIGHT)
    if not _editing(manager):
        move = move or next((direction for key, direction in _KEY_MOVES
                             if rl.is_key_pressed(key) or rl.is_key_pressed_repeat(key)), None)
        activate = activate or rl.is_key_pressed(rl.KeyboardKey.KEY_ENTER)
    return Nav(move=move, activate=activate, back=back, space=space, shift=shift, confirm=confirm)


def build_scene(manager: ScreenManager, scene: str) -> None:
    """The stack as `scene` names it: `ScenesScreen` sits at the bottom so Esc/Back returns to the scene picker."""
    manager.push(ScenesScreen(manager))
    if scene != "scenes":
        open_scene(manager, scene)


def save_screenshot(path: Path) -> None:
    """Save what has been drawn this frame; call before end_drawing."""
    rl.rl_draw_render_batch_active()  # raygui draws are batched until end_drawing otherwise
    image = rl.load_image_from_screen()
    rl.export_image(image, str(path))
    rl.unload_image(image)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen", choices=SCENES, default="scenes", help="The scene to start in.")
    parser.add_argument("--screenshot", type=Path, help="Save a PNG after a few frames, then exit.")
    parser.add_argument("--size", default="1000,700", help="Window size, W,H (default 1000,700).")
    parser.add_argument("--mouse", help="Hold the mouse at X,Y (pixels), for a tooltip in a screenshot.")
    args = parser.parse_args()
    width, _, height = args.size.partition(",")
    mouse: tuple[float, float] | None = None
    if args.mouse is not None:
        mouse_x, _, mouse_y = args.mouse.partition(",")
        mouse = float(mouse_x), float(mouse_y)
    elif args.screen in ("tooltip", "menu"):
        mouse = MIRA.centre(int(width), int(height))
    elif args.screen == "drag-held":
        mouse = DRAG_MOUSE

    rl.init_window(int(width), int(height), "rayscreen demo")
    rl.set_exit_key(rl.KeyboardKey.KEY_NULL)  # Escape navigates (pause menu, close window), not exits
    rl.set_target_fps(60)
    theme = Theme()
    theme.apply_style()
    manager = ScreenManager()
    build_scene(manager, args.screen)

    running = True
    frames = 0
    shot_at = 30 if mouse is not None else 5  # time for a tooltip's delay
    while running and not rl.window_should_close():
        if mouse is not None:
            rl.set_mouse_position(int(mouse[0]), int(mouse[1]))
        rl.begin_drawing()
        rl.clear_background(theme.background)
        for screen in manager.visible():
            if isinstance(screen, (DragScreen, GameScreen)):
                screen.draw_world()
        top = manager.top
        events = frame(manager, theme, read_nav(manager))
        for event in events:
            print(event)
            if event.screen == "scenes" and event.widget == "quit":
                running = False
            elif event.screen == "main" and event.widget == "quit":
                if len(manager._stack) > 1:
                    _unload_screen(manager.pop())
                else:
                    running = False
            elif event.widget == "quit.yes":
                _pop_to_scenes(manager)
        # an Esc that closed the focused window or dropped what was typed must not also navigate
        if rl.is_key_pressed(rl.KeyboardKey.KEY_ESCAPE) and not manager.esc_used:
            if isinstance(top, GameScreen):
                manager.push(PauseScreen(manager))
            elif isinstance(top, PauseScreen) and top.window is None:
                manager.pop()
            elif not isinstance(top, ScenesScreen) and len(manager._stack) > 1:
                _unload_screen(manager.pop())
        if args.screenshot is not None and frames >= shot_at:
            save_screenshot(args.screenshot)
            rl.end_drawing()
            break
        rl.end_drawing()
        frames += 1
    while manager._stack:
        _unload_screen(manager.pop())
    theme.unload()
    rl.close_window()


if __name__ == "__main__":
    main()
