"""Headless tests for `FilesScreen` in `rayscreen.demo`."""

import json
from pathlib import Path

import pyray as rl

from rayscreen import Button, Event, FileWindow, Label, ScreenManager, dispatch
from rayscreen.demo.__main__ import SCENES
from rayscreen.demo.screens import BUNDLE_FILES, FilesScreen, MainScreen, ScenesScreen, SettingsScreen


def test_scenes_screen_has_a_button_for_every_demo_scene():
    manager = ScreenManager()
    scenes = ScenesScreen(manager)
    manager.push(scenes)
    for name in SCENES:
        if name == "scenes":
            continue
        assert isinstance(scenes.find(f"scene.{name}"), Button)
    assert dispatch(scenes, [Event("scenes", "scene.settings", None)]) == []
    assert isinstance(manager.top, SettingsScreen)
    assert dispatch(manager.top, [Event("settings", "back", None)]) == []
    assert manager.top is scenes


def _write_png(path: Path, width: int = 48, height: int = 32) -> Path:
    image = rl.gen_image_color(width, height, rl.Color(80, 140, 200, 255))
    rl.export_image(image, str(path))
    rl.unload_image(image)
    return path


def test_main_screen_opens_files_screen_and_pops_back():
    manager = ScreenManager()
    main = MainScreen(manager)
    manager.push(main)
    assert dispatch(main, [Event("main", "files", None)]) == []
    assert isinstance(manager.top, FilesScreen)
    files = manager.top
    assert dispatch(files, [Event("files", "back", None)]) == []
    assert manager.top is main
    files.unload()


def test_files_screen_loads_png_and_saves_directory_bundle(tmp_path: Path):
    png_dir = tmp_path / "images"
    png_dir.mkdir()
    _write_png(png_dir / "banner.png", width=64, height=40)
    export_dir = tmp_path / "exported_bundle"

    manager = ScreenManager()
    screen = FilesScreen(manager, image_path=png_dir, export_dir=export_dir)
    manager.push(screen)
    assert screen.image_size == (256, 256)

    # Open the Load PNG FileWindow, select banner.png, and confirm with Load
    assert dispatch(screen, [Event("files", "files.open-png", None)]) == []
    assert isinstance(screen.window, FileWindow) and screen.window.id == "files.load"
    assert [f.name for f in screen.window.files] == ["banner.png"]

    assert dispatch(screen, [Event("files", "files.load.file.0", True)]) == []
    assert dispatch(screen, [Event("files", "files.load.ok", None)]) == []
    assert screen.window is None
    assert screen.image_name == "banner.png"
    assert screen.image_size == (64, 40)
    status = screen.find("files.status")
    assert isinstance(status, Label) and status.tone == "ok"

    # Open the Save directory FileWindow and confirm to write preview.png, manifest.json, readme.txt
    assert dispatch(screen, [Event("files", "files.save-dir", None)]) == []
    assert isinstance(screen.window, FileWindow) and screen.window.id == "files.save"
    assert screen.window.chosen_path() == export_dir.resolve()

    assert dispatch(screen, [Event("files", "files.save.ok", None)]) == []
    assert screen.window is None
    assert export_dir.is_dir()
    for name in BUNDLE_FILES:
        assert (export_dir / name).is_file() and (export_dir / name).stat().st_size > 0
    manifest = json.loads((export_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["width"] == 64 and manifest["height"] == 40
    assert manifest["files"] == list(BUNDLE_FILES)
    saved_dir_label = screen.find("files.saved.dir.v")
    assert isinstance(saved_dir_label, Label) and saved_dir_label.text == str(export_dir.resolve())
    screen.unload()


def test_files_screen_reports_error_on_invalid_png(tmp_path: Path):
    bad_png = tmp_path / "broken.png"
    bad_png.write_text("not a png", encoding="utf-8")

    manager = ScreenManager()
    screen = FilesScreen(manager, image_path=bad_png)
    manager.push(screen)

    assert dispatch(screen, [Event("files", "files.open-png", None)]) == []
    assert dispatch(screen, [Event("files", "files.load.ok", None)]) == []
    assert screen.window is None
    assert screen.image_size == (256, 256)
    status = screen.find("files.status")
    assert isinstance(status, Label) and status.tone == "error"
    screen.unload()
