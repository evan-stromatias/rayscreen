"""Formatted text: spans in tones, hanging indents, tables whose columns line up, separators. No window
(a fake text width of 7 px a character)."""

from rayscreen.geometry import Rect
from rayscreen.layout import Run, arrange, content_width, measure, natural_width, table_columns, text_lines
from rayscreen.specs import TEXT, Column, Label, Row, Separator, Span, Table, Text, TextBox, check_unique_ids


def fake_measure(text: str, size: int) -> float:
    return float(len(text) * 7)


LINE = TEXT + 4  # a text's line, as a wrapped label's


# --- Text


def test_spans_flow_as_one_line_each_in_its_tone():
    text = Text.of("t", "walls ", Span("no", "muted"), ", plaza ", Span("yes"))
    assert text_lines(text, 1000.0, fake_measure) == [[Run(0.0, "walls ", "ink"), Run(42.0, "no", "muted"), Run(56.0, ", plaza yes", "ink")]]


def test_a_text_wraps_at_words_and_keeps_tones_across_lines():
    text = Text.of("t", "aaa bbb ", Span("ccc ddd", "error"))
    lines = text_lines(text, 7 * 8, fake_measure)  # "aaa bbb" fits, " ccc" does not
    assert lines == [[Run(0.0, "aaa bbb", "ink")], [Run(0.0, "ccc ddd", "error")]]
    assert measure(text, 7 * 8, fake_measure) == 2 * LINE


def test_a_word_is_not_broken_where_its_tone_changes():
    text = Text.of("t", "aaaa ", "bb", Span("cc", "muted"))
    assert text_lines(text, 7 * 6, fake_measure) == [[Run(0.0, "aaaa", "ink")], [Run(0.0, "bb", "ink"), Run(14.0, "cc", "muted")]]


def test_lines_after_the_first_hang_by_the_indent():
    item = Text.of("item", "• one two three", indent=14.0)
    lines = text_lines(item, 7 * 9, fake_measure)
    assert [line[0].x for line in lines] == [0.0, 14.0]
    assert [line[0].text for line in lines] == ["• one two", "three"]


def test_a_newline_starts_a_line():
    text = Text.of("t", "one\ntwo")
    assert [line[0].text for line in text_lines(text, 1000.0, fake_measure)] == ["one", "two"]
    assert content_width(text, fake_measure) == 21.0


def test_a_text_takes_a_share_in_a_row_and_wants_its_longest_line():
    text = Text.of("t", "abc ", Span("de", "muted"))
    assert natural_width(text, fake_measure) is None
    assert content_width(text, fake_measure) == 7 * 6


# --- Table


def key_value(rows: list[tuple[str, str]], **options: object) -> Table:
    return Table([[Label(f"k{i}", key), Label(f"v{i}", value)] for i, (key, value) in enumerate(rows)], **options)


def test_columns_are_as_wide_as_their_widest_cell():
    table = key_value([("radius", "130 m"), ("buildings", "246")])
    assert table_columns(table, 1000.0, fake_measure) == [63.0, 35.0]
    arrange(table, Rect(0, 0, 1000, 500), fake_measure)
    assert [row[1].rect.x for row in table.rows] == [63.0 + table.gap] * 2


def test_a_right_aligned_column_lines_up_at_its_right_edge():
    table = key_value([("radius", "130 m"), ("gates", "2")], align=("left", "right"))
    arrange(table, Rect(10, 0, 1000, 500), fake_measure)
    right = [row[1].rect.x + row[1].rect.width for row in table.rows]
    assert right == [10 + 42.0 + table.gap + 35.0] * 2 and table.rows[1][1].rect.width == 7.0


def test_a_short_rows_last_cell_spans_the_rest_and_widens_no_column():
    note = Label("note", "a note far wider than any key")
    table = Table([[Label("k", "radius"), Label("v", "130 m")], [note]])
    assert table_columns(table, 1000.0, fake_measure) == [42.0, 35.0]
    arrange(table, Rect(0, 0, 300, 500), fake_measure)
    assert note.rect.x == 0 and note.rect.width == 300
    assert content_width(table, fake_measure) == 7 * len(note.text)


def test_the_last_column_shrinks_and_its_text_wraps_when_the_table_does_not_fit():
    text = Text.of("v", "one two three four")
    table = Table([[Label("k", "attempts"), text]])
    width = 56.0 + table.gap + 7 * 10  # "one two" and "three four" fit after the key, not "one two three"
    assert table_columns(table, width, fake_measure) == [56.0, 70.0]
    assert measure(table, width, fake_measure) == 2 * LINE


def test_rows_are_as_tall_as_their_tallest_cell_and_row_gap_apart():
    table = Table([[Label("a", "a", height=20), Label("b", "b", height=30)], [Label("c", "c", height=20)]], row_gap=4.0)
    assert measure(table, 500.0, fake_measure) == 30 + 4 + 20
    arrange(table, Rect(0, 0, 500, 500), fake_measure)
    assert table.rows[1][0].rect.y == 34


def test_a_tables_cells_are_in_the_tree():
    table = key_value([("a", "1"), ("a", "2")])
    table.rows[1][0].id = "k0"
    try:
        check_unique_ids(Column(children=[table]))
    except ValueError as e:
        assert "k0" in str(e)
    else:
        raise AssertionError("a duplicate id in a table's cells went unseen")


# --- Separator


def test_a_separator_is_thin_and_takes_the_width_it_is_given():
    rule = Separator()
    column = Column(children=[Label("a", "a"), rule, Label("b", "b")], gap=0)
    arrange(column, Rect(0, 0, 200, 300), fake_measure)
    assert rule.rect == Rect(0, 26, 200, rule.height)
    assert natural_width(rule, fake_measure) is None and content_width(Row(children=[rule]), fake_measure) == 0.0


def test_a_stretch_table_gives_its_last_column_the_width_left():
    table = Table([[Label("k", "radius"), TextBox("v", "130")]], stretch=True)
    arrange(table, Rect(0, 0, 300, 100), fake_measure)
    box = table.rows[0][1]
    assert box.rect.x == table_columns(table, 300, fake_measure)[0] + table.gap
    assert box.rect.x + box.rect.width == 300
    assert table_columns(Table([[Label("k", "radius"), TextBox("v", "130")]]), 300, fake_measure)[1] == 0.0
