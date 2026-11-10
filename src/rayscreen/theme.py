"""The look of every screen: colours, text sizes and the font, plus the raygui style, applied once
after the window opens. Text helpers honour the font, which `rl.draw_text`/`rl.measure_text` never do.

- The default font is the bundled monogram pixel font on a 16 px grid, so it is loaded once per size
  drawn, without smoothing; one size scaled to another has uneven strokes.
  Sizes that are multiples of 16 (16, 32, 48) are the crispest.
- `Theme()` is light; `Theme.dark_theme()` is dark, and `set_dark` switches a theme in place at runtime.
- Fonts load lazily, the first time a size is measured or drawn, and only once the window is open
  (they live on the GPU); until then, as in tests, raylib's own font measures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pyray as rl
import raylib

from rayscreen import icons
from rayscreen.specs import PAD, ROW, SMALL, TEXT

FONT = Path(__file__).parent / "assets" / "monogram-extended.ttf"

# The characters fonts are loaded with: ASCII, Latin-1 (° ² × é ...) and common punctuation (– — ‘ ’ “ ” … − →);
# raylib loads only ASCII by default, and draws "?" for the rest. monogram has no soft hyphen (0xAD)
CODEPOINTS = [*range(32, 127), *range(160, 173), *range(174, 256), 0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2026, 0x2212, 0x2192]

_P = rl.GuiControlProperty
# raygui's own dark style (its styles/dark), as 0xRRGGBBAA: the controls' borders, bases and texts by state
DARK_RAYGUI = {
    _P.BORDER_COLOR_NORMAL: 0x878787FF, _P.BASE_COLOR_NORMAL: 0x2C2C2CFF, _P.TEXT_COLOR_NORMAL: 0xC3C3C3FF,
    _P.BORDER_COLOR_FOCUSED: 0xE1E1E1FF, _P.BASE_COLOR_FOCUSED: 0x848484FF, _P.TEXT_COLOR_FOCUSED: 0x181818FF,
    _P.BORDER_COLOR_PRESSED: 0x000000FF, _P.BASE_COLOR_PRESSED: 0xEFEFEFFF, _P.TEXT_COLOR_PRESSED: 0x202020FF,
    _P.BORDER_COLOR_DISABLED: 0x6A6A6AFF, _P.BASE_COLOR_DISABLED: 0x818181FF, _P.TEXT_COLOR_DISABLED: 0x606060FF,
    rl.GuiDefaultProperty.BACKGROUND_COLOR: 0x212121FF,
}


@dataclass(slots=True)
class Theme:
    text: int = TEXT
    small: int = SMALL
    font_path: Path | None = field(default_factory=lambda: FONT)  # None: raygui's default font
    spacing: int = 0  # pixels between letters; monogram's own advance already leaves a gap
    background: rl.Color = field(default_factory=lambda: rl.Color(236, 238, 241, 255))
    ink: rl.Color = field(default_factory=lambda: rl.Color(38, 42, 50, 255))
    muted: rl.Color = field(default_factory=lambda: rl.Color(100, 108, 120, 255))
    error: rl.Color = field(default_factory=lambda: rl.Color(190, 48, 40, 255))  # a problem: its message, a bad box's border
    ok: rl.Color = field(default_factory=lambda: rl.Color(35, 125, 65, 255))  # a state that is done, good news
    warning: rl.Color = field(default_factory=lambda: rl.Color(185, 115, 15, 255))  # a state out of date
    info: rl.Color = field(default_factory=lambda: rl.Color(40, 100, 190, 255))  # a state under way
    accent: rl.Color = field(default_factory=lambda: rl.Color(197, 139, 42, 255))  # a marked frame (the equipment's hands)
    panel: rl.Color = field(default_factory=lambda: rl.Color(246, 247, 249, 255))  # a filled Panel
    dim: rl.Color = field(default_factory=lambda: rl.Color(20, 24, 32, 170))  # over what a modal covers
    tooltip_delay: float = 0.3  # seconds the mouse rests on a thing before its tooltip shows; hiding is at once
    title_ink: rl.Color | None = None  # the focused window's title; None: `ink`
    raygui: dict[int, int] = field(default_factory=dict)  # raygui DEFAULT properties set before the rest (colours)
    dark: bool = False
    _fonts: dict[int, rl.Font] = field(default_factory=dict, init=False, repr=False)

    @classmethod
    def dark_theme(cls) -> Theme:
        """The same look in light text on dark grey, with raygui's controls in its own dark style's colours."""
        return cls(
            background=rl.Color(33, 34, 37, 255),
            ink=rl.Color(214, 216, 220, 255),
            muted=rl.Color(150, 156, 166, 255),
            panel=rl.Color(44, 45, 49, 255),
            dim=rl.Color(0, 0, 0, 170),
            error=rl.Color(240, 108, 96, 255),
            ok=rl.Color(110, 200, 130, 255),
            warning=rl.Color(230, 175, 80, 255),
            info=rl.Color(120, 170, 240, 255),
            accent=rl.Color(226, 171, 78, 255),
            title_ink=rl.Color(24, 24, 24, 255),
            raygui=dict(DARK_RAYGUI),
            dark=True,
        )

    def set_dark(self, dark: bool) -> None:
        """Switch this theme between light and dark in place (the screens keep drawing with it), restyling
        raygui once the window is open. The fonts loaded so far are kept."""
        source = Theme.dark_theme() if dark else Theme()
        for name in ("background", "ink", "muted", "panel", "dim", "error", "ok", "warning", "info", "accent", "title_ink", "raygui",
                     "dark"):
            setattr(self, name, getattr(source, name))
        if rl.is_window_ready():
            self.apply_style()

    def apply_style(self) -> None:
        """Set raygui's style and font; call once, after the window opens (and again after `set_dark`).
        Starts from raygui's default style, so switching back to light restores it exactly."""
        # raygui's reset unloads the font it was given, which is one of ours (cached in `_fonts`): give it its own first
        rl.gui_set_font(rl.get_font_default())
        rl.gui_load_style_default()
        icons.install()
        for prop, value in self.raygui.items():
            rl.gui_set_style(rl.GuiControl.DEFAULT, prop, value)
        rl.gui_set_style(rl.GuiControl.DEFAULT, rl.GuiDefaultProperty.TEXT_SIZE, self.text)
        rl.gui_set_style(rl.GuiControl.DEFAULT, rl.GuiDefaultProperty.TEXT_SPACING, self.spacing)
        # one colour scale: raygui's controls write in the theme's ink, as labels do, and group box
        # lines and titles in its muted grey (raygui's pale blue vanished on light panels)
        rl.gui_set_style(rl.GuiControl.DEFAULT, rl.GuiControlProperty.TEXT_COLOR_NORMAL, rl.color_to_int(self.ink))
        rl.gui_set_style(rl.GuiControl.DEFAULT, rl.GuiDefaultProperty.LINE_COLOR, rl.color_to_int(self.muted))
        rl.gui_set_style(rl.GuiControl.CHECKBOX, rl.GuiControlProperty.TEXT_COLOR_PRESSED, rl.color_to_int(self.ink))
        # the focused window's title bar is raygui's focused blue; its title stays in ink to read
        title = self.title_ink if self.title_ink is not None else self.ink
        rl.gui_set_style(rl.GuiControl.STATUSBAR, rl.GuiControlProperty.TEXT_COLOR_FOCUSED, rl.color_to_int(title))
        rl.gui_set_style(rl.GuiControl.LISTVIEW, rl.GuiListViewProperty.LIST_ITEMS_HEIGHT, int(ROW))
        # raygui centres list items; a list of saves or files reads down its left edge
        rl.gui_set_style(rl.GuiControl.LISTVIEW, rl.GuiControlProperty.TEXT_ALIGNMENT, rl.GuiTextAlignment.TEXT_ALIGN_LEFT)
        rl.gui_set_style(rl.GuiControl.LISTVIEW, rl.GuiControlProperty.TEXT_PADDING, int(PAD))
        if self.font_path is not None:
            rl.gui_set_font(self.font(self.text))

    def unload(self) -> None:
        """Free the loaded fonts; call before the window closes."""
        for font in self._fonts.values():
            rl.unload_font(font)
        self._fonts.clear()

    def font(self, size: int) -> rl.Font:
        """The font loaded at exactly `size`, loading it on first use; raylib's own before the window
        opens or with no `font_path`."""
        if self.font_path is None or not rl.is_window_ready():
            return rl.gui_get_font()
        if size not in self._fonts:
            # raylib's own function: pyray's wrapper takes no codepoint array
            font = raylib.LoadFontEx(str(self.font_path).encode(), size, rl.ffi.new("int[]", CODEPOINTS), len(CODEPOINTS))
            rl.set_texture_filter(font.texture, rl.TextureFilter.TEXTURE_FILTER_POINT)
            self._fonts[size] = font
        return self._fonts[size]

    def text_width(self, text: str, size: int) -> float:
        return rl.measure_text_ex(self.font(size), text, size, self.spacing).x

    def draw_text(self, text: str, x: float, y: float, size: int, color: rl.Color) -> None:
        rl.draw_text_ex(self.font(size), text, rl.Vector2(int(x), int(y)), size, self.spacing, color)
