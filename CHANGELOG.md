# Changelog

## v0.5.3 — 2026-11-11

- test(ui): QC hardening of the 0.5.2 launch-UX tests after an independent out-of-family
  review (GLM 5.3 Flash dispatch, 2026-11-10, per the milestone-QC playbook): the nav row
  enabling after LOAD is now asserted (was create-only), the from-Home path is driven
  through the home menu's real wiring (was direct `push_screen`), and 'esc' on the launch
  screen is asserted alongside 'b' plus a screen-stack identity check (nothing sits behind
  the launch screen). Each reviewer-proposed mutation was applied in isolation and turned
  the suite RED, then restored. Fast suite 129 passed. No behaviour change. Commit 257020a.

## v0.5.2 — 2026-11-10

- feat(ui): the app now always launches in New / load project (step 0), not Home —
  every setting depends on a saved project (user 2026-11-10 12:44). On that launch
  screen the trailing nav row is disabled until a project is created/loaded and is
  labelled 'Home', not 'Back' (entered from Home later it is 'Back' again). Video
  format (aspect/fps/UHD) is set in the SAME create/load step, so the separate
  'Save format' action is gone. 'b'/esc on the launch screen no longer pops it.
  Tests: `tests/test_launch_project.py` (launch screen, gated+Home row,
  Back-from-home, b-inert at launch) + updated menu_ux/projects_root/format tests;
  fast suite 128 passed; mutation (gate removed) RED on the disabled assertion,
  restored GREEN. Commit b607861.

## v0.5.1 — 2026-11-10

- fix(ui): typing a bare hex colour (`ffffff`, no `#`) into a CI colour field crashed the
  whole menu with an unhandled `StyleValueError` (user report 2026-11-10 09:23 via
  `bin/motion-pipeline-dev`). Hex input is now canonicalised to `#rrggbb` (bare 6-hex
  accepted) for the swatch/H/S/L, and Save stores the canonical form in `scheme.json`;
  invalid input shows the visible empty swatch instead of crashing; `_set_swatch` only ever
  assigns a canonical colour, so no field value can crash the app. Tests:
  `tests/test_colours_hex_input.py` (RED with the exact 0.5.0 crash under mutation, GREEN
  after; fast suite 125 passed).

## v0.5.0 — 2026-11-10

Menu rebuilt around one shared csl-style action list after user testing of v0.4.1
(plan: `~/.claude/plans/2026-11-10-motion-pipeline-0.5.0-ui-fixes-plan.md`):

- hover/keyboard highlight recolours text like csl — the v0.4.x selectors
  (`.list-item:hover`) matched nothing in Textual 8.2.8; now `ListItem.-hovered`/`.-highlight`
- every submenu: numbered action rows `N) label`, `Back` last and never saving; main menu:
  blank-separated rows, plain `Quit` last, no Back
