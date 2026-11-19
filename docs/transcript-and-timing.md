# Transcript markup and timing JSON

Transcript (plain text): `# Section name` starts a section; `*word*` marks emphasis;
blank lines separate paragraphs. A section named `Intro` is added automatically at the top
if the transcript doesn't start with one; duplicate section names are refused with a
message naming both lines. Word ids are `w<index>`, stable across re-parse and section
renames.

Timing JSON (aligner output): `{source, method, inputs, sections: {name: start_s},
words: [{id, word, start, end, confidence}]}` — the word-timing shape of the source
explainer project, extended with `id` and an `inputs` fingerprint (the freshness gate:
saving inputs recomputes it, and the "Add motion graphics" step stays disabled until it
matches). All generated animation and keep-out zones anchor to word ids / section names,
never seconds: re-attaching the VO re-aligns and only times change. No VO:
`method: "estimated (N wpm)"` from a configurable speaking rate.

## Scene-relative page timings and the AI stage

Generated scene pages expose `window.MP.timings` **scene-relative** (seconds into the
scene), `MP.anchors`, `MP.scene`/`MP.frame`/`MP.palette`/`MP.fonts`/`MP.zones`, and
`MP.at(ref)` which resolves a word id, a `#Section` name, or a number. AI scripts anchor to
those, so a re-take re-times everything automatically.

## SFX manifest fields (ai_graphics/manifest.json)

Each graphic entry may carry `"sfx": [{"file": "sfx/whoosh.wav", "offset": 0.0,
"gain_db": -3.0}]` — `file` relative inside `ai_graphics/` (.wav .aif .aiff .flac .mp3
.m4a), `offset` seconds (-5..30) from the graphic's anchor (word start or section start),
`gain_db` -60..12. Every file needs a line in `ai_graphics/sfx/LICENSES.md`
(`<file> — <source/author> — <licence>`); the menu never writes SFX. Validated by
`motion-pipeline --check-graphics <project>` (exit 0 ok / 1 problems / 3 project error).
