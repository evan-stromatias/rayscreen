"""Windows under display scaling (150% on a Wayland desktop): what every rayscreen app opens its window with, and the
mouse fix it runs each frame.

- `HIGHDPI`: with it raylib lays out in the desktop's units, as the mouse comes, and draws them at the pixels; without
  it raylib draws in pixels and every click lands short of its aim by the scale.
- `follow_wayland_mouse`: raylib 6.0 divides the mouse by the display scale again on Wayland, where it already comes
  in the window's units (raylib's master skips that). To drop once pyray bundles a raylib with the fix.
"""

import os
from functools import cache

import pyray as rl

HIGHDPI = rl.ConfigFlags.FLAG_WINDOW_HIGHDPI


@cache
def on_wayland() -> bool:
    """GLFW draws through Wayland when the session has a Wayland display (GLFW 3.4 prefers it to XWayland)."""
    return bool(os.environ.get("WAYLAND_DISPLAY"))


def follow_wayland_mouse() -> None:
    """Each frame, before anything reads the mouse: raylib 6.0 sets its scale again on every resize and change of
    scale."""
    if on_wayland():
        rl.set_mouse_scale(1.0, 1.0)
