# MOTION GRAPHICS PLAYBOOK — {project_name}

This file is menu-owned: it is regenerated on every visit to the "Add motion graphics" step and
on every Save inputs. Do not hand-edit it — your changes would be overwritten. Read it first and
follow it exactly.

Project facts (live): frame {width}x{height} at {fps} fps, aspect {aspect}. Palette:
{palette_table}
Fonts per role: {fonts_table}

## 0 Start with questions

Before designing anything, ask the user with AskUserQuestion (multiple choice, recommended option
first): overall style (clean line-art / bold shapes / data-viz / iconographic), density (key
moments only / every section / continuous), which sections get graphics (multi-select from the
scene table below), colour use (palette accent only / full palette), SFX character (subtle UI
clicks and whooshes / cinematic hits / none) and loudness. Then summarise the plan and ask for a
go.

## 1 The three zones

The project uses three zones (see AGENTS.md): the text zone (generated text lives here), the
keep-out zones (graphics live here — the text avoids them), and the AI layer. Stay inside the
active keep-out zones listed below per scene.

## 2 Files and manifest

Add files ONLY inside `ai_graphics/`:
- `manifest.json` declares each graphic. Example entry (incl. SFX):
  ```json
  {"id": "intro-icon", "file": "intro.html", "anchor": {"section": "Intro"}, "layer": "above",
   "sfx": [{"file": "sfx/whoosh.wav", "offset": 0.0, "gain_db": -3.0}]}
  ```
- `file` must be a relative path inside `ai_graphics/` (.html fragment or .js script), and must
  exist. `anchor` is exactly one of `{"word": "<word id>"}` or `{"section": "<section name>"}` —
  never seconds. `layer` is `above` (default) or `below`. `sfx` is a list of cues (see section 7).

## 3 The page API + mp_lib

Every scene page defines `window.MP` BEFORE any ai_graphics script runs:
- `MP.tl` IS the scene's registered paused timeline — add your tweens to it, never create your own.
- `MP.at('w12')` = that word's scene-relative start (seconds); `MP.at('#Intro')` = section start;
  `MP.at(2.5)` = 2.5 s. `MP.at(ref, offset)` adds offset.
- `MP.timings`, `MP.anchors`, `MP.scene` ({name, slug, start, end, duration}), `MP.frame`
  ({W, H, fps, aspect}), `MP.palette` (hex per key), `MP.fonts` ({role: 'mp-<role>'}),
  `MP.zones` ([[x,y,w,h], ...] active zones of THIS scene), `MP.sfx` (read-only cue list).
- `MP.el(tag, style, parent, html)`, `MP.enter(el, ref, {d, y, ease})`, `MP.exit(el, ref, {d})`,
  `MP.drawOn(svgEl, ref, {d, ease})` (DrawSVG, vendored), `MP.float(el, fromRef, toRef, {amp, per})`,
  `MP.inZone(el, i)` (fills active zone i), `MP.random(seed)` (mulberry32).

Worked example — a line icon drawn on inside zone 0 at word `{example_word}`, exiting at the
section end, with an entrance whoosh and an exit tick:
```js
const icon = MP.el('svg', null, null, '<path d="M0 0 L 100 0" stroke="#fff"/>');
MP.inZone(icon, 0);
MP.drawOn(icon.querySelector('path'), '{example_word}', {d: 0.8});
MP.exit(icon, '#{example_section}', {d: 0.3});
```

## 4 Timing rules

Anchor to word ids or section names only (`MP.at`). A new voiceover take re-times everything
anchored this way automatically. A graphic lives inside the scene it is anchored to.

Scene table (scene, section, start, end, duration, first/last word id):
{scene_table}

Word ids live in `timing.json` (`words[].id`) and `src/element_ids.json` (published element ids).

## 5 Layout rules

Stay inside the active keep-out zones (listed per scene in the table above). Never cover generated
text. Stay inside the frame. Use `MP.palette` / `MP.fonts` — never literal client colours.

Active zones per scene: {zones_table}

## 6 Determinism rules

Never use `requestAnimationFrame`, `setTimeout`, `Date`, unseeded `Math.random` (use
`MP.random(seed)`), or the network — the renderer seeks frames, so anything time- or
random-dependent renders differently per frame. All tweens go on `MP.tl`.

## 7 Sound effects

One cue list per graphic (`sfx` in the manifest entry), timed to its visual beats (entrance /
emphasis / exit). WAV 48 kHz preferred. Peaks <= -6 dBFS; use `gain_db` to balance against the
voiceover. Only files the user supplied or with a licence that allows use (CC0 / licensed
library); every file gets its `ai_graphics/sfx/LICENSES.md` line (`<file> — <source/author> —
<licence>`). If the user has not supplied sound effects, find suitable ones on free sources via
web search (CC0 / public-domain libraries such as freesound.org's CC0 collection, Pixabay,
or Wikimedia Commons) rather than asking the user to provide them. Never generate or download
audio without the user's approval. Keep SFX off VO-critical words unless asked. The menu never
writes SFX.

## 8 Check your work

Run `motion-pipeline --check-graphics {project_dir}` — must exit 0. Then
`motion-pipeline --render-test {project_dir} --section <name> [--from S --to E]` renders that span
to `{project_dir}/scratch/ai-test/` — extract stills with
`ffmpeg -ss <t> -i <file> -frames:v 1 still.png` and LOOK at them. Never claim done without a
viewed still per graphic.

## 9 Done criteria + hand back

Tell the user to open the menu's Render step. Never edit menu-owned files (this playbook,
`AGENTS.md`, `project.json`), never render the masters yourself.

Current manifest entries: {manifest_entries}
