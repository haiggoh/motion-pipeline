# Changelog

## [0.7.1] — 2026-11-22 — non-Homebrew fallbacks, crash fix, in-place loader, graphics route

- No Homebrew needed for the render toolchain: node and ffmpeg fall back to sha256-verified
  binaries in the app cache, and the launcher finds a python without Homebrew (tap PR #31)
- The speech engine self-installs on first launch without Homebrew (CLT source build with a
  Rosetta prebuilt fallback, sha256-pinned, atomic, resumable); `whisper-cpp` is no longer a
  hard formula dependency (tap PR #30)
- Crash fix: a late timing callback on a removed screen no longer crashes; the voiceover line
  also accepts `.aac`/`.ogg`
- Operations over ~100 ms show a loading animation where the content lands (first-run screen
  included); launch is faster (lazy screen imports, 24 h-cached toolchain probe)
- "Add motion graphics" leads with the Free-Agents route (dropdowns + launch button), Manual
  route as fallback; fonts-less projects render with the bundled Montserrat fallback (Save
  still gates strictly); pytest-xdist in the dev extras; the 3 real-render toolchain tests
  assert post-cleanup evidence

## [0.7.0] — 2026-11-22 — friendlier inputs, contrast fixer, font roles, zone map, transcript formats, automatic speech model

- CI colours: hex fields take only `0-9a-fA-F` (max 6, the `#` is a fixed dimmed label outside
  the field); `#fff` short form works; pasting `#FF6A00` is accepted whole, never truncated;
  H/S/L take digits only and refuse out-of-range values at input (H>360, S/L>100)
- Contrast failures show a red `!` on exactly the rows involved, name the pair
  (`text on background dark: 1.07:1 — needs at least 4.5:1`) and offer **Fix contrast**
  (smallest OKLab-lightness change that keeps BOTH pairs passing) plus
  **Save anyway (ignore contrast)**; the override is honoured by the renderer too
- Font menu: an "Apply to all roles" checkbox (default on) replaces the role dropdown; role
  rows are clickable and the picked row is highlighted; the inline preview is much larger
  (full width × remaining height, recomputed on resize) and the sharp preview window
  (Quick Look) updates live on every change
- Keep-out zones: a short explanation on top, a live box-drawn frame map that updates as you
  type the rect, and an overlay on the latest background-test frame
- Transcript line loads `.txt/.md/.rtf/.doc/.docx/.pdf` (docx maps real headings and bold
  runs; rtf/doc via textutil; pdf via pypdf — new dep); the voiceover line takes audio files
  (`.wav/.mp3/.m4a/.aac/.aif/.aiff/.flac/.ogg`, plus `.mov/.mp4`); after Save the status
  shows `N sections, M words`; language defaults to Auto-detect for new projects;
  with a voiceover attached, wpm becomes a read-only `measured N wpm` indicator
- Computing timings shows a spinner and a progress bar fed by stage lines from the
  prepare-only job (whisper's own progress included)
- The speech model installs itself on first launch (sha256-pinned, atomic, resumable with a
  Retry row on failure); `whisper-cpp` is a Homebrew dependency of the formula
- The brew launcher resyncs the per-user venv when the shipped dependency list changes
  (so upgrading to 0.7.0 installs pypdf into an existing venv)

## [0.6.4] — 2026-11-21 — standalone --render-test and PTY-test fixes (found by resuming the dogfood session)

- `--render-test` spawns `render_scene.sh` directly, so it never got `preflight()`'s
  toolchain PATH — standalone CLI render-tests exited 3 with "hyperframes not on PATH"
  while the menu path worked. It now reuses the preflight env (+ `MP_PYTHON`), guarded
  when the toolchain is absent. Guard test captures the subprocess env and asserts the
  hyperframes dir is on PATH (RED before, GREEN after).
- The PTY terminal-driver tests spawned their child with `cwd=tmp_path` and `-P` (no cwd
  on sys.path) and no `PYTHONPATH` — the child died on "No module named motion_pipeline",
  so BOTH discriminants (query suppressed on Apple Terminal / present elsewhere) read
  vacuously. The child env now carries the repo root; 7/7 PTY tests pass for real.
- Both surfaced while resuming the killed `sevenone-adf-test` dogfood session
  (93a52b75): its work (design gate, 2 graphics + CC0 SFX, final verification green) was
  re-verified against this build on the real spaced project path — `--check-graphics` OK,
  both render-tests exit 0, chroma gates pass, stills show the designed shapes.
- Gate: 316 passed, 7 printed env-skips, exit 0.

## [0.6.3] — 2026-11-21 — bug fixes from the 0.6.2 hands-on test

- No stray `p` on startup in Apple Terminal (the 2048 in-band-resize query is skipped there; PTY-tested, other terminals unchanged)
- Finder drops land in the field that accepts the file type — a `.wav` goes to the voiceover field even when the transcript field has focus; a multi-item drop uses the first item and says so in the field's frame
- No grey block behind the job logs anymore (terminal-native csl look on the background-test and render screens)
- Background test render no longer needs a transcript: it uses a built-in sample (or the transcript's first section) in a scratch copy, so your project's files stay untouched; step 4 no longer depends on step 5
- "Add motion graphics" says why it is greyed out ("needs saved timings (step 5)") and re-checks when you come back to the menu; computing timings reports success (`timings saved — N words, M sections, engine …`) or the named error
- Hidden Apple-private `.`-prefixed font families (e.g. `.SF NS`) in the font list
- A corrupt `project.json` is named in the UI (`error: project.json: …`) and Save refuses to overwrite it — never silently replaced by defaults
- The voiceover is decoded once when computing timings (was twice)
- Fixed a never-green test (`TimeRange.start` → `start_time`) that only skipped in CI

## [0.6.2] — 2026-11-19 — determinism lint in --check-graphics for AI scripts

- `motion-pipeline --check-graphics <project>` now also scans every `ai_graphics/`
  .js/.html file for nondeterministic calls — `requestAnimationFrame`, `setTimeout`,
  `setInterval`, `new Date`/`Date.now`, unseeded `Math.random`, and network calls
  (`fetch`/`XMLHttpRequest`/`WebSocket`/`sendBeacon`/dynamic `import(`) — listing each as
  `file:line` with exit 1 (problems listed). The renderer seeks frames, so these would
  render differently per frame; `MP.random(seed)` stays the allowed seeded path (covered by
  a no-false-positive test). Found by the Task 22 QC review; tests watched RED, the
  Math.random-rule-drop mutation went RED and was restored. Gate: 280 passed, 6 printed
  env-skips, exit 0.

## [0.6.1] — 2026-11-19 — M6: the shipped sample renders end to end; README/docs truthful

- **Sample as shipped (Task 18):** `samples/globe` now carries its own `project.json`
  (16:9, 25 fps, globe graphics, Montserrat role weights, Welcome keep-out zone) and
  `scheme.json`; the e2e test loads the sample AS COMMITTED and computes timings/pages via
  the real `--prepare-only` path; new `test_sample_loads_unmodified` validates the shipped
  files. The slow e2e's frame window and chroma-gate frame are derived from the sample's
  fps (the hardcoded 120-149/15 assumed the old 60 fps fixture — at 25 fps the trim was
  empty and the gate read past the master's end); the hyperframes skip now also checks the
  toolchain cache, so the real render gates on any machine with `--setup-render`.
- **README/docs truthful (Task 19):** steps 0-7 including step 6 "Add motion graphics"
  (menu-owned playbook, `--check-graphics`/`--render-test`, free-agents launcher); `.mov`
  masters with VO/SFX tracks, preview, FCP 7 XML for Premiere/DaVinci, opt-in joined
  master, bit-exact remux; toolchain via `--setup-render`; no hardcoded suite count; no
  "4:5 falls back to square". `docs/transcript-and-timing.md` documents the Intro
  auto-section, duplicate-name refusal, scene-relative `MP.timings` and the SFX manifest
  fields. New `tests/test_readme_claims.py` guards retired claims (absent) and every
  README flag (listed by the shipped `--help`) — both mutations watched RED, then reverted.
- Gate: 277 passed, 6 skipped (all printed env reasons), exit 0.

## [0.6.0] — 2026-11-18 — M1–M5: menu UX, fonts, render correctness, audio/Premiere/aligners, motion graphics

- **M1 — menu UX (Tasks 1–6):** zones screen crash fix + delete + select-to-edit + per-aspect
  zones + loud validation; inputs screen prefills every field, adds wpm/language/aligner, save
  keeps the VO; project screen step-0 picker (create refuses an existing dir, apply format,
  create from sample); menu chrome (nav gap, new nav labels, dimmed/red feedback lines); render
  screens (one job at a time, honest done/failed log line, wrapped log, right open target);
  dev/brew launcher hardened with `python -P` so a cwd package can no longer shadow the checkout.
- **M2 — fonts (Tasks 7–10):** font_index — recursive scan, real OS/2 weights, mtime/size cache;
  per-role font model with legacy migration and content-resolved client faces; role-by-role
  fonts screen with background scan; inline half-block preview + sharp Quick Look PNG.
- **M3 — render correctness (Tasks 11–14):** role faces embedded per page + font gate (exit 5);
  section-relative scene model (slug ids, registered paused timelines, next-line dimming, fit
  guard); zone + chroma + disk gates on every render; toolchain install-from-menu
  (`--setup-render`, `--dry-run`) with the node ≥ 22 rule.
- **M4 — audio/Premiere/aligners (Tasks 15–17):** .mov masters with VO+SFX tracks, opt-in joined
  full-length master, preview, bit-exact re-mux (video stream copied, never re-encoded); SFX cue
  declarations validated in the AI manifest; Premiere import via FCP 7 XML
  `<variant>_sequence.xml`; classical aligner (pause runs, syllable nuclei, DP assignment) plus
  an optional whisper.cpp engine snapped to the transcript.
- **M5 — Add motion graphics (Tasks 21–23):** inputs fingerprint + timings freshness gate, and
  step 5's Save now computes and saves the timings via `--prepare-only` (the step stays
  disabled until they are fresh); every scene page defines `window.MP` (timeline,
  timings, anchors, scene, frame, palette, fonts, zones, sfx, `at()`) BEFORE any ai_graphics
  script loads, with `mp_lib.js` helpers (enter/exit/drawOn/float/inZone/el/random — seeded
  mulberry32, no rAF/setTimeout/Date/unseeded random/network) and vendored DrawSVGPlugin 3.14.2
  (sha equals the P&G project copy); the menu-owned `MOTION_GRAPHICS_PLAYBOOK.md` renders live
  facts and regenerates on every visit/save; `motion-pipeline --check-graphics DIR` (exit 0/1/3)
  and `--render-test DIR --section NAME [--from S --to E] [--draft] [--dry-run]` render one
  scene span into `<project>/scratch/ai-test/`; the new step 6 offers open/reveal/copy(pbcopy)/
  check actions and — only when free-agents is detected — model + effort Selects (ladder
  resolved live: session prefs → dispatch preferences → inventory; trial/retired/no-key rows
  filtered) and "Start a free AI session" opening a NEW Terminal window via osascript with a
  shlex-quoted argv, link-form `--prompt`, explicit `--effort`, `FA_PRE_TRUST=1`.
- **Fixes:** `audio_mux.sfx_cues` resolves manifest anchors from the transcript model (aligner
  timing words drop `section` — generated pages crashed with KeyError on any manifest project);
  `--prepare-only` no longer requires `--mode` (the menu's real argv, caught during dogfood prep).
- **Quality:** outcome-shaped tests throughout (generated page bytes, node-executed page API
  incl. mulberry32 known vectors, real subprocess exit codes, frame luma in the slow render
  test), plus two test-hardening commits: render-log polling switched to real time (810c630,
  flaky under xdist CPU contention) and a CSS at-rule selector guard (fdde8e2); mutation
  discriminants (ordering, `MP.at`, dry-run, `--prompt`, version sort) watched RED then
  reverted; milestone QC via out-of-family dispatches (Playbook-milestone-qc-offload-test-
  proof), including one on THIS release's changelog and ship wiring. Full suite 270 passed,
  2 environmental skips.

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
