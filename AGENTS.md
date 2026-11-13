# AGENTS.md

Guidance for coding agents working in this repository.

`rayscreen` is a Python 3.13 library of composable screens, windows, and widgets built on raygui and
raylib. The distribution and import package are both named `rayscreen`; the demo command is
`rayscreen-demo`. The source code is GPL-3.0-or-later.

This is a single uv package, not a workspace. The root `pyproject.toml` holds the project metadata,
runtime and development dependencies, uv build configuration, and pytest and ruff configuration. Run
commands from the repository root. Keep the package independently buildable and installable: do not add
dependencies on another repository or on files outside this package.

## Git operations

Do not run state-changing git operations without asking the user first. This includes commits, pushes,
stash, checkout, restore, reset, apply, merge, and similar operations that rewrite the working tree or
index. Read-only git commands such as `status`, `diff`, `log`, and `show` are fine.

## Commands

```sh
uv sync                                                        # install the package and dev dependencies
uv run pytest -q                                               # headless test suite
uv run ruff check .                                            # lint checks
uv run rayscreen-demo                                          # interactive scene launcher
uv run rayscreen-demo --screen gallery                         # open one demo scene
uv run rayscreen-demo --screen gallery --screenshot out.png    # save a visual check
uv run rayscreen-demo --screen tooltip --mouse 500,350          # hold the pointer for a screenshot
uv run rayscreen-demo --screen nav --focus gender.prev          # start with the focus ring on a widget
uv build                                                       # build source and wheel distributions
```

The demo's `--size W,H` sets the window size. Use `--screen NAME --screenshot PATH` for repeatable
visual checks, `--mouse X,Y` when a scene needs a particular pointer position, and `--focus ID` when it needs
the keyboard or gamepad focus on a widget (the `nav` scene then shows where each move goes from it).

## Layout

The import package is in `src/rayscreen/`:

- `__init__.py`: the public API re-exports. Keep these exports deliberate and consistent with the README.
- `specs.py`: widget and container specifications used to build a screen's tree, plus shared size
  metrics (`ROW`, `GAP`, `PAD`, ...). This module has no raylib dependency.
- `geometry.py`: rectangles and placement geometry shared by layout and drawing.
- `layout.py`: the `measure`/`arrange` passes and text layout. Text width is injected, so these passes
  are testable without raylib or a window.
- `screen.py`: `Screen`, `Window`, `Event`, and the `ScreenManager` stack
  (`push`/`pop`/`replace`/`reset`). Overlay screens let the screen below draw dimmed and locked. A
  screen's `hover` and `menu` hooks provide tooltips and context menus for application content.
- `state.py`: `UiState`, holding cross-frame interaction state by widget ID: text editing, open
  dropdowns and menus, scroll offsets, split positions, focus, and picture dragging.
- `navigation.py`: keyboard/gamepad-style navigation through `Nav`. Focus movement along the tree's rows and
  columns, dropdown and menu navigation, slider adjustments, and scrolling focused widgets into view are
  independent of raylib input handling. A focused window sees the navigation first through `Window.navigate`.
- `draw.py`: `frame(manager, theme)`, the per-frame walk that calls raygui and returns events no screen
  consumed. It also owns pointer routing, locking rules, overlays, popups, drag and drop, and the
  `mouse_free` check for application content beneath the UI.
- `theme.py`: light and dark colours, text sizes, the bundled font, and raygui style application.
  `Theme.dark_theme()` creates a dark theme; `set_dark` switches an existing theme at runtime.
- `icons.py`: additional icons drawn into free raygui icon slots (250 to 255, all used now).
- `display.py`: `HIGHDPI` for display scaling and `follow_wayland_mouse` for the raylib 6.0 Wayland
  pointer workaround. New application loops should account for both where applicable.
- `data.py`: `data_tree`, which turns plain nested data into specification trees.
- `file_window.py`: modal file and directory selection through `FileWindow`.
- `keyboard_window.py`: the modal on-screen keyboard `KeyboardWindow`, for typing with a gamepad.
- `demo/`: the `rayscreen-demo` checking harness and its scenes. Demo code may use the public or
  internal API, but must not introduce runtime dependencies beyond those declared in `pyproject.toml`.
