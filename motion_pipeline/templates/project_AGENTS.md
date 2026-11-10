# AGENTS.md — how to change this motion-pipeline project safely

This file is written by the motion-pipeline menu every time the project is saved. Edits to it
are overwritten; it exists so that an AI (or a person) adding motion graphics never breaks the
parts the menu has to keep editing.

## The three zones — one owner each

| Zone | Files | Owner | Rule |
|---|---|---|---|
| **Menu-owned** | `project.json`, `scheme.json`, `variants/*.json`, `transcript.txt`, `timing.json`, `transcript_model.json`, `audio/`, `fonts/` | the motion-pipeline menu | **never** edit these by hand or by AI. The menu validates them strictly and refuses a file with keys it does not own. |
| **Generated** | `src/` (scene pages, `src/element_ids.json`, `src/ai_graphics/`) | the generator | **never** edit — rebuilt on every generate/render, changes are lost. |
| **AI-owned** | `ai_graphics/` | you | add your graphics here, and only here. The menu never writes to this folder. |

## Adding a graphic

1. Put the file in `ai_graphics/`: an `.html` fragment (placed on the page inside a full-frame,
   absolutely positioned layer) or a `.js` script (loaded after the page's own script).
2. Declare it in `ai_graphics/manifest.json`:

```json
{"graphics": [
  {"id": "spark", "file": "spark.html", "anchor": {"word": "w12"},      "layer": "above"},
  {"id": "pulse", "file": "pulse.js",   "anchor": {"section": "Intro"}, "layer": "below"}
]}
```

- `id`: unique, lowercase letters/digits/`-`/`_`.
- `anchor`: exactly ONE of `{"word": <word id>}` or `{"section": <section name>}` — never
  seconds. Word ids and section card ids are listed in `src/element_ids.json` (after a
  generate); a new voiceover take re-times everything anchored this way automatically.
- `layer`: `above` (default) or `below` the generated text.

3. In a script, read timing and anchors from `window.MP`:
   `MP.timings[<word id>] = {start, end}` (seconds into the scene) and
   `MP.anchors[<your id>] = {element, layer, start?}`; the anchored element is
   `document.getElementById(MP.anchors[<your id>].element)`.
4. Touch generated text ONLY through those published element ids. Never rely on other
   markup in `src/` — it may change with any release.

An invalid manifest entry stops the generator with a message naming the entry; nothing in the
menu-owned zone is touched by that failure.
