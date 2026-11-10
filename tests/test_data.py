"""Plain data as specs (`data_tree`), laid out without a window."""

from rayscreen.data import BULLET, data_tree
from rayscreen.geometry import Rect
from rayscreen.layout import arrange
from rayscreen.specs import Label, Table, Text, Tooltip, walk

ANSWER = {"reasoning": "A stranger asking about the road, and too many questions for an honest traveller to need.",
          "reply": "Safe enough.", "feeling": {"mood": "content", "intensity": "very"}, "tools": [], "retries": 1,
          "ended": None, "polite": False}


def fake_measure(text: str, size: int) -> float:
    return len(text) * size * 0.5


def leaves(node) -> dict[str, tuple[str, str]]:
    """Each text's id -> (its text, its tone)."""
    return {n.id: ("".join(s.text for s in n.spans), n.spans[0].tone) for n in walk(node) if isinstance(n, Text)}


def test_a_dict_is_its_keys_beside_its_values_with_tones_by_type():
    tree = data_tree("answer", ANSWER)
    assert isinstance(tree, Table)
    assert [row[0].text for row in tree.rows] == list(ANSWER)
    assert all(isinstance(row[0], Label) and row[0].tone == "muted" for row in tree.rows)
    texts = leaves(tree)
    assert texts["answer.reply"] == ("Safe enough.", "ink")
    assert texts["answer.tools"] == ("[]", "muted")
    assert texts["answer.retries"] == ("1", "info")
    assert texts["answer.ended"] == ("null", "muted")
    assert texts["answer.polite"] == ("false", "warning")


def test_a_nested_dict_is_a_table_in_its_value_cell():
    tree = data_tree("answer", ANSWER)
    feeling = tree.rows[2][1]
    assert isinstance(feeling, Table) and [row[0].text for row in feeling.rows] == ["mood", "intensity"]
    assert leaves(feeling)["answer.feeling.intensity"] == ("very", "ink")


def test_a_list_is_bullets():
    tree = data_tree("calls", ["end_conversation(reason='rude')", {"name": "give"}])
    assert [row[0].text for row in tree.rows] == [BULLET, BULLET]
    assert isinstance(tree.rows[1][1], Table)


def test_ids_are_unique_and_a_tooltip_takes_the_tree():
    Tooltip("answer", data_tree("answer", ANSWER))  # checks its ids are unique


def test_nesting_indents_and_long_strings_wrap_in_the_value_column():
    tree = data_tree("answer", ANSWER)
    arrange(tree, Rect(0, 0, 300, 400), fake_measure)
    keys_right = max(row[0].rect.x + row[0].rect.width for row in tree.rows)
    reasoning, feeling = tree.rows[0][1], tree.rows[2][1]
    assert reasoning.rect.x > keys_right and feeling.rect.x == reasoning.rect.x
    assert reasoning.rect.x + reasoning.rect.width <= 300 and reasoning.rect.height > fake_measure("x", reasoning.size)
    assert feeling.rows[0][1].rect.x > feeling.rect.x  # its own values sit right of its own keys
