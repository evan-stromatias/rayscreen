"""UiState's pure parts: the frame-start snapshot and the lazily made scroll pointers. No window
needed (Esc is only polled while a box is being edited, which these tests never do)."""

from rayscreen.state import UiState


def test_begin_snapshots_the_editing_state():
    state = UiState()
    assert state.begin() is False
    state.editing = "player"
    state.begin()
    assert state._editing == "player"
    state.editing = None
    state.begin()
    assert state._editing is None


def test_scroll_pointers_are_stable_per_id():
    state = UiState()
    assert state.scroll_ptr("s") is state.scroll_ptr("s")
    assert state.scroll_ptr("s") is not state.scroll_ptr("t")
    assert state.list_scroll_ptr("l") is state.list_scroll_ptr("l")


def test_a_held_slider_is_forgotten_when_it_leaves_the_tree():
    state = UiState()
    state.sliding = "volume"
    state.keep({"volume", "name"})
    assert state.sliding == "volume"
    state.keep({"name"})
    assert state.sliding is None


def test_a_follow_scroll_starts_at_the_bottom_and_follows_while_there():
    state = UiState()
    assert state.follow("chat", 0.0, -40.0) == -40.0  # first frame: the newest line shows
    assert state.follow("chat", -40.0, -70.0) == -70.0  # content grew while at the bottom
    assert state.follow("chat", -20.0, -70.0) == -20.0  # the user scrolled up
    assert state.follow("chat", -20.0, -95.0) == -20.0  # and it stays there as content grows
    assert state.follow("chat", -95.0, -95.0) == -95.0  # back at the bottom
    assert state.follow("chat", -95.0, -120.0) == -120.0  # follows again


def test_a_follow_scroll_forgets_its_bottom_when_it_leaves_the_tree():
    state = UiState()
    state.follow("chat", 0.0, -40.0)
    state.follow("chat", -10.0, -40.0)
    state.keep(set())
    assert state.follow("chat", -10.0, -60.0) == -60.0


def test_a_draft_is_taken_once():
    state = UiState()
    state.drafts["say"] = "Is the road safe?"
    assert state.take_draft("say") == "Is the road safe?"
    assert state.take_draft("say") == ""


def test_taking_the_draft_of_the_box_being_edited_clears_it():
    state = UiState()
    state.editing = "say"
    state.buffer[0:5] = b"Hello"
    assert state.take_draft("say") == "Hello"
    assert state.take_draft("say") == "" and state.editing == "say"
