2026-11-10, 0.42.5:
  - Add GitHub Actions checks on pull requests: title prefix (`major: `/`minor: `/`patch: `), Ruff lint, and the test suite
  - Add a merge-triggered release workflow that runs the tests, bumps the version from the PR title prefix,
    prepends the changelog entry (title plus PR-body bullets), refreshes `uv.lock`, and commits and tags
    `v<version>` on main

2026-11-10, 0.42.4:
  - Measure test coverage with pytest-cov; `uv run pytest` prints a per-file report with missing lines

2026-11-10, 0.42.3:
  - Add the pre-commit Ruff hook and its development dependency

2026-11-10, 0.42.2:
  - Add a README TODO for CI checks, PR-title-driven version increments, and automated releases

2026-11-10, 0.42.1:
  - Add captured demo scenes to the README and source distribution
  - Add standalone agent guidance and correct the bundled monogram font's attribution to CC0

2026-11-09, 0.42.0:
  - `Window.handle` and `dispatch`: open windows on the top screen get first chance at events before `Screen.handle`,
    consuming internal events (`True`) or replacing an action with the window's own completion event (`Event`)
  - `FileWindow` (`rayscreen.file_window`, plan 001-phase-2/029): modal file and directory browser supporting
    `mode="load_file"`, `"save_file"` and `"directory"`, with parent/home navigation, editable `cwd` and `name` boxes,
    folder creation, extension filtering, hidden-files toggle, human-readable file sizes (`format_size`) and
    left-aligned `Toggle(align="left")` file rows
  - `FilesScreen` in `r-rayscreen-demo` (`--screen files`, `files-load`, `files-save`): loads a `.png` image into a
    preview and writes a bundle of files (`preview.png`, `manifest.json`, `readme.txt`) into a chosen directory
  - `ScenesScreen` in `r-rayscreen-demo` (the default screen when started without `--screen`): grouped launcher buttons
    for every demo scene (`main`, `settings`, `load`, `game`, `quests`, `pause`, `dialog`, `minimized`, `tooltip`,
    `menu`, `gallery`, `drag`, `drag-held`, `chat`, `board`, `files`, `files-load`, `files-save`), returning to the
    launcher on `Back` or `Esc`

2026-11-08, 0.41.0:
  - In a `Row`, a weighted `Column` with a `width` keeps that width and fills the row's height (a pane of a fixed width
    whose scroll reaches the bottom); before, its weight made it take a share of the width

2026-11-08, 0.40.0:
  - Moving through a screen without the mouse reaches dropdowns, sliders and check boxes: activating a dropdown opens
    its list, whose choices then take up, down, activate and back (Esc closes an open list too); left and right move a
    focused slider by its new `step` (`navigation.slid`, `list_step`); activating a check box flips it

2026-11-07, 0.39.1:
  - raylib pinned to exactly 6.0.1.0 (it bundles raylib 6.1-dev), no longer at least it

