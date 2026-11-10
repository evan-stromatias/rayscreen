"""Plain data (what JSON holds: dicts, lists, strings, numbers, booleans, None) as a tree of specs, for reading: a
model's structured output in a tooltip, a record in an inspector. No raylib.

- A dict is a table of its keys, muted, beside their values; a value that is itself a dict or a list is a table in
  the value's cell, so nesting indents by the keys' column, as an outline does.
- A list is a table of bullets beside its items; an empty dict or list says so, muted.
- Strings read in ink and wrap in the last column (a long reasoning wraps under itself, not under its key); numbers in
  the info tone, booleans in the warning tone, None as "null", muted.
"""

from collections.abc import Mapping, Sequence

from rayscreen.specs import GAP, PAD, SMALL, Label, Node, Span, Table, Text, Tone

BULLET = "–"
ROW_GAP = 3.0  # pixels between rows, so a wrapped value reads apart from the next


def data_tree(widget: str, value: object, size: int = SMALL) -> Node:
    """`value` as specs whose ids start with `widget`, text at `size`."""
    match value:
        case Mapping() if value:
            return Table([[_key(f"{widget}.{key}.key", str(key), size), data_tree(f"{widget}.{key}", item, size)]
                          for key, item in value.items()], gap=PAD, row_gap=ROW_GAP)
        case Sequence() if not isinstance(value, str) and value:
            return Table([[_key(f"{widget}.{i}.key", BULLET, size), data_tree(f"{widget}.{i}", item, size)]
                          for i, item in enumerate(value)], gap=GAP, row_gap=ROW_GAP)
        case Mapping() | Sequence() if not isinstance(value, str):
            return _leaf(widget, "{}" if isinstance(value, Mapping) else "[]", "muted", size)
        case str():
            return _leaf(widget, value, "ink", size)
        case bool():  # before numbers: a bool is an int
            return _leaf(widget, "true" if value else "false", "warning", size)
        case int() | float():
            return _leaf(widget, f"{value:g}" if isinstance(value, float) else str(value), "info", size)
        case None:
            return _leaf(widget, "null", "muted", size)
    return _leaf(widget, str(value), "ink", size)


def _key(widget: str, text: str, size: int) -> Label:
    """A key, as tall as a `Text`'s line so it sits level with the value beside it."""
    return Label(widget, text, height=size + 4, size=size, tone="muted")


def _leaf(widget: str, text: str, tone: Tone, size: int) -> Text:
    return Text(widget, [Span(text, tone)], size)
