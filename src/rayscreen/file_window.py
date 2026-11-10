"""Modal file and directory selection window (`FileWindow`), built from `pathlib.Path` and rayscreen specs with no raylib.

- Supports `"load_file"` (pick an existing file), `"save_file"` (pick an existing or new file in `cwd`), and
  `"directory"` (pick `cwd` itself or an existing/new folder inside `cwd`).
- Internal navigation (entering folders, going up or home, editing `cwd` or `name`, toggling hidden files, filtering by
  extension, making a new folder) is handled inside `FileWindow.handle`; the screen only receives
  `Event(screen.id, window.id, str(chosen_path))` on confirm or `Event(screen.id, window.id, None)` on cancel/close.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pyray import ffi

from rayscreen.screen import Event, Screen, Window
from rayscreen.specs import (
    ROW,
    SMALL,
    Button,
    CheckBox,
    Column,
    Dropdown,
    Label,
    Node,
    Row,
    Scroll,
    TextBox,
    Toggle,
    Tooltip,
)

type FileMode = Literal["load_file", "save_file", "directory"]

DEFAULT_SIZE = (620.0, 460.0)
_DEFAULT_OK: dict[FileMode, str] = {
    "load_file": "Load",
    "save_file": "Save",
    "directory": "Select",
}


def format_size(num_bytes: int) -> str:
    """Human-readable byte count for a file row (`"142.3 KB"`)."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    if num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    return f"{num_bytes / (1024 * 1024 * 1024):.1f} GB"


