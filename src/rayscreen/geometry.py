"""The rectangle the layout works in: no raylib, so the layout is tested without a window."""

from typing import NamedTuple, Self


class Rect(NamedTuple):
    x: float
    y: float
    width: float
    height: float

    def inset(self, pad: float) -> Self:
        """The rect shrunk by `pad` on every side."""
        return Rect(self.x + pad, self.y + pad, self.width - 2 * pad, self.height - 2 * pad)

    def contains(self, x: float, y: float) -> bool:
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height

    def overlap(self, other: Self) -> Self:
        """Where the two rects overlap; empty (no width or no height) where they do not."""
        x, y = max(self.x, other.x), max(self.y, other.y)
        right, bottom = min(self.x + self.width, other.x + other.width), min(self.y + self.height, other.y + other.height)
        return Rect(x, y, max(right - x, 0.0), max(bottom - y, 0.0))


def place_beside(
    point: tuple[float, float], width: float, height: float, screen_width: float, screen_height: float, offset: float
) -> tuple[float, float]:
    """The top-left of a box beside `point` (the cursor): below and right of it by `offset`, flipped
    to the left or above where it would leave the screen, then clamped onto it (a box wider than
    the screen sits at its left edge)."""
    x, y = point
    left, top = x + offset, y + offset
    if left + width > screen_width:
        left = x - offset - width
    if top + height > screen_height:
        top = y - offset - height
    return max(0.0, min(left, screen_width - width)), max(0.0, min(top, screen_height - height))