- `assets/`: package data loaded by rayscreen. The default monogram font lives here so installed wheels
  need no external assets directory. Keep bundled asset notices in `THIRD_PARTY_NOTICES.md` current.

Tests are in `tests/`. They run without opening a window; preserve that property for specification,
layout, state, navigation, event-routing, and geometry tests. Generated environments, caches, build
output, screenshots, and demo output belong in ignored locations, not in source control.

## Architecture and conventions

- **Application ownership.** The application owns its model, window, frame loop, custom rendering, and
  event routing. rayscreen borrows control for one frame through `frame` and returns unconsumed events.
  Do not move the application's main loop into the library.
- **Headless core.** Keep widget specifications, measuring, arrangement, screen navigation, and input
  geometry independent of an open raylib window. Inject text measurement where needed rather than
  adding raylib calls to headless modules.
- **Coordinates and time.** UI positions and dimensions are in raylib window units, normally pixels;
  frame deltas and tooltip delays are in seconds. Use the shared layout metrics instead of scattering
  duplicate constants.
- **raylib.** Keep GL and GPU-resource calls on the main thread. Applications retain ownership of
  textures they place in `Picture` specs. Fonts loaded by a `Theme` are released with `theme.unload()`
  before the window closes.
- **Style.**
  - Match the surrounding code: short docstrings that explain why, comments sparingly, and names
    spelled out. Short names are appropriate for coordinates and indices in formulas.
  - Annotate every parameter, not only public ones. Name recurring shapes with a type alias or
    `NamedTuple`; use `Any` only for genuinely untyped values. Prefer PEP 695 type statements and
    generics, and use `TYPE_CHECKING` to break import cycles.
  - A long docstring starts with a summary line followed by bullets. Do not shorten one by removing its
    reasons.
  - Split a long function into named steps only where each step has a clear name and input. A helper
    used once is worthwhile when its name explains the step, not when it merely forwards many locals.
  - Search for an existing helper before writing a private one; do not duplicate it in another module.
  - Catch the narrowest exception. Every broad exception handler needs a comment explaining why.
  - Prefer a clear loop to a clever one-liner.
  - Keep lines readable. Ruff's configured line limit is 180 characters.
  - Lint configuration is in `pyproject.toml`. The user runs linting themselves, so do not run lint
    fixes unasked.
- **Package data.** If bundled resources change, build both distributions and verify that the files are
  present in the wheel and source archive. A test that only uses the editable checkout is not enough to
  prove package data will survive installation.

## Checking work

Run `uv run pytest -q` after code changes. Keep headless tests genuinely headless.

For visual changes, use the demo to take a screenshot and inspect the image before calling the work
done:

```sh
uv run rayscreen-demo --screen NAME --screenshot out.png
```

Choose a scene that exercises the changed behaviour. Use `--mouse X,Y` for pointer-dependent states and
`--size W,H` when layout or resizing matters. Remove generated screenshots or leave them in an ignored
location.

Keep `README.md` consistent with user-visible behaviour, commands, public API, and architecture. Do not
refer to documentation, packages, commands, or assets that are not part of this repository.

## Changelog and version

Do not edit `CHANGELOG.md` or bump `version` in `pyproject.toml` by hand; the release workflow
(`.github/workflows/release.yml`) handles both when a pull request merges. The PR title's
`major: `/`minor: `/`patch: ` prefix drives the semantic-version bump — while the version is 0.x, minor
covers new features and breaking changes and patch covers fixes, refactors, and documentation — and the
changelog entry comes from the PR title and the PR body's bullet lines, dated at merge. The workflow
commits the result and tags `v<version>` on main.

Entries have this form:

```text
YEAR-MONTH-DAY, SEMANTIC-VERSION:
  - brief description of change 1
  - brief description of change 2
```

`scripts/release_bump.py` does the bookkeeping and is what to extend when the format changes.