- ONE round frame on the visible field only (inputs + dropdowns' `SelectCurrent`), round
  blue when focused, rounded overlay when expanded
- colour editor: labelled rows, always-visible framed swatches, live hex + H/S/L sync,
  saved scheme prefilled on load
- colour variants as overlays (`variants/<name>.json` override only); generate renders the
  chosen variant
- projects live in a projects folder you choose once (`~/.config/motion-pipeline`), never
  inside the brew libexec (wiped on upgrade); fixes schemes nesting at `<project>/<name>/scheme.json`
- modular project layout: menu-owned files stay pristine, foreign keys refused by name;
  AI graphics declared in `ai_graphics/manifest.json`; generated per-project `AGENTS.md`
- Finder drag-and-drop into path fields (paste routing, `My\ Folder` / `file://` decoding,
  exists/not-found marker)
- Background test and full render run the REAL pipeline via `render_cli`; Cancel stops the
  process; failures name the exit code + reason; in-terminal frame preview
- video format on the project screen (step 0): aspect 16:9/9:16/1:1/4:5, fps 25/30/50/60,
  UHD (16:9 only) — for new projects and via "Save format" on the current project
- `bin/motion-pipeline-dev` runs the menu from a repo checkout (see README)
- tests are delivery-level (computed styles, on-screen regions, disk bytes, executed
  commands) with mutation checks; the e2e chroma gate now samples after the section card

Manual check (not automatable, left to a human): a real Finder drag-and-drop into a path
field in Terminal.app.

## v0.4.1 — 2026-11-09

Regression fixes for v0.4.0 (caught by user testing, reproduced with screenshot/region
tests, not just widget-existence checks):
- colour editor laid out vertically and compact, so swatch + hex + H/S/L fields all
  fit in a 100-column terminal (they were rendered off-screen before)
- hover highlight uses the class selector Textual actually applies — text recolours,
  no more filled block
- Homebrew launcher installs ALL pyproject dependencies (was a hardcoded subset;
  the font menu crashed with ModuleNotFoundError: PIL)

## v0.4.0 — 2026-11-09

Menu UX iteration (user-tested):
- hover highlights like csl (soft-blue text on hover + keyboard highlight, never a filled block)
- rounded `ansi_bright_black` frames on the text fields (inputs + dropdowns) only, not the window
- visible "0 - Back to main menu (no save)" button at the top of every submenu (b/esc/q keys too)
- home menu items separated by an empty line
- new step 0: create or load the project directory; everything entered afterwards is stored there
- CI colours: live swatch per colour + separate H/S/L fields, two-way synced with the hex field
- font menu: live search over all system-installed fonts (133 families); choosing a system font
  copies it into the project's gitignored fonts/ with a licence warning; bundled OFL first

## v0.3.0 — 2026-11-09

Custom paths + output affordances (user requests): every submenu that asks for
files or writes output has a path field (drag a file/folder from Finder into the
terminal input to paste its path); render and background-test screens take a
custom output directory (`render_scene.sh --out DIR`) and on completion show the
output directory as a clickable OSC-8 `file://` link (cmd+click opens Finder) plus
an "Open output in Finder" button. The background test render now shows the
rendered test frame inline in the terminal below the buttons (ANSI half-block image).

## v0.2.0 — 2026-11-09

Menu UX (user-tested feedback): csl-style terminal-native theme (ansi_default surfaces,
rounded `ansi_bright_black` panels, text-only highlights) and a visible
"Back to main menu (no save)" action on every submenu plus b/esc/q keys.
Also: `python -m motion_pipeline` launches the menu from the CLI.

## v0.1.3 — 2026-11-09

`__version__` drifted from pyproject (brew run printed 0.1.0 on a 0.1.2 install) —
bumped and pinned with a test asserting the two agree.

## v0.1.2 — 2026-11-09

Homebrew launcher fix (caught by `brew install` + first run): python@3.14 is keg-only,
so the wrapper must call `python3.14`, and it now runs the shipped package via PYTHONPATH
instead of pip-installing it (avoids requiring the uv_build backend at install time).
Also wires `python -m motion_pipeline` to launch the interactive menu.

## v0.1.1 — 2026-11-09

Fix-forward from dogfooding the v0.1.0 tarball: de-brand the changelog (the asset
audit gate flagged the source-project name) and add pytest-asyncio to the dev extra
(fresh venvs errored on the TUI tests without it).

## v0.1.0 — 2026-11-09

First public release of the reusable, publishable kinetic-typography render pipeline
with a no-code project menu (extracted from a client explainer project's pipeline).

- Textual menu (steps 1–6): CI colours (OKLab-derived palette, contrast floors, light/dark
  schemes, variants), font family + role mapping (bundled OFL; client fonts gitignored with
  licence warning), timed keep-out zones, background test, transcript+VO inputs, render —
  long jobs run as workers with progress and cancellation.
- Deterministic offline VO aligner (DE/EN) producing word-level timing JSON with stable word
  ids; speaking-rate fallback when no VO. Transcript markup: `# Section`, `*emphasis*`.
- Kinetic-typography generator: masked slide-up reveals on word onsets, emphasis weights,
  section cards, per-aspect layout (16:9/9:16/1:1/4:5, 25–60 fps, optional UHD), zone
  routing; AI graphics layer isolated in `ai_graphics/` with stable element ids.
- 10-bit render backend: lossless RGB capture -> FFV1 `bgr0` intermediates -> a single BT.709
  `yuv422p10le` conversion (no chroma staircase; gate measured 1.0–1.9 vs the old 8-bit
  pipeline's 5.3–6.2 on gradient strips).
- Gates: portability (incl. `--help`/exit-2 contracts, intermediate resume refusal),
  chroma staircase, keep-out zones, font gate, publication asset audit; pytest suite with a
  real end-to-end render test.
- Sample project (globe opening, neutral copy) and docs.
