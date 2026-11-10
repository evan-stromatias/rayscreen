"""Tests for `Window.handle`, `dispatch`, and `FileWindow`. No raylib window needed."""

from pathlib import Path

from rayscreen import (
    Button,
    Column,
    Dropdown,
    Event,
    FileWindow,
    Fill,
    Label,
    Screen,
    TextBox,
    Toggle,
    dispatch,
    format_size,
)


def _make_tree(tmp_path: Path) -> Path:
    (tmp_path / "beta").mkdir()
    (tmp_path / "alpha").mkdir()
    (tmp_path / ".secret").mkdir()
    (tmp_path / "alpha" / "nested.png").write_bytes(b"1234")
    (tmp_path / "zebra.png").write_bytes(b"x" * 2048)
    (tmp_path / "map.png").write_bytes(b"x" * 120)
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
    (tmp_path / ".hidden.png").write_bytes(b"x" * 10)
    return tmp_path


def test_format_size():
    assert format_size(0) == "0 B"
    assert format_size(512) == "512 B"
    assert format_size(2048) == "2.0 KB"
    assert format_size(2 * 1024 * 1024) == "2.0 MB"
    assert format_size(3 * 1024 * 1024 * 1024) == "3.0 GB"


def test_load_file_listing_sorting_filter_and_hidden(tmp_path: Path):
    root = _make_tree(tmp_path)
    window = FileWindow(
        "dlg",
        "Load PNG",
        path=root,
        mode="load_file",
        suffixes=(".png",),
        prompt="Pick a PNG.",
    )
    assert window.cwd == root.resolve()
    assert window.name == ""
    assert not window.can_confirm
    assert [d.name for d in window.dirs] == ["alpha", "beta"]
    assert [f.name for f in window.files] == ["map.png", "zebra.png"]
    assert isinstance(window.find("dlg.prompt"), Label)
    assert window.find("dlg.mkdir") is None

    screen = Screen("s", Column(children=[Fill()]))
    screen.open(window)

    # Toggle hidden files on -> .secret/ and .hidden.png appear
    assert dispatch(screen, [Event("s", "dlg.hidden", True)]) == []
    assert [d.name for d in window.dirs] == [".secret", "alpha", "beta"]
    assert [f.name for f in window.files] == [".hidden.png", "map.png", "zebra.png"]

    # Switch filter to "All files" -> notes.txt appears
    assert dispatch(screen, [Event("s", "dlg.filter", "All files")]) == []
    assert [f.name for f in window.files] == [".hidden.png", "map.png", "notes.txt", "zebra.png"]

    # Switch filter back to "*.png" and hide hidden files
    assert dispatch(screen, [Event("s", "dlg.filter", "*.png"), Event("s", "dlg.hidden", False)]) == []
    assert [f.name for f in window.files] == ["map.png", "zebra.png"]


def test_load_file_selection_requires_ok_button_to_confirm(tmp_path: Path):
    root = _make_tree(tmp_path)
    screen = Screen("s", Column(children=[Fill()]))
    window = FileWindow("dlg", "Load PNG", path=root, mode="load_file", suffixes=(".png",))
    screen.open(window)

    # Clicking the first file selects it; clicking it a second time keeps it selected without closing
    assert dispatch(screen, [Event("s", "dlg.file.0", True)]) == []
    assert window.name == "map.png"
    assert window.can_confirm
    assert screen.window is window

    assert dispatch(screen, [Event("s", "dlg.file.0", False)]) == []
    assert window.name == "map.png"
    assert screen.window is window
    file_toggle = window.find("dlg.file.0")
    assert isinstance(file_toggle, Toggle) and file_toggle.active

    # Clicking Load confirms, closes the window, and emits Event(screen.id, window.id, str(chosen_path))
    events = dispatch(screen, [Event("s", "dlg.ok", None)])
    assert events == [Event("s", "dlg", str((root / "map.png").resolve()))]
    assert screen.window is None


def test_navigation_into_subfolder_up_home_and_typed_cwd(tmp_path: Path):
    root = _make_tree(tmp_path)
    screen = Screen("s", Column(children=[Fill()]))
    window = FileWindow("dlg", "Load PNG", path=root / "map.png", mode="load_file", suffixes=(".png",))
    screen.open(window)
    assert window.cwd == root.resolve()
    assert window.name == "map.png"

    # Scroll down, then enter alpha/ -> scroll resets to 0.0 and name clears in load_file mode
    window.state.scroll_ptr("dlg.scroll")[0].y = -40.0
    assert dispatch(screen, [Event("s", "dlg.dir.0", None)]) == []
    assert window.cwd == (root / "alpha").resolve()
    assert window.name == ""
    assert window.state.scroll_ptr("dlg.scroll")[0].y == 0.0
    assert [f.name for f in window.files] == ["nested.png"]

    # Go up to parent
    assert dispatch(screen, [Event("s", "dlg.up", None)]) == []
    assert window.cwd == root.resolve()

    # Type an invalid cwd -> outlines cwd box in error and disables confirm
    assert dispatch(screen, [Event("s", "dlg.cwd", str(root / "no-such-folder"))]) == []
    assert window.cwd_invalid
    cwd_box = window.find("dlg.cwd")
    assert isinstance(cwd_box, TextBox) and cwd_box.invalid
    target_label = window.find("dlg.target")
    assert isinstance(target_label, Label) and target_label.tone == "error"

    # Type a file path into cwd in load_file mode -> navigates to its parent and sets name
    nested = root / "alpha" / "nested.png"
    assert dispatch(screen, [Event("s", "dlg.cwd", str(nested))]) == []
    assert not window.cwd_invalid
    assert window.cwd == (root / "alpha").resolve()
    assert window.name == "nested.png"
    assert window.can_confirm

    # Home button navigates to Path.home()
    assert dispatch(screen, [Event("s", "dlg.home", None)]) == []
    assert window.cwd == Path.home().resolve()