2026-11-07, 0.39.0:
  - `Screen.pinned_tip`: a tooltip the app shows without the mouse, beside a point (what a gamepad points at in a
    game's world); the mouse's own tooltip, an open menu or a drag hide it

2026-11-07, 0.38.0:
  - The focused widget's tooltip shows beside it while the focus ring does: what the mouse resting on it would show
    (an item's details in a grid moved through with the keys or a pad)

2026-11-07, 0.37.0:
  - The nav reaches the window with the focus, modal or not (a game's inventory over the running world)
  - Pictures that do something take the focus: a `clickable` one is clicked, one with a `menu` opens it beside the
    picture (an item in a grid)
  - An open context menu takes the nav first: up and down its enabled items (`navigation.menu_step`, `OpenMenu.focused`),
    activating chooses one, back dismisses it, the focused item ringed

2026-11-07, 0.36.0:
  - Menus without the mouse (plan 001-phase-2/021): `Nav` (a move, a click, a back) passed to `frame`; the focus moves
    between enabled buttons and toggles by where they lie, clicks as the mouse does, closes a closeable modal window on
    back, and shows as a ring in the theme's accent until the mouse moves; widgets in a `Scroll` are placed where it
    shows them, and the focus's scroll moves to keep it in view (the ring shows only while it is)
  - `specs.children`, a node's direct children (`walk` uses it)

2026-11-06, 0.35.0:
  - `Button.invalid`: its border and text in the theme's error colour (a key bound twice), still clickable

2026-11-06, 0.34.0:
  - `rayscreen.display`: `HIGHDPI`, the flag every rayscreen app opens its window with, so under display scaling
    (150%) the layout and the mouse are in the same units; `follow_wayland_mouse`, called each frame, undoes raylib
    6.0's second division of Wayland's mouse by the scale (fixed in raylib's master)

2026-11-06, 0.33.0:
  - `Slider.enabled` (greyed, emitting nothing) and `Slider.tooltip`, as a dropdown's

2026-11-06, 0.32.0:
  - `Toggle.enabled` and `Dropdown.enabled`: greyed, emitting nothing (an option the environment fixes); `Dropdown.tooltip`
    (why it is disabled)

2026-11-06, 0.31.0:
  - `Progress.vertical` (fills from the bottom, `width` wide in a row), `Progress.colour`, `Progress.tooltip`
  - `Toggle.tooltip`, as a button's
  - `Panel.solid`: a backdrop panel the mouse over is the panel's, as over a filled one (a HUD's bar)
  - `Column.width`: in a row, a column with a width is that wide instead of taking a share
  - the gallery's "Bars" panel shows them

2026-11-02, 0.30.0:
  - `Board` (docs/plans/001-phase-2/007-equipment.md): a canvas of a fixed aspect ratio — a background picture, and
    children placed by their middle at fractions of it (`Placed`, a wrapper, not a node); it keeps its aspect inside
    what it is given, centred (`layout.board_rect`), and each child keeps its own size
  - `Picture.caption`: text wrapped inside the box while it has no texture (an empty equipment slot's name);
    `Picture.tint`: an RGBA the texture is drawn through (a blocked slot's dimmed picture); `Picture.accent`: the
    frame in the theme's new `accent` colour (the paperdoll's hands) instead of muted
  - `Theme.accent` (amber), in `dark_theme` and `set_dark` too
  - the demo's `board` scene (`r-rayscreen-demo --screen board`)

2026-11-02, 0.29.0:
  - `TextBox(submit=True)`, a chat's box: Enter emits the text, clears the box and keeps the focus; leaving it emits
    nothing and keeps a draft (`UiState.take_draft`, for a Send button)
  - `Scroll(follow=True)` stays at the bottom while its content grows, unless scrolled up (`UiState.follow`)
  - `Picture.width`: a picture's fixed width in a row
  - `Text.tooltip`, shown while the mouse rests on the text, as a label's
  - `data_tree(id, value)`: plain data (dicts, lists, strings, numbers, booleans, None) as nested key/value tables,
    keys muted, values toned by type, nesting indented by the keys' column, long strings wrapped (in the gallery)
  - the demo's `chat` scene (`r-rayscreen-demo --screen chat`)

2026-11-02, 0.28.0:
  - drag and drop between pictures (docs/plans/001-phase-2/003-inventory-grid.md): `Picture.drag` is what a picture
    carries when pressed and moved `DRAG_START` pixels (a press without moving is still a click); `Picture.drop` takes
    one. While a drag runs (`UiState.dragging`, a `Dragging`, on the screen's state so it crosses windows) everything
    draws locked, the source shows empty, the target under the mouse is outlined and the picture follows the mouse.
    Letting go emits the source's `Event` with a `Drop` value: what was dragged, the target's id or None, where, and
    whether over a window (none: onto the screen, a game's world). Esc cancels; a screen pushed over drops it
  - `release_drag` and `drop_target` are the release's rules, tested without a window
  - `Picture.menu`: a context menu opened by a right-click on the picture; `Picture.framed` outlines a picture with a
    texture too
  - `Grid.columns`: exactly that many columns, whatever the width
  - `Rect.contains` and `Rect.overlap`
  - the demo's `drag` scene (and `drag-held`, a drag kept going for a screenshot)

2026-11-01, 0.27.1:
  - a `Slider` no longer emits its own value on its first frame: the change is judged against the value as raygui's
    32-bit float holds it, not the spec's double (a tool's sliders marked a fresh face as edited)

2026-10-30, 0.27.0:
  - `theme.FONT` is an `assetlib` `Asset` (`fonts/monogram/monogram-extended.ttf` in the shared root `assets/`,
    plan 027); the Kenney and Waste No Space UI art moved to `assets/ui/`, their zips to `assets-raw/ui/`

2026-10-30, 0.26.0:
  - for the game's debug inspector (plan 026):
  - `keyboard_free(manager)`: False while a text box of the visible screens or their windows is being typed in
  - `Table.stretch`: the last column takes all the width the others leave, so text boxes beside names fill the row
  - `Window(menu=...)`: a window's context menu, opened by a right-click on the window away from its widgets
  - `UiState.sliding`: the `Slider` the mouse holds, until the button is let go, so an app can leave its range
    alone meanwhile; `Slider(format="")` shows no value beside the bar

2026-10-30, 0.25.0:
  - for the game's screens (plan 025):
  - `Panel.backdrop`: a see-through fill in the theme's background colour (0 to 1), with no lines when
    untitled, for a HUD's text over a game's world; the mouse over it stays free
  - `Window(backdrop=False)`: a borderless window that paints nothing of its own, so a round picture in it
    (a minimap) shows the screen through its transparent corners
  - `Panel.fit`: in a row, a panel as wide as its content (as a tooltip measures it) instead of taking a share
  - a placed window (`position` set) stays on the screen when the screen shrinks under it
  - the demo's game screen has a round compass in such a window, dragged anywhere, and its hint on a backdrop

2026-10-30, 0.24.0:
  - `Menu.info`: a spec tree drawn locked between a context menu's title and its items, at most `Menu.width` wide
    (what the thing right-clicked is, above what to do with it); `MenuSize.info` is its height
  - a context menu's items are no longer cut short ("Show the whole w..."): its width counts the 2 px raygui keeps
    clear each side of a button's text (`layout.BUTTON_INSET`, measured)

2026-10-30, 0.23.0:
  - for the world generator UI (plan 024), rayscreen's second user:
  - state tones: `Tone` adds `ok` (done), `warning` (out of date) and `info` (under way), for labels and spans,
    with light and dark colours in `Theme` (`set_dark` switches them too)
  - `Label.tooltip` and `Button.tooltip`, shown as a `Picture`'s is while the mouse rests on it (a field's
    description with descriptions hidden, what an icon's button does)
  - `Button.align`: "left" reads its text from the left, for a long form's section headers
  - `Label.elide`: a label too long for its width gives its start up to "…" (a path); `layout.elided`
  - the demo's gallery shows stage headers in each tone, a field's help as its name's tooltip and a rule's card

2026-10-29, 0.22.0:
  - formatted text: `Text`, a paragraph of `Span`s each in its own tone (`ink`, `muted`, `error`), wrapped as one
    flow (a word is not broken where its tone changes), with a hanging `indent`; `Table`, rows of cells in columns
    as wide as their widest cell, aligned per column, a short row's last cell spanning the rest, the last column
    shrinking (and wrapping) when it does not fit; `Separator`, a thin rule. `text_lines`, `table_columns` and
    `table_cells` in the layout; the demo's gallery shows them

2026-10-29, 0.21.0:
  - `Picture.tooltip`: a `Tooltip` shown while the mouse rests on the picture (unlocked, in the tree that has the
    mouse: the topmost window under it, or the screen's), in place of the screen's `hover` hook's; shown and
    dismissed by the same rules (its `key`, `theme.tooltip_delay`, a press hides it)

2026-10-29, 0.20.0:
  - `Split`: two children side by side, each the full height, with a bar between them that the mouse drags;
    `ratio` is the left's share, each side keeps its `minimum`. The dragged ratio is kept in the screen's
    `UiState.splits` by id, so it outlives `set_root`; releasing the bar emits `Event(screen, id, ratio)`. The
    mouse over the bar is not free, and while it is dragged the tree is locked (letting go over a button does not
    click it). `split_widths`, `split_bar`, `split_ratio` in the layout; the demo's gallery is split
  - `UiState.keep` forgets the splits of ids no longer in the tree

2026-10-29, 0.19.1:
  - fonts load Latin-1 and common punctuation (° ² × é – — ‘ ’ “ ” … − →) besides ASCII; raylib loads only
    ASCII by default and drew "?" for the rest (`theme.CODEPOINTS`)

2026-10-29, 0.19.0:
  - dark mode: `Theme.dark_theme()`, light text on dark grey with raygui's controls in its own dark
    style's colours, and `Theme.set_dark(dark)` to switch a theme in place at runtime (the screens keep
    drawing with it). `apply_style` now starts from raygui's default style, so switching back restores
    light exactly (a light theme draws as before); raygui's reset would unload the theme's font, so it
    is handed raygui's own first. `Theme.title_ink` (the focused window's title) and `Theme.raygui`
    (raygui DEFAULT properties) carry the difference
  - `Button.width`: a fixed natural width in a row (a narrow "<" in a crowded row)
  - icons raygui lacks (`rayscreen.icons`): a sun and a moon, drawn from circles into raygui's free icon
    slots (250, 251; `SUN`, `MOON`) when the style is applied; `icon_text(icon)` is a button's text for one
  - `Swatch`: a square of colour beside a label, a legend's key (plan 022)

2026-10-29, 0.18.0:
  - widgets for the town generator UI (plan 022), its first user beyond the demo:
  - `Picture`: a texture shown in its rect (`fit` "contain" or "stretch", `flipped` for a render
    texture); the mouse over it is free (the screen's hooks and the app's pan and zoom work on it)
    unless it is `clickable`, when a press emits its event. `picture_rect` is where it draws
  - `Grid`: wraps its children into as many `cell`-wide columns as fit, row by row (`grid_columns`)
  - problems on widgets: `Label.tone` ("ink", "muted", "error") replaces `Label.muted` (breaking:
    `muted=True` is now `tone="muted"`); `TextBox.invalid` draws the box's border in the theme's new
    `error` colour
  - `enabled` on `TextBox` and `CheckBox`: greyed, and not editable or checkable
  - `Screen.set_root(root)` and `Window.set_root(root)` replace the tree, keeping the interaction
    state (the box being edited and what was typed, scroll offsets, an open list) of the ids still
    in it (`UiState.keep`)
  - a `Row`'s weighted children fill its height too, so two columns side by side can each fill a
    window (a row given only its natural height lays out as before)
  - demo: a `gallery` scene with a picture, a box with a problem, disabled widgets and a grid of
    clickable thumbnails

2026-10-29, 0.17.0:
  - tooltips (plan 021): `Screen.hover(x, y)` returns a `Tooltip` (a key and any spec tree;
    `Tooltip.text(key, title, *lines)`) for what is under the mouse on the screen itself (the game's
    world); it shows beside the cursor after `Theme.tooltip_delay` (0.3 s) on the same key, kept on
    screen, and hides the frame the key changes or goes, or on a press
  - context menus: `Screen.menu(x, y)` returns a `Menu` of `MenuItem`s (greyed when not `enabled`)
    for a right-click there, or `Screen.open_menu` opens one from code; a choice emits
    `Event(screen, menu.id, item.id, target=menu.target)`, a press outside or Esc dismisses it with
    value None, and a right-click elsewhere moves it. `Event` gains `target` (default None)
  - who owns the mouse: `mouse_free(manager, screen, theme)` is True when the mouse is over the
    screen itself (not a window, a widget, a scroll, a filled panel or a popup), the rule the hooks
    are asked under, for the game to check before acting on a click; `ScreenManager.mouse_used`
    says whether rayscreen spent this frame's press
  - a popup list's choices (the open dropdown's, a context menu's) read from the left, as the
    dropdown's own text does
  - demo: a villager, a chest and a minimap on the fake game's field, with tooltips and menus;
    `tooltip` and `menu` scenes and `--mouse X,Y`

2026-10-29, 0.16.1:
  - README: "A game on rayscreen" — how a game sits under its screens (it keeps its loop and its 3D
    rendering, rayscreen draws the UI over it), with diagrams of one frame, the draw layers, the
    screen stack and pausing

2026-10-29, 0.16.0:
  - window focus: one window of a screen at a time has the focus (`Screen.focus`, None for the
    screen itself), and Esc closes the focused window instead of the topmost one. Opening a window
    focuses it (`open(window, focus=False)` opens one in the background); a click focuses and raises
    the window under the mouse, or gives the focus back to the screen outside every window; closing
    the focused window hands the focus back to what had it before. A modal window keeps the focus
    while it is up. `Screen.focus_window(window)` sets it from code
  - the focused window's title bar is drawn in raygui's focused colours, the others in the normal
    grey
  - `ScreenManager.esc_used`: True in a frame whose Esc rayscreen spent (dropping what was typed,
    closing the focused window), so the app's own Esc handling can skip it
  - a window closed by its own close button no longer upsets the loop drawing the screen's windows
  - the demo: the quest log opens in the background, so Esc on the game screen pauses until the
    log is clicked; the demo's Esc check uses `esc_used`

2026-10-29, 0.15.0:
  - the theme's font is monogram (`font_path`, default the bundled `monogram-extended.ttf`), loaded
    once per size drawn with no smoothing instead of raygui's 10 px font scaled; `Theme.font(size)`
    and `Theme.unload()`. The `font` field is gone, and letters are no longer spaced 1 px apart
    (`spacing`, default 0)
  - one colour scale: raygui's controls write in the theme's `ink`, and group box lines and titles
    in its `muted` grey
  - `Label(muted=True)` for secondary text, `Button(enabled=False)` greys a button that emits
    nothing, `Slider(format=...)` for the value beside the bar, `Fill(weight=0, size=N)` a fixed gap
  - a dropdown reads its choice from the left with the arrow on the right; its open list opens on
    the side with more room and is cut, with a last "..." row, when it does not fit
  - a minimizable window's title-bar button shows collapse (up) when open and expand (down) when
    minimized, no longer the dropdown's down arrow
  - the demo: Settings keeps its heading and Back button out of the scroll and puts toggles and the
    dropdown beside their names; quest descriptions are indented and muted; Load is greyed until a
    save is picked; the HUD and the pause menu are filled panels

2026-10-29, 0.14.0:
  - breaking: an unweighted child of a `Row` with a natural width (a label, button, toggle, check
    box or dropdown) gets that width instead of an equal share, as the `specs` docstring already
    said ("0: just its natural size"); weighted children, and unweighted ones with no natural width,
    share the rest. Give buttons `weight=1` for equal shares. Natural widths that do not fit shrink
    in proportion
  - `natural_width(node, measure_text)`, and the `ICON` and `MIN_BUTTON` metrics
  - the demo's HUD labels take their natural width and the bar the rest

2026-10-29, 0.13.0:
  - a `Panel`'s title costs half a text line (the half raygui draws above the box's top line)
    instead of a whole row below it: no gap between the title and the content, and a titled panel
    stacked under another no longer has its title over the other's bottom border
  - `Panel(fill=True)` paints the panel with the theme's new `panel` colour (the demo's pause menu)
  - `Scroll(pad=PAD)` keeps the content off the scroll's border; the default pads every scroll

2026-10-29, 0.12.1:
  - a framed window no longer draws a second, empty title bar over the top of its content (raygui's
    `GuiPanel` draws a header for any title that is not NULL, and "" is not NULL)
  - an untitled `Panel` no longer draws a stray tick in its top-left corner
  - minimizing a centred window keeps its title bar where it was, instead of re-centring the bar
  - an open dropdown shows an up arrow (it showed raygui's filled down arrow, icon 120)
  - list views are left-aligned, with padding

2026-10-29, 0.12.0:
  - a double-click on a minimizable window's title bar toggles it between minimized and open

2026-10-29, 0.11.0:
  - `Window(resizable=True)`: a grip in the bottom-right corner resizes the window (clamped to a
    minimum and to the screen, with the resize cursor while hovering); the size is remembered, and
    resizing a content-sized window fixes its size. A resize owns the mouse: a drag never starts
    from the grip and the content is locked mid-resize
  - the demo's quest log is resizable

2026-10-29, 0.10.1:
  - the README's "How it works" opens with a mermaid diagram of the frame (who calls whom, where
    state lives), and the scene list matches the demo

2026-10-29, 0.10.0:
  - a screen holds any number of windows: `open` stacks them (the last one is on top),
    `close_window()` removes the topmost or a given one, and `screen.window` is the topmost
  - `Window(modal=False)`: a floating window — no dim, no lock, no pause; the screen beneath is
    locked only while the mouse is over the window, so a click on it never reaches what lies under
    it. A modal window locks and dims everything below it, floating windows included
  - the demo's game screen floats a quest log beside the intro dialog: too small for its quests, so
    it scrolls

2026-10-29, 0.9.1:
  - fix: the demo disabled raylib's built-in exit key, so Esc opens the pause menu instead of
    closing the window; the README notes apps should do the same

2026-10-28, 0.9.0:
  - `Window(pauses=...)`: a pausing window freezes what runs behind it — its own screen and every
    screen below skip their `update` while it is up (they still draw, locked and dimmed); a
    minimized window pauses nothing
  - the demo's intro and quit windows pause the game behind them (the HP bar stops)

2026-10-28, 0.8.0:
  - `Window(borderless=...)`: a borderless window drops the frame (title bar, buttons, border) and
    draws just its background; a draggable one is dragged by clicking anywhere inside it that is not
    a widget, so its controls keep their clicks. `minimizable` has no effect on a borderless window;
    `closeable` still governs Esc
  - the demo: the intro window is borderless, the quit window is minimizable

2026-10-28, 0.7.0:
  - `Window(minimizable=..., closeable=...)`: a minimizable window gets a title-bar button that
    collapses it to the bar and back (the screen stays locked but is no longer dimmed, so it can be
    peeked at); a non-closeable window has no close button and Esc does not close it
  - the window frame is composed from parts (status bar, buttons, panel) instead of raygui's
    `GuiWindowBox`, which always shows a close button; a covered screen's window is now locked too
  - the demo: the intro window is minimizable, the quit window is not closeable, and a "minimized"
    scene shows the collapsed state

2026-10-28, 0.6.0:
  - windows can be dragged by their title bar (the position is remembered, clamped on screen;
    `draggable=False` fixes one in place)
  - fix: a `Scroll` whose content fits inflated its child to the bounds height, but raygui's view is
    the bounds minus the border, so the bottom row ended half outside the view and locked (the demo
    settings' Back button did not respond); the child now inflates to the bounds minus the border
  - the demo's game screen opens with a floating window (a wrapped label and a Continue button)

2026-10-28, 0.5.0:
  - `Window`: a centred modal panel inside a screen, sized to its content or a given size, with a
    close button and an Esc shortcut; while open, the tree beneath is locked and dimmed
  - `Scroll`: a scrollable container whose content draws scissored to its view (nodes outside are
    skipped, nodes half in view are locked); the demo's dialog scene exercises windows

2026-10-28, 0.4.0:
  - the widget set: `Toggle`, `CheckBox`, `Slider` (label and value drawn inside its rect: raygui
    draws a slider's texts outside its bounds), `TextBox` (commits when the user leaves the box,
    Esc drops the edit), `Dropdown` (an open list that locks the tree beneath), `Progress`,
    `ListView`
  - `UiState` keeps what crosses frames, keyed by widget id: the box being edited and its buffer,
    the open list, scroll offsets

2026-10-28, 0.3.0:
  - `Screen`, `Window`, `Event` and the `ScreenManager` stack (push/pop/replace/reset; an `overlay`
    screen lets the screen below draw, dimmed and locked)
  - `Theme` (colours, text sizes, optional font) and `apply_style`
  - `draw.frame`: the per-frame walk that calls raygui and returns the events no screen consumed
  - `r-rayscreen-demo`: main menu, settings, load-game and game scenes navigating via the stack

2026-10-28, 0.2.0:
  - the layout core: widget and container specs (`Label`, `Button`, `Column`, `Row`, `Panel`,
    `Fill`) with no raylib, and the `measure`/`arrange` passes with text width injected, tested
    without a window

2026-10-28, 0.1.0:
  - new package: screens and widgets on top of raygui, to simulate "windows"/screens (main game screen, options screen, other widgets)
