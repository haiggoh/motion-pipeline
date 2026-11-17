"""ai_layer.py — the AI-owned zone of a project: ai_graphics/ (0.5.0 Task 4d).

An AI (or a human) adds extra motion graphics ONLY here, declared in
ai_graphics/manifest.json:

  {"graphics": [
     {"id": "spark", "file": "spark.html", "anchor": {"word": "w12"},      "layer": "above"},
     {"id": "pulse", "file": "pulse.js",   "anchor": {"section": "Intro"}, "layer": "below"}]}

  id      unique, lowercase letters/digits/-/_
  file    a file inside ai_graphics/: .html (a fragment placed on the page) or .js (a script
          loaded after the page's own script; it can read window.MP.timings / MP.anchors)
  anchor  exactly ONE of {"word": <word id>} or {"section": <section name>} — never seconds,
          so a new voiceover take re-times the graphic automatically
  layer   "above" (default) or "below" the generated text

The menu never writes here and its files never reference it; the generator only READS it
(copies listed files into src/ai_graphics/ and wires them into the matching section page).
"""
import json
import os
import re

DIR = 'ai_graphics'
MANIFEST = os.path.join(DIR, 'manifest.json')
_ID = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')
LAYERS = ('above', 'below')


def load_manifest(project_dir, words):
    """Validated manifest entries ([] when there is no manifest). `words` = transcript model
    words (dicts with id + section) used to resolve word anchors to their section."""
    path = os.path.join(project_dir, MANIFEST)
    if not os.path.isfile(path):
        return []
    with open(path) as f:
        try:
            m = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f'{MANIFEST}: not valid JSON ({e})') from e
    if not isinstance(m, dict) or not isinstance(m.get('graphics'), list):
        raise ValueError(f'{MANIFEST}: want {{"graphics": [...]}}')
    sections = {w['section'] for w in words}
    word_section = {w['id']: w['section'] for w in words}
    seen, out = set(), []
    for g in m['graphics']:
        gid = g.get('id') if isinstance(g, dict) else None
        where = f'{MANIFEST} entry {gid!r}'
        if not isinstance(gid, str) or not _ID.match(gid):
            raise ValueError(f'{where}: id must be lowercase letters/digits/-/_')
        if gid in seen:
            raise ValueError(f'{where}: duplicate id')
        seen.add(gid)
        fname = g.get('file')
        if not isinstance(fname, str) or os.path.isabs(fname) or '..' in fname.split('/'):
            raise ValueError(f'{where}: file must be a relative path inside {DIR}/')
        if not fname.endswith(('.html', '.js')):
            raise ValueError(f'{where}: file {fname!r} must be .html or .js')
        if not os.path.isfile(os.path.join(project_dir, DIR, fname)):
            raise ValueError(f'{where}: file {fname!r} not found in {DIR}/')
        anchor = g.get('anchor')
        if not isinstance(anchor, dict) or len(anchor) != 1 or set(anchor) - {'word', 'section'}:
            raise ValueError(f'{where}: anchor must have exactly one of "word" or "section"')
        if 'word' in anchor:
            if anchor['word'] not in word_section:
                raise ValueError(f'{where}: unknown word id {anchor["word"]!r}')
            section, element = word_section[anchor['word']], f'el-{anchor["word"]}'
        else:
            if anchor['section'] not in sections:
                raise ValueError(f'{where}: unknown section {anchor["section"]!r}')
            section, element = anchor['section'], f'card-{anchor["section"]}'
        layer = g.get('layer', 'above')
        if layer not in LAYERS:
            raise ValueError(f'{where}: layer must be one of {list(LAYERS)}, got {layer!r}')
        # Task 15b (D4): optional per-graphic SFX cue list, validated here; timed in audio_mux
        sfx = g.get('sfx', [])
        if isinstance(sfx, dict):
            sfx = [sfx]  # a single object normalises to a one-item list
        if not isinstance(sfx, list):
            raise ValueError(f'{where}: sfx must be a list of cue objects')
        licences = _licence_files(project_dir)
        cues = []
        for ci, cue in enumerate(sfx):
            cwhere = f'{where} sfx cue {ci}'
            if not isinstance(cue, dict):
                raise ValueError(f'{cwhere}: cue must be an object')
            cf = cue.get('file')
            if not isinstance(cf, str) or os.path.isabs(cf) or '..' in cf.split('/'):
                raise ValueError(f'{cwhere}: file must be a relative path inside {DIR}/')
            if not cf.endswith(('.wav', '.aif', '.aiff', '.flac', '.mp3', '.m4a')):
                raise ValueError(f'{cwhere}: file {cf!r} must be .wav .aif .aiff .flac .mp3 .m4a')
            if not os.path.isfile(os.path.join(project_dir, DIR, cf)):
                raise ValueError(f'{cwhere}: file {cf!r} not found in {DIR}/')
            if cf not in licences:
                raise ValueError(f'{cwhere}: {cf!r} has no line in {DIR}/sfx/LICENSES.md '
                                 f'(<file> — <source/author> — <licence>)')
            off = cue.get('offset', 0.0)
            if not isinstance(off, (int, float)) or isinstance(off, bool) or not -5 <= off <= 30:
                raise ValueError(f'{cwhere}: offset must be -5..30 seconds, got {off!r}')
            gd = cue.get('gain_db', 0.0)
            if not isinstance(gd, (int, float)) or isinstance(gd, bool) or not -60 <= gd <= 12:
                raise ValueError(f'{cwhere}: gain_db must be -60..12, got {gd!r}')
            cues.append({'file': cf, 'offset': float(off), 'gain_db': float(gd)})
        out.append({'id': gid, 'file': fname, 'section': section, 'element': element,
                    'anchor': anchor, 'layer': layer, 'sfx': cues})
    return out


SFX_EXTS = ('.wav', '.aif', '.aiff', '.flac', '.mp3', '.m4a')


def _licence_files(project_dir):
    """File names listed in ai_graphics/sfx/LICENSES.md (one '<file> — <source> — <licence>' per line)."""
    path = os.path.join(project_dir, DIR, 'sfx', 'LICENSES.md')
    if not os.path.isfile(path):
        return set()
    out = set()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                out.add(line.split('—')[0].strip())
    return out
