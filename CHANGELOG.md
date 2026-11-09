# Changelog

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
