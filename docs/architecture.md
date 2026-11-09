# Architecture

```
motion_pipeline/
  scheme.py        scheme JSON -> Palette via OKLab derivation + contrast floors
  fonts.py         bundled OFL faces, role map, font gate, licence flags
  background.py    generates browser-side JS for the smooth gradient (colours from the scheme)
  transcript.py    plain-text markup (# sections, *emphasis*) -> words with stable ids w<i>
  align.py         deterministic offline aligner -> timing JSON (G5 shape + word ids)
  generate.py      scenes: layout in Python, GSAP reveals anchored to word ids, element_ids.json
  project.py       project.json model + loud validation
  tui/             Textual menu: colours, fonts, zones, background test, inputs, render (workers)
  graphics/        globe.js + land-110m.js (Natural Earth PD) — optional project graphic
tools/
  env.sh           pinned toolchain (node 24.19.0, hyperframes 0.8.31, chrome-headless-shell 156)
  render_scene.sh  generic 10-bit backend: png-sequence -> FFV1 bgr0 -> one bt709 10-bit master
  render_info.py   per-render info incl. intermediate=ffv1-bgr0 resume refusal (exit 4)
  check_chroma_steps.py / check_zone.py / audit_assets.py / test_portability.sh   gates
```

Data flow: project.json + scheme.json + transcript.txt (+ VO) -> transcript_model.json +
timing.json -> generate -> src/scene_*.html -> render_scene.sh -> renders/<variant>/*.mp4.
The menu's background test and the full render call the same render_scene.sh path.
