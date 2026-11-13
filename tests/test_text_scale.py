"""A container's `text_scale` and a widget's own text `size`: what they measure and arrange to, with a fake text
width. No window needed."""

from rayscreen.geometry import Rect
from rayscreen.layout import arrange, content_width, icon_scale, measure, natural_width, scaled, text_size, title_strip
from rayscreen.navigation import focusables, into_view
from rayscreen.specs import CHECK, GAP, MIN_BUTTON, PAD, ROW, SMALL, TEXT, Button, CheckBox, Column, Label, Panel, Row, Scroll, Slider, Text, TextBox, Toggle


def fake_measure(text: str, size: int) -> float:
    return len(text) * size * 0.5


def widgets(prefix: str) -> list:
    return [Label(f"{prefix}.label", "Name"), Button(f"{prefix}.button", "OK"), Toggle(f"{prefix}.toggle", "Happy"),
            Slider(f"{prefix}.slider", "Size", 5, 0, 10), TextBox(f"{prefix}.box", "Mira")]


def test_a_button_with_a_size_measures_wider_sized_to_its_text():
    text = "A long button text"
    assert natural_width(Button("big", text, size=32), fake_measure) > natural_width(Button("plain", text), fake_measure)
    assert natural_width(Button("big", "OK", size=32), fake_measure) == 2 * MIN_BUTTON  # its least width grows too
    assert measure(Button("big", "OK", size=32), 200, fake_measure) == 2 * ROW
    assert measure(Button("tall", "OK", size=32, height=30), 200, fake_measure) == 30


def test_a_scaled_column_measures_its_rows_twice_as_tall_and_a_sibling_as_before():
    scaled, plain = Column(children=widgets("big"), text_scale=2.0), Column(children=widgets("plain"))
    root = Row(children=[scaled, plain], gap=0)
    arrange(root, Rect(0, 0, 800, 600), fake_measure)
    for big, normal in zip(scaled.children, plain.children):
        assert big.rect.height == 2 * normal.rect.height == 2 * ROW
    for above, below in zip(scaled.children, scaled.children[1:]):
        assert above.rect.y + above.rect.height + GAP == below.rect.y  # no overlap
    assert plain.children[1].rect.y == ROW + GAP  # as without a scale
    assert measure(scaled, 400, fake_measure) == 5 * 2 * ROW + 4 * GAP


def test_the_text_under_a_scale_is_its_size_times_it():
    assert text_size(Label("l", "x"), 1.5) == 24
    assert text_size(Label("l", "x", size=SMALL), 2.0) == 2 * SMALL
    assert text_size(Button("b", "x"), 2.0) == 2 * TEXT
    assert text_size(Text.of("t", "x"), 1.5) == 24
    assert icon_scale(text_size(Button("b", "x"), 2.0)) == 2 and icon_scale(TEXT) == 1


def test_widths_sized_to_their_text_measure_at_the_scaled_size():
    row = Row(children=[Button("b", "A long button text"), CheckBox("c", "Check")], text_scale=2.0)
    plain = Row(children=[Button("b2", "A long button text"), CheckBox("c2", "Check")])
    arrange(Column(children=[row, plain]), Rect(0, 0, 1000, 400), fake_measure)
    assert row.children[0].rect.width == fake_measure("A long button text", 32) + 2 * PAD
    assert row.children[1].rect.width == 2 * CHECK + GAP + fake_measure("Check", 32)
    assert plain.children[0].rect.width == fake_measure("A long button text", TEXT) + 2 * PAD
    assert content_width(row, fake_measure) == content_width(plain, fake_measure, 2.0)


def test_a_nested_scale_replaces_the_outer_and_a_widgets_own_size_wins():
    inner = Column(children=[Label("inner", "x"), Button("own", "x", size=20)], text_scale=1.0)
    outer = Column(children=[Label("outer", "x"), inner], text_scale=2.0)
    arrange(outer, Rect(0, 0, 400, 400), fake_measure)
    assert outer.children[0].rect.height == 2 * ROW
    assert inner.children[0].rect.height == ROW
    assert inner.children[1].rect.height == ROW * 20 / TEXT
    assert text_size(inner.children[1], 2.0) == 20


def test_an_explicit_height_stays_as_given_under_a_scale():
    column = Column(children=[Label("l", "x", height=30), Slider("s", "x", 0, 0, 1, height=20)], text_scale=2.0)
    arrange(column, Rect(0, 0, 400, 400), fake_measure)
    assert [child.rect.height for child in column.children] == [30, 20]


def test_a_scroll_of_scaled_content_scrolls_its_scaled_height_and_brings_the_focus_into_view():
    content = Column(children=[Button(f"b{i}", f"Item {i}") for i in range(10)], text_scale=2.0)
    scroll = Scroll("list", content, weight=1)
    root = Column(children=[scroll])
    arrange(root, Rect(0, 0, 300, 200), fake_measure)
    assert content.rect.height == 10 * 2 * ROW + 9 * GAP
    last = [placed for placed in focusables(root) if placed.node.id == "b9"][0]
    offset = into_view(last, 0.0)
    assert last.rect.y + last.rect.height + scroll.pad + offset <= scroll.rect.y + scroll.rect.height


def titled(scale: float | None, title: str = "Make your character") -> tuple[Column, Panel]:
    panel = Panel(Column(children=[Button("a", "First"), Button("b", "Second")]), title=title, weight=1.0)
    return Column(children=[panel], text_scale=scale), panel


def test_a_scaled_panels_content_clears_the_lower_half_of_its_title():
    root, panel = titled(2.0)
    arrange(root, Rect(0, 0, 400, 400), fake_measure)
    line = panel.rect.y + title_strip(panel, 2.0)  # the box's top line, which the title is centred on
    assert panel.child.rect.y - line >= scaled(TEXT, 2.0) / 2
    first = panel.child.children[0]
    assert measure(panel, 400, fake_measure, 2.0) == first.rect.height + GAP + first.rect.height + (first.rect.y - panel.rect.y) + PAD


def test_an_unscaled_or_untitled_panel_lays_out_as_before():
    for scale, title in ((None, "Title"), (1.0, "Title"), (2.0, "")):
        root, panel = titled(scale, title)
        arrange(root, Rect(0, 0, 400, 400), fake_measure)
        assert panel.child.rect.y == title_strip(panel, scale or 1.0) + PAD
