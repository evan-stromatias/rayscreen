"""The measure and arrange passes, with a fake text width: no window needed."""

import pytest

from rayscreen.geometry import Rect
from rayscreen.layout import arrange, board_rect, content_width, measure, natural_width, wrap_text
from rayscreen.specs import (
    CHECK,
    GAP,
    ICON,
    MIN_BUTTON,
    PAD,
    ROW,
    SCROLL_BORDER,
    SCROLLBAR,
    TEXT,
    Board,
    Button,
    CheckBox,
    Column,
    Dropdown,
    Fill,
    Label,
    Panel,
    Picture,
    Placed,
    Progress,
    Row,
    Scroll,
    Slider,
    TextBox,
    check_unique_ids,
)


def fake_measure(text: str, size: int) -> float:
    return float(len(text) * 7)


def test_leaf_measures_its_height():
    assert measure(Button("b", "Go"), 100.0, fake_measure) == ROW


def test_column_stacks_children():
    one, two = Button("one", "One"), Button("two", "Two")
    column = Column(children=[one, two])
    arrange(column, Rect(0, 0, 200, 100), fake_measure)
    assert one.rect == Rect(0, 0, 200, ROW)
    assert two.rect == Rect(0, ROW + GAP, 200, ROW)


def test_column_fill_takes_the_leftover():
    one, fill, two = Button("one", "One"), Fill(), Button("two", "Two")
    arrange(Column(children=[one, fill, two]), Rect(0, 0, 200, 100), fake_measure)
    assert fill.rect.height == 100 - 2 * ROW - 2 * GAP
    assert two.rect.y == 100 - ROW


def test_column_weights_share_the_leftover():
    small, large = Fill(weight=1), Fill(weight=3)
    arrange(Column(children=[small, large]), Rect(0, 0, 200, 100), fake_measure)
    leftover = 100 - GAP
    assert small.rect.height == leftover / 4
    assert large.rect.height == leftover * 3 / 4


def test_row_divides_equal_weights_equally():
    children = [Button(f"b{i}", f"B{i}", weight=1) for i in range(3)]
    arrange(Row(children=children), Rect(0, 0, 400, ROW), fake_measure)
    share = (400 - 2 * GAP) / 3
    assert [child.rect.width for child in children] == [share, share, share]
    assert children[1].rect.x == share + GAP


def test_row_gives_unweighted_widgets_their_natural_width():
    # the HUD: a label, a bar taking the rest, a label
    hp, bar, gold = Label("hp", "HP"), Progress("bar", 0.5, weight=3), Label("gold", "Gold: 12")
    arrange(Row(children=[hp, bar, gold]), Rect(0, 0, 400, ROW), fake_measure)
    assert hp.rect.width == 2 * 7
    assert gold.rect.width == 8 * 7
    assert bar.rect.width == 400 - 2 * GAP - hp.rect.width - gold.rect.width
    assert gold.rect.x + gold.rect.width == 400


def test_a_vertical_bar_and_a_column_with_a_width_keep_their_width_in_a_row():
    """A HUD's meters and its buttons either side of a log that takes the rest."""
    meter = Progress("hp", 0.5, vertical=True, width=22, height=80)
    buttons = Column(children=[Button("a", "Inventory"), Button("b", "Map")], width=200)
    log = Label("log", "Took a loaf", weight=1)
    row = Row(children=[meter, log, buttons])
    arrange(row, Rect(0, 0, 600, 100), fake_measure)
    assert (meter.rect.width, meter.rect.height) == (22, 80)
    assert buttons.rect.width == 200 and buttons.rect.x + 200 == 600
    assert log.rect.width == 600 - 22 - 200 - 2 * GAP
    assert measure(row, 600, fake_measure) == 80
    assert content_width(buttons, fake_measure) == 200


def test_unweighted_widgets_without_a_natural_width_share_as_weight_one():
    label, box, fill = Label("l", "Name"), TextBox("t", ""), Fill()
    arrange(Row(children=[label, box, fill]), Rect(0, 0, 200, ROW), fake_measure)
    assert box.rect.width == fill.rect.width == (200 - 2 * GAP - 4 * 7) / 2


