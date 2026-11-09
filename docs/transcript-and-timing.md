# Transcript markup and timing JSON

Transcript (plain text): `# Section name` starts a section; `*word*` marks emphasis;
blank lines separate paragraphs. Word ids are `w<index>`, stable across re-parse and
section renames.

Timing JSON (aligner output): `{source, method, sections: {name: start_s},
words: [{id, word, start, end, confidence}]}` — the word-timing shape of the source
explainer project, extended with `id`. All generated animation and keep-out zones anchor
to word ids / section names, never seconds: re-attaching the VO re-aligns and only times
change. No VO: `method: "estimated (N wpm)"` from a configurable speaking rate.
