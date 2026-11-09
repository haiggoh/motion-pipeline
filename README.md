# motion-pipeline

A reusable, publishable **kinetic-typography render pipeline** with a no-code project menu:
feed in your CI (a few colours + a font), attach a **transcript and optional voiceover**, and
get back a finished **10-bit video timed to the voiceover** — no code editing, no AI required
for the core. An AI session can add extra creative graphics on the generated project folder
afterwards (recommended: [free-agents](https://github.com/haiggoh/free-agents)).

## The two things it does best

1. **CI inputs, no code.** The Textual menu takes a few main colours (background dark,
   background glow, accent, text) and a font family; every other colour is derived in OKLab
   with enforced contrast floors. One colour scheme per project by default; a checkbox adds
   a second variant (and more). Bundled fonts are OFL-only (Montserrat, Inter); a client font
   can live in the project's gitignored `fonts/` with a licence warning — never committed.
2. **Voiceover timing workflow.** Transcript in (plain text: `# Section` headings, `*key
   words*`), VO audio optional. A deterministic, offline aligner (German + English) produces
   word-level timings; the text animation — masked slide-up reveals on each word's onset,
   dimming as the next lands, emphasis in a heavier weight, section heading cards — is
   generated and timed to those word ids, so a new VO take re-times everything automatically.
   Without VO, timings are estimated from a configurable speaking rate (preview quality).

## Smooth gradient backgrounds in 10-bit

No 8-bit or lossy step sits between capture and the master: the browser captures lossless
RGB (`--format png-sequence`), packed into **FFV1 `bgr0`** intermediates, and the master
encode's `scale=out_color_matrix=bt709:…:format=yuv422p10le` is the **only** RGB→YUV
conversion — true BT.709 10-bit 4:2:2 masters. Measured on the source project this pipeline
was extracted from: the old 8-bit-intermediate masters showed chroma staircases of 5.3–6.2
(10-bit codes, threshold 2.0) on gradient strips; the 10-bit pipeline renders them at
1.0–1.9 and passes the automated gate (`tools/check_chroma_steps.py`, wired into the suite).

## Output options

- Formats: **16:9, 9:16, 1:1, 4:5**; fps **25/30/50/60**; 16:9 also **UHD 3840×2160**.
  Resolution and fps are project settings, never constants. (hyperframes 0.8.31 renders at
  preset resolutions matching the composition aspect; 4:5 currently falls back to square —
  documented limitation.)
- Colourway variants per project (one by default, checkbox adds more).
- Masters: H.264 High 4:2:2, 10-bit `yuv422p10le`, per scene → `renders/<variant>/`.
- Timed keep-out zones (rectangle per aspect, anchored to transcript sections) keep text
  out of graphic areas; post-render gates: chroma staircase, zone, font, asset audit.

## What works out of the box vs what needs an AI model

Out of the box, zero AI: CI scheme, fonts, background, VO alignment, text animation,
rendering, gates. Needs an AI model (your own session, e.g. via
[free-agents](https://github.com/haiggoh/free-agents)): additional creative graphics at key
moments. They live in the project's `ai_graphics/` folder, which the generator never touches;
they can reference generated text only via the stable element ids in `src/element_ids.json`,
and everything time-based anchors to word ids / section names, not seconds.

## Quickstart

```bash
brew install fnm uv ffmpeg
fnm install 24.19.0
uv venv --python /opt/homebrew/bin/python3.11 .venv
uv pip install --python .venv/bin/python -e '.[dev]'
npm install                                   # pinned hyperframes 0.8.31
npx --yes @puppeteer/browsers install chrome-headless-shell@156.0.8078.4 --path ~/.cache/motion-pipeline/chrome
bash tools/test_portability.sh                 # == PORTABLE
.venv/bin/python -m pytest tests/ -q           # 57 passed (includes a real e2e render)
# new project from the sample:
cp -r samples/globe projects/my-globe
# then run the menu: .venv/bin/python -m motion_pipeline  (steps 1-6: colours, font, zones,
# background test, transcript+VO, render) — or drive it headless via tools/render_scene.sh
```

macOS first (Apple Silicon); Linux assumed. See `docs/` for architecture, the scheme
derivation rules, the transcript markup reference, and the timing-JSON reference.

## Licences

Our code Apache-2.0 (`LICENSE`); details and third-party notices in `NOTICES.md`
(HyperFrames Apache-2.0; GSAP 3.14.2 Standard No-Charge — its "no tools competing with
Webflow" clause was reviewed and the risk accepted for a small tool, 2026-11-08; bundled
fonts OFL; map data Natural Earth PD / world-atlas ISC). `tools/audit_assets.py` fails the
build if any tracked file matches client-asset patterns.