def test_save_file_auto_appends_suffix_and_creates_folder(tmp_path: Path):
    root = _make_tree(tmp_path)
    screen = Screen("s", Column(children=[Fill()]))
    extra = Dropdown("dlg.layer", ("Full", "Districts"))
    window = FileWindow(
        "dlg",
        "Save PNG",
        path=root / "world-map.png",
        mode="save_file",
        suffixes=(".png",),
        extra=(extra,),
    )
    screen.open(window)
    assert window.cwd == root.resolve()
    assert window.name == "world-map.png"
    assert window.can_confirm
    assert window.find("dlg.layer") is extra

    # Typing a new folder name enables mkdir; clicking mkdir creates and enters it, clearing name
    assert dispatch(screen, [Event("s", "dlg.name", "exports")]) == []
    assert window.can_mkdir
    assert dispatch(screen, [Event("s", "dlg.mkdir", None)]) == []
    assert (root / "exports").is_dir()
    assert window.cwd == (root / "exports").resolve()
    assert window.name == ""
    assert not window.can_confirm

    # Typing a filename without .png auto-appends .png in chosen_path()
    assert dispatch(screen, [Event("s", "dlg.name", "town")]) == []
    assert window.chosen_path() == (root / "exports" / "town.png").resolve()
    assert window.can_confirm

    events = dispatch(screen, [Event("s", "dlg.ok", None)])
    assert events == [Event("s", "dlg", str((root / "exports" / "town.png").resolve()))]
    assert screen.window is None


def test_directory_mode_selects_cwd_or_new_subfolder_and_disables_file_rows(tmp_path: Path):
    root = _make_tree(tmp_path)
    screen = Screen("s", Column(children=[Fill()]))
    window = FileWindow(
        "dlg",
        "Save world",
        path=root / "archipelago",
        mode="directory",
        ok="Save",
    )
    screen.open(window)
    assert window.cwd == root.resolve()
    assert window.name == "archipelago"
    assert window.chosen_path() == (root / "archipelago").resolve()
    assert window.can_confirm

    # Files in cwd are shown disabled so the user can see what is inside the folder
    file_toggle = window.find("dlg.file.0")
    assert isinstance(file_toggle, Toggle) and not file_toggle.enabled

    # Entering an existing directory clears name so the entered directory itself is the target
    assert dispatch(screen, [Event("s", "dlg.dir.0", None)]) == []
    assert window.cwd == (root / "alpha").resolve()
    assert window.name == ""
    assert window.chosen_path() == (root / "alpha").resolve()
    assert window.can_confirm

    # Typing the name of an existing regular file makes can_confirm False
    assert dispatch(screen, [Event("s", "dlg.name", "nested.png")]) == []
    assert not window.can_confirm
    ok_btn = window.find("dlg.ok")
    assert isinstance(ok_btn, Button) and not ok_btn.enabled

    # Relative path with .. in the name box resolves against cwd
    assert dispatch(screen, [Event("s", "dlg.name", "../new_world")]) == []
    assert window.cwd == root.resolve()
    assert window.name == "new_world"
    assert window.can_confirm

    # Cancel closes the window and emits Event(screen.id, window.id, None)
    events = dispatch(screen, [Event("s", "dlg.cancel", None)])
    assert events == [Event("s", "dlg", None)]
    assert screen.window is None


def test_mkdir_button_opens_inline_new_folder_bar_when_name_is_empty(tmp_path: Path):
    root = _make_tree(tmp_path)
    screen = Screen("s", Column(children=[Fill()]))
    window = FileWindow("dlg", "Save directory", path=root, mode="directory", ok="Save")
    screen.open(window)

    # Even when Folder (name) is empty, the mkdir button is enabled
    mkdir_btn = window.find("dlg.mkdir")
    assert isinstance(mkdir_btn, Button) and mkdir_btn.enabled

    # Clicking mkdir when name is empty opens the inline New folder bar with default "new_folder"
    assert dispatch(screen, [Event("s", "dlg.mkdir", None)]) == []
    assert window.mkdir_open and window.mkdir_name == "new_folder"
    assert isinstance(window.find("dlg.mkdir.name"), TextBox)

    # Typing a custom name and clicking Create creates the folder and enters it
    assert dispatch(screen, [Event("s", "dlg.mkdir.name", "bundle_out"), Event("s", "dlg.mkdir.ok", None)]) == []
    assert not window.mkdir_open
    assert (root / "bundle_out").is_dir()
    assert window.cwd == (root / "bundle_out").resolve()
    assert window.name == ""