def test_natural_widths():
    assert natural_width(Button("b", "Go"), fake_measure) == MIN_BUTTON
    assert natural_width(Button("b", "A long button text"), fake_measure) == 18 * 7 + 2 * PAD
    assert natural_width(CheckBox("c", "Music"), fake_measure) == CHECK + GAP + 5 * 7
    assert natural_width(Dropdown("d", ("Low", "Medium")), fake_measure) == 6 * 7 + ICON + GAP + 2 * PAD
    assert natural_width(Label("l", "word word", wrap=True), fake_measure) is None
    assert natural_width(Slider("s", "Volume", 1, 0, 2), fake_measure) is None


def test_natural_widths_that_do_not_fit_shrink():
    one, two, rest = Button("one", "One"), Button("two", "Two"), Fill()
    arrange(Row(children=[one, two, rest]), Rect(0, 0, 100, ROW), fake_measure)
    assert one.rect.width == two.rect.width == (100 - 2 * GAP) / 2
    assert rest.rect.width == 0


def test_row_divides_by_weights():
    one, three = Button("one", "One", weight=1), Button("three", "Three", weight=3)
    arrange(Row(children=[one, three]), Rect(0, 0, 200, ROW), fake_measure)
    available = 200 - GAP
    assert one.rect.width == available / 4
    assert three.rect.width == available * 3 / 4


def test_row_children_keep_their_natural_height():
    short, tall = Button("short", "Short"), Label("tall", "Tall", height=40)
    arrange(Row(children=[short, tall]), Rect(0, 0, 200, 40), fake_measure)
    assert measure(Row(children=[short, tall]), 200, fake_measure) == 40
    assert short.rect.height == ROW  # top-aligned, not stretched to the row's height
    assert tall.rect.height == 40


def test_panel_insets_its_child_under_the_title():
    # raygui centres the title on the box's top line: half of it is above the box, the rest in the pad
    child = Button("b", "Go")
    arrange(Panel(child=child, title="Audio"), Rect(0, 0, 200, 100), fake_measure)
    assert child.rect == Rect(PAD, TEXT / 2 + PAD, 200 - 2 * PAD, 100 - TEXT / 2 - 2 * PAD)


def test_untitled_panel_only_pads():
    child = Button("b", "Go")
    panel = Panel(child=child)
    assert measure(panel, 200, fake_measure) == ROW + 2 * PAD
    arrange(panel, Rect(0, 0, 200, 100), fake_measure)
    assert child.rect.y == PAD


def test_stacked_titled_panels_leave_room_for_the_title():
    first, second = Panel(Button("a", "A"), title="One"), Panel(Button("b", "B"), title="Two")
    arrange(Column(children=[first, second]), Rect(0, 0, 200, 300), fake_measure)
    title_top = second.rect.y  # the title's half above the line starts at the rect, the line is lower
    assert title_top >= first.rect.y + first.rect.height


def test_scroll_gives_its_child_the_natural_height():
    child = Column(children=[Button(f"b{i}", f"B{i}") for i in range(5)])
    scroll = Scroll("s", child, weight=1)
    arrange(Column(children=[Button("top", "Top"), scroll]), Rect(0, 0, 200, 100), fake_measure)
    assert scroll.rect.height == 100 - ROW - GAP  # the column's leftover
    natural = 5 * ROW + 4 * GAP
    assert child.rect.height == natural  # taller than the scroll: it scrolls
    assert child.rect == Rect(PAD, ROW + GAP + PAD, 200 - SCROLLBAR - 2 * PAD, natural)


def test_unweighted_scroll_measures_its_content_and_padding():
    child = Column(children=[Button(f"b{i}", f"B{i}") for i in range(2)])
    assert measure(Scroll("s", child, pad=6), 200, fake_measure) == 2 * ROW + GAP + 2 * 6


def test_scroll_child_fills_the_view_when_the_content_fits():
    # so a Fill in the child still pushes content apart when there is nothing to scroll; the fill
    # stops at the bounds minus raygui's border, or the bottom row ends half outside the view
    child = Column(children=[Button("b", "B"), Fill()])
    scroll = Scroll("s", child)
    arrange(scroll, Rect(0, 0, 200, 500), fake_measure)
    assert child.rect.height == 500 - 2 * SCROLL_BORDER - 2 * PAD


def test_wrapped_label_measures_its_lines():
    label = Label("l", "aaaa bbbb", wrap=True)  # 7 px a character: two lines in 35 px
    assert measure(label, 35, fake_measure) == 2 * (TEXT + 4)
    assert measure(label, 200, fake_measure) == TEXT + 4


