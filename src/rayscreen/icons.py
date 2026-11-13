"""Icons raygui lacks, drawn into the icon slots it leaves free (250 to 255), so a button shows one as raygui's
own: `Button(id, icon_text(SUN))`. Each is a 16 x 16 bitmap made from circles or drawn as pixel rows, so it needs
no image file.
"""

import math
from collections.abc import Callable

import pyray as rl

SUN, MOON = 250, 251  # light mode's and dark mode's
SHIFT, SHIFT_ON, CAPS_LOCK = 252, 253, 254  # an on-screen keyboard's shift: an outlined arrow, filled, and barred
BACKSPACE = 255  # an on-screen keyboard's backspace: a key pointing left with an X cut out of it
SIZE = 16  # raygui's icons are 16 x 16 pixels, two rows to a 32-bit word


def icon_text(icon: int) -> str:
    """A button's text that draws `icon` (raygui's "#id#")."""
    return f"#{icon}#"


def _bitmap(inside: Callable[[float, float], bool]) -> list[int]:
    """The 8 words of an icon whose pixel (x, y) is set where `inside` holds at its centre: word i holds rows
    2i (bits 0-15) and 2i + 1 (bits 16-31), bit x of a row being column x, as GuiDrawIcon reads them."""
    words = [0] * (SIZE * SIZE // 32)
    for y in range(SIZE):
        for x in range(SIZE):
            if inside(x + 0.5, y + 0.5):
                words[y // 2] |= 1 << (x + SIZE * (y % 2))
    return words


def _sun(x: float, y: float) -> bool:
    """A disc with eight short rays around it."""
    dx, dy = x - 7.5, y - 7.5  # on a pixel's centre, so rays are one pixel wide
    r = math.hypot(dx, dy)
    if r <= 3.3:
        return True
    angle = math.atan2(dy, dx) / (math.pi / 4)
    return 4.9 <= r <= 7.2 and abs(angle - round(angle)) * (math.pi / 4) * r < 0.6


def _moon(x: float, y: float) -> bool:
    """A crescent: a disc with a smaller one taken out of its upper right."""
    return math.hypot(x - 7.5, y - 7.5) <= 6.4 and math.hypot(x - 10.5, y - 5) > 5.0


_SHIFT_ROWS = (
    "................",
    "................",
    ".......##.......",
    "......#..#......",
    ".....#....#.....",
    "....#......#....",
    "...#........#...",
    "..####....####..",
    ".....#....#.....",
    ".....#....#.....",
    ".....#....#.....",
    ".....#....#.....",
    ".....######.....",
)
_SHIFT_ON_ROWS = (
    "................",
    "................",
    ".......##.......",
    "......####......",
    ".....######.....",
    "....########....",
    "...##########...",
    "..############..",
    ".....######.....",
    ".....######.....",
    ".....######.....",
    ".....######.....",
    ".....######.....",
)

_BACKSPACE_ROWS = (
    "................",
    "................",
    "................",
    "......##########",
    ".....###########",
    "....####.####.##",
    "...######.##.###",
    "..########..####",
    "..########..####",
    "...######.##.###",
    "....####.####.##",
    ".....###########",
    "......##########",
)


def _drawn(rows: tuple[str, ...]) -> Callable[[float, float], bool]:
    """A pixel-row drawing ("#" set), its rows top first, as `_bitmap` asks for it."""
    return lambda x, y: int(y) < len(rows) and rows[int(y)][int(x)] == "#"


ICONS = {
    SUN: _bitmap(_sun),
    MOON: _bitmap(_moon),
    SHIFT: _bitmap(_drawn(_SHIFT_ROWS)),
    SHIFT_ON: _bitmap(_drawn(_SHIFT_ON_ROWS)),
    CAPS_LOCK: _bitmap(_drawn((*_SHIFT_ON_ROWS, "................", ".....######....."))),
    BACKSPACE: _bitmap(_drawn(_BACKSPACE_ROWS)),
}


def install() -> None:
    """Write the icons into raygui's icon table (static data: no window needed)."""
    table = rl.gui_get_icons()
    words = SIZE * SIZE // 32
    for icon, bitmap in ICONS.items():
        for i, word in enumerate(bitmap):
            table[icon * words + i] = word