def _normalize_suffixes(suffixes: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for raw in suffixes:
        ext = raw.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        if ext not in normalized:
            normalized.append(ext)
    return tuple(normalized)


def _nearest_existing_dir(start: Path) -> Path:
    for candidate in (start, *start.parents):
        try:
            if candidate.is_dir():
                return candidate.resolve()
        except OSError:
            continue
    return Path.cwd().resolve()


class FileWindow(Window):
    """A modal dialog for picking a file to load, a file path to save to, or a directory path."""

    def __init__(
        self,
        id: str,
        title: str,
        path: str | Path = ".",
        *,
        mode: FileMode = "load_file",
        suffixes: Sequence[str] = (),
        prompt: str = "",
        ok: str | None = None,
        extra: Sequence[Node] = (),
        size: tuple[float, float] = DEFAULT_SIZE,
    ) -> None:
        self.mode: FileMode = mode
        self.suffixes = _normalize_suffixes(suffixes)
        self.prompt = prompt
        self.ok_label = ok if ok is not None else _DEFAULT_OK[mode]
        self.extra = tuple(extra)
        self.show_hidden = False
        self.filter_index = 0

        raw = Path(path).expanduser() if str(path) else Path(".")
        if raw.is_dir():
            self.cwd = raw.resolve()
            self.name = ""
        else:
            resolved = raw.resolve()
            self.cwd = _nearest_existing_dir(resolved.parent)
            self.name = raw.name

        self.cwd_text = str(self.cwd)
        self.cwd_invalid = False
        self.mkdir_open = False
        self.mkdir_name = ""
        self.dirs: list[Path] = []
        self.files: list[Path] = []
        super().__init__(id, title, Column(children=[]), size=size, resizable=True, modal=True)
        self.refresh()

    def _filter_label(self) -> str:
        return ", ".join(f"*{ext}" for ext in self.suffixes)

    def _filter_active(self) -> bool:
        return bool(self.suffixes) and self.filter_index == 0

    def _matches_filter(self, path: Path) -> bool:
        if not self._filter_active():
            return True
        return path.suffix.lower() in self.suffixes

    def chosen_path(self) -> Path:
        """The resolved target path for the current `cwd` and `name`."""
        if self.mode == "directory":
            return self.cwd if not self.name else self.cwd / self.name
        if not self.name:
            return self.cwd
        name = self.name
        if self.mode == "save_file" and self._filter_active() and Path(name).suffix.lower() not in self.suffixes:
            name = f"{name}{self.suffixes[0]}"
        return self.cwd / name

    @property
    def can_confirm(self) -> bool:
        """Whether the OK button is enabled for the current selection."""
        if self.cwd_invalid or not self.cwd.is_dir():
            return False
        target = self.chosen_path()
        if self.mode == "load_file":
            return bool(self.name) and target.is_file() and self._matches_filter(target)
        if self.mode == "save_file":
            return bool(self.name) and not target.is_dir() and target.parent.is_dir()
        return not target.is_file() and target.parent.is_dir()

    def _live_text(self, box_id: str, fallback: str) -> str:
        """The text in `box_id`, including uncommitted characters while the user is still editing the box."""
        if box_id in (self.state.editing, self.state._editing):
            return ffi.string(self.state.buffer).decode("utf-8", "replace")
        return fallback

    def _valid_new_folder(self, candidate: str) -> bool:
        cleaned = candidate.strip()
        if not cleaned or cleaned in (".", "..") or "/" in cleaned or "\\" in cleaned:
            return False
        return not self.cwd_invalid and self.cwd.is_dir() and not (self.cwd / cleaned).exists()

    def _default_new_folder_name(self) -> str:
        base = "new_folder"
        if not (self.cwd / base).exists():
            return base
        i = 2
        while (self.cwd / f"{base}_{i}").exists():
            i += 1
        return f"{base}_{i}"

    @property
    def can_mkdir(self) -> bool:
        """Whether `name` (or `mkdir_name` when the inline bar is open) is a valid new subdirectory inside `cwd`."""
        if self.mkdir_open:
            return self._valid_new_folder(self._live_text(f"{self.id}.mkdir.name", self.mkdir_name))
        candidate = self._live_text(f"{self.id}.name", self.name).strip()
        if self.mode == "save_file" and self.suffixes and Path(candidate).suffix.lower() in self.suffixes:
            return False
        return self._valid_new_folder(candidate)

    def _target_status(self) -> tuple[str, bool]:
        """The text and whether it is an error problem for the bottom target label."""
        if self.cwd_invalid or not self.cwd.is_dir():
            return "Directory does not exist", True
        target = self.chosen_path()
        if self.mode == "load_file":
            if not self.name:
                return str(self.cwd), False
            if target.is_dir():
                return "Target is a directory", True
            if not target.is_file():
                return "File does not exist", True
            if not self._matches_filter(target):
                return f"File must match {self._filter_label()}", True
            return str(target), False
        if self.mode == "save_file":
            if not self.name:
                return str(self.cwd), False
            if target.is_dir():
                return "Target is an existing directory", True
            if not target.parent.is_dir():
                return "Parent directory does not exist", True
            return str(target), False
        if target.is_file():
            return "Target is an existing file", True
        if not target.parent.is_dir():
            return "Parent directory does not exist", True
        return str(target), False

    def _scan_entries(self) -> None:
        dirs: list[Path] = []
        files: list[Path] = []
        try:
            entries = list(self.cwd.iterdir())
        except OSError:
            entries = []
        for entry in entries:
            if not self.show_hidden and entry.name.startswith("."):
                continue
            try:
                if entry.is_dir():
                    dirs.append(entry)
                elif entry.is_file() and self._matches_filter(entry):
                    files.append(entry)
            except OSError:
                continue
        dirs.sort(key=lambda p: p.name.lower())
        files.sort(key=lambda p: p.name.lower())
        self.dirs = dirs
        self.files = files

    def _build(self) -> Column:
        self._scan_entries()
        children: list[Node] = []
        if self.prompt:
            children.append(Label(f"{self.id}.prompt", self.prompt, size=SMALL, wrap=True, tone="muted"))

        path_bar: list[Node] = [
            Button(
                f"{self.id}.up",
                "#117#",
                width=ROW,
                enabled=self.cwd != self.cwd.parent,
                tooltip=Tooltip.text(f"{self.id}.up", "Parent folder"),
            ),
            Button(
                f"{self.id}.home",
                "#185#",
                width=ROW,
                tooltip=Tooltip.text(f"{self.id}.home", "Home folder"),
            ),
            TextBox(f"{self.id}.cwd", self.cwd_text, invalid=self.cwd_invalid, weight=1),
        ]
        if self.mode in ("save_file", "directory"):
            path_bar.append(
                Button(
                    f"{self.id}.mkdir",
                    "#204#",
                    width=ROW,
                    enabled=not self.cwd_invalid and self.cwd.is_dir(),
                    tooltip=Tooltip.text(
                        f"{self.id}.mkdir",
                        "Create folder",
                        "Create the folder named in Folder, or open a New folder prompt.",
                    ),
                )
            )
        children.append(Row(children=path_bar))
        if self.mkdir_open:
            children.append(
                Row(
                    children=[
                        Label(f"{self.id}.mkdir.label", "New folder", size=SMALL, tone="muted"),
                        TextBox(f"{self.id}.mkdir.name", self.mkdir_name, weight=1),
                        Button(
                            f"{self.id}.mkdir.ok",
                            "Create",
                            enabled=self._valid_new_folder(self.mkdir_name),
                        ),
                        Button(f"{self.id}.mkdir.cancel", "Cancel"),
                    ]
                )
            )

        entry_rows: list[Node] = [
            Button(f"{self.id}.dir.{i}", f"#217# {entry.name}/", align="left")
            for i, entry in enumerate(self.dirs)
        ]
        for i, entry in enumerate(self.files):
            try:
                size_text = format_size(entry.stat().st_size)
            except OSError:
                size_text = ""
            entry_rows.append(
                Row(
                    children=[
                        Toggle(
                            f"{self.id}.file.{i}",
                            f"#218# {entry.name}",
                            active=self.mode != "directory" and entry.name == self.name,
                            align="left",
                            enabled=self.mode != "directory",
                            weight=1,
                        ),
                        Label(f"{self.id}.size.{i}", size_text, size=SMALL, tone="muted"),
                    ]
                )
            )
        if not entry_rows:
            entry_rows.append(Label(f"{self.id}.empty", "Empty folder", size=SMALL, tone="muted"))
        children.append(Scroll(f"{self.id}.scroll", Column(children=entry_rows), weight=1))

        name_row: list[Node] = [
            Label(f"{self.id}.name.label", "Folder" if self.mode == "directory" else "File"),
            TextBox(f"{self.id}.name", self.name, weight=1),
        ]
        if self.suffixes:
            choices = (self._filter_label(), "All files")
            name_row.append(Dropdown(f"{self.id}.filter", choices, self.filter_index))
        children.append(Row(children=name_row))

        children.extend(self.extra)

        target_text, problem = self._target_status()
        children.append(
            Row(
                children=[
                    CheckBox(f"{self.id}.hidden", "Hidden", self.show_hidden),
                    Label(
                        f"{self.id}.target",
                        target_text,
                        size=SMALL,
                        tone="error" if problem else "muted",
                        elide=True,
                        weight=1,
                    ),
                    Button(f"{self.id}.cancel", "Cancel"),
                    Button(f"{self.id}.ok", self.ok_label, enabled=self.can_confirm),
                ]
            )
        )
        return Column(children=children)

    def refresh(self) -> None:
        """Rebuild the window's widget tree after a path or filter change."""
        self.set_root(self._build())

    def _enter_dir(self, directory: Path, *, keep_name: bool = False) -> None:
        self.cwd = directory.resolve()
        self.cwd_text = str(self.cwd)
        self.cwd_invalid = False
        self.mkdir_open = False
        self.mkdir_name = ""
        if not keep_name and self.mode != "save_file":
            self.name = ""
        self.state.scroll_ptr(f"{self.id}.scroll")[0].y = 0.0
        self.refresh()

    def _create_and_enter(self, folder_name: str) -> None:
        cleaned = folder_name.strip()
        if not self._valid_new_folder(cleaned):
            return
        new_dir = self.cwd / cleaned
        new_dir.mkdir(parents=True, exist_ok=True)
        self.state.editing = None
        if self.mode != "save_file":
            self.name = ""
        self._enter_dir(new_dir, keep_name=True)

    def _handle_cwd_edit(self, text: str) -> None:
        raw = text.strip()
        if not raw:
            self.cwd_text = str(self.cwd)
            self.cwd_invalid = False
            self.refresh()
            return
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = self.cwd / candidate
        if candidate.is_dir():
            self._enter_dir(candidate)
            return
        if self.mode in ("load_file", "save_file") and candidate.is_file():
            self.name = candidate.name
            self._enter_dir(candidate.parent, keep_name=True)
            return
        self.cwd_text = raw
        self.cwd_invalid = True
        self.refresh()

    def _handle_name_edit(self, text: str) -> None:
        cleaned = text.strip()
        if not cleaned:
            self.name = ""
            self.refresh()
            return
        if "/" in cleaned or "\\" in cleaned or cleaned in (".", "..") or cleaned.startswith("~"):
            candidate = Path(cleaned).expanduser()
            if not candidate.is_absolute():
                candidate = self.cwd / candidate
            if candidate.is_dir():
                self.name = ""
                self._enter_dir(candidate, keep_name=True)
                return
            if candidate.parent.is_dir():
                self.name = candidate.name
                self._enter_dir(candidate.parent, keep_name=True)
                return
        self.name = cleaned
        self.refresh()

    def handle(self, screen: Screen, event: Event) -> Event | bool:
        prefix = f"{self.id}."
        if not event.widget.startswith(prefix):
            return False
        action = event.widget.removeprefix(prefix)
        if action == "up":
            if self.cwd != self.cwd.parent:
                self._enter_dir(self.cwd.parent)
            return True
        if action == "home":
            self._enter_dir(Path.home())
            return True
        if action == "cwd" and isinstance(event.value, str):
            self._handle_cwd_edit(event.value)
            return True
        if action == "mkdir":
            live_name = self._live_text(f"{self.id}.name", self.name).strip()
            is_file_name = self.mode == "save_file" and bool(self.suffixes) and Path(live_name).suffix.lower() in self.suffixes
            if not self.mkdir_open and not is_file_name and self._valid_new_folder(live_name):
                self.name = ""
                self._create_and_enter(live_name)
            else:
                self.mkdir_open = not self.mkdir_open
                if self.mkdir_open:
                    self.mkdir_name = self._default_new_folder_name()
                self.refresh()
            return True
        if action == "mkdir.name" and isinstance(event.value, str):
            self.mkdir_name = event.value.strip()
            self.refresh()
            return True
        if action == "mkdir.ok":
            live_mkdir = self._live_text(f"{self.id}.mkdir.name", self.mkdir_name)
            self._create_and_enter(live_mkdir)
            return True
        if action == "mkdir.cancel":
            self.mkdir_open = False
            self.mkdir_name = ""
            self.refresh()
            return True
        if action.startswith("dir."):
            index = int(action.removeprefix("dir."))
            if 0 <= index < len(self.dirs):
                self._enter_dir(self.dirs[index])
            return True
        if action.startswith("file."):
            index = int(action.removeprefix("file."))
            if self.mode != "directory" and 0 <= index < len(self.files):
                self.name = self.files[index].name
                self.refresh()
            return True
        if action == "name" and isinstance(event.value, str):
            self._handle_name_edit(event.value)
            return True
        if action == "filter" and isinstance(event.value, str):
            self.filter_index = 1 if event.value == "All files" else 0
            self.refresh()
            return True
        if action == "hidden":
            self.show_hidden = bool(event.value)
            self.refresh()
            return True
        if action == "cancel":
            screen.close_window(self)
            return Event(screen.id, self.id, None)
        if action == "ok":
            if self.can_confirm:
                chosen = str(self.chosen_path())
                screen.close_window(self)
                return Event(screen.id, self.id, chosen)
            return True
        return False