def test_wrap_text():
    assert wrap_text("aa bb cc", 35, TEXT, fake_measure) == ["aa bb", "cc"]


def test_duplicate_ids_fail():
    with pytest.raises(ValueError, match="duplicate widget id"):
        check_unique_ids(Column(children=[Button("x", "A"), Button("x", "B")]))


def test_fixed_fill_is_a_gap_of_its_size():
    indent, label = Fill(weight=0, size=22), Label("l", "word word", wrap=True)
    arrange(Row(children=[indent, label], gap=0), Rect(0, 0, 200, ROW), fake_measure)
    assert (indent.rect.width, label.rect.x) == (22, 22)
    assert measure(Column(children=[Fill(weight=0, size=12), Button("b", "B")]), 200, fake_measure) == 12 + GAP + ROW


def test_weighted_children_of_a_row_fill_its_height():
    left = Column(children=[Button("a", "A"), Scroll("s", Column(children=[]), weight=1)], weight=1)
    right = Column(children=[Button("b", "B")], weight=1)
    fixed = Button("c", "C")
    row = Row(children=[left, right, fixed], weight=1)
    arrange(Column(children=[row]), Rect(0, 0, 600, 400), fake_measure)
    assert left.rect.height == right.rect.height == 400
    assert left.children[1].rect.height == 400 - ROW - GAP  # the scroll gets what its column leaves
    assert fixed.rect.height == ROW  # unweighted: its natural height


def test_a_fit_panel_in_a_row_is_as_wide_as_its_text():
    text = Column(children=[Label("a", "short"), Label("b", "the longest line")], gap=0)
    fitted, shared = Panel(text, fit=True, backdrop=0.6), Panel(Label("c", "x"))
    arrange(Row(children=[fitted, Fill(), shared]), Rect(0, 0, 1000, 100), fake_measure)
    assert fitted.rect.width == fake_measure("the longest line", TEXT) + 2 * PAD
    assert shared.rect.width > 300  # a panel takes a share, as before


def test_a_picture_with_a_width_keeps_it_in_a_row():
    portrait, fill = Picture("face", height=120, width=120), Fill(weight=1)
    arrange(Row(children=[portrait, fill]), Rect(0, 0, 500, 120), fake_measure)
    assert (portrait.rect.x, portrait.rect.width) == (0, 120)
    assert natural_width(Picture("p"), fake_measure) is None


def test_a_board_measures_by_its_aspect_and_keeps_it_centred():
    board = Board(Picture("bg"), [Placed(Picture("box", width=40, height=40), (0.5, 0.5))], aspect=0.5)
    assert measure(board, 200, fake_measure) == 400
    wide, tall = Rect(0, 0, 300, 500), Rect(0, 0, 100, 500)
    assert board_rect(board, wide) == Rect(25, 0, 250, 500)  # as tall as fits, centred across
    assert board_rect(board, tall) == Rect(0, 150, 100, 200)  # as wide as fits, centred down

    box = board.children[0].child
    arrange(board, wide, fake_measure)
    assert box.rect == Rect(25 + 125 - 20, 250 - 20, 40, 40)  # the middle of the fitted rect
    assert board.background.rect == Rect(25, 0, 250, 500)


def test_a_boards_children_keep_their_own_sizes_and_places():
    square = Picture("square", height=48)  # no width: square on its height
    label = Label("label", "Right hand")  # its text's width
    board = Board(Picture("bg"), [Placed(square, (0.0, 0.0)), Placed(label, (1.0, 1.0))], aspect=1.0)
    arrange(board, Rect(0, 0, 400, 400), fake_measure)
    assert square.rect == Rect(-24, -24, 48, 48)  # a corner's middle is the corner
    assert label.rect.width == fake_measure("Right hand", TEXT)
    assert label.rect.x == 400 - label.rect.width / 2 and label.rect.y == 400 - ROW / 2


def test_a_weighted_column_with_a_width_keeps_it_and_fills_the_rows_height():
    pane = Column(children=[Label("a", "a")], width=120.0, weight=1)
    rest = Column(children=[Label("b", "b")], weight=1)
    row = Row(children=[rest, pane])
    arrange(row, Rect(0, 0, 500, 300), fake_measure)
    assert pane.rect.width == 120.0 and pane.rect.height == 300.0  # its own width, the row's whole height
    assert rest.rect.width == 500 - 120 - row.gap and rest.rect.height == 300.0
