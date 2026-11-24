"""playbook.py — render the menu-owned MOTION_GRAPHICS_PLAYBOOK.md into a project with live
facts (Task 22). Regenerated on every visit to the step and every Save inputs — hand edits are
overwritten on purpose."""
import os

from . import project as project_mod
from .util import load_json, read_text

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates',
                        'motion_graphics_playbook.md')
OUT_NAME = 'MOTION_GRAPHICS_PLAYBOOK.md'


def write_playbook(project_dir):
    """Render the playbook into <project>/MOTION_GRAPHICS_PLAYBOOK.md; returns the path."""
    p = project_mod.load(project_dir)
    W, H = p['resolution']
    fps = p['fps']
    from .scheme import derive_palette, resolve_variant
    palette = derive_palette(resolve_variant(project_dir, p['variants'][0] if p['variants'] else 'default'))
    palette_table = '\n'.join(f'- `{k}`: `{v}`' for k, v in sorted(palette.items()))
    from . import fonts as fonts_mod
    try:
        roles = fonts_mod.resolve_role_map(project_dir, p.get('fonts', {}))
        fonts_table = '\n'.join(f'- `{role}`: {r["family"]} {r["weight"]}'
                                for role, r in roles.items())
    except Exception:
        fonts_table = '(font gate failed — save valid fonts in step 4 first)'
    scenes = []
    sp = os.path.join(project_dir, 'src', 'scenes.json')
    if os.path.isfile(sp):
        scenes = load_json(sp)
    tr_path = os.path.join(project_dir, 'transcript_model.json')
    words = load_json(tr_path)['words'] if os.path.isfile(tr_path) else []
    rows = []
    by_id = {w['id']: i for i, w in enumerate(words)}
    for s in scenes:
        if s.get('words'):
            # 0.8.3 (D1'): a paginated page — match words by the entry's [first, last] range
            i0, i1 = by_id[s['words'][0]], by_id[s['words'][1]]
            ws = words[i0:i1 + 1]
        else:
            ws = [w for w in words if w.get('section') == s['name']]
        first = ws[0]['id'] if ws else '-'
        last = ws[-1]['id'] if ws else '-'
        ch = s.get('chapter')
        label = (f"page `{s['name']}` of chapter `{ch}`" if ch and ch != s['name']
                 else f"section `{s['name']}`")
        rows.append(f"- `{s['file']}` — {label}: {s['start']:.2f}s–{s['end']:.2f}s "
                    f"({s['end'] - s['start']:.2f}s), first word `{first}`, last `{last}`")
    scene_table = '\n'.join(rows) or '(no scenes yet — save timings in step 5 first)'
    zones = project_mod.active_zones(p)
    by_scene = {}
    for z in zones:
        by_scene.setdefault(z['section'], []).append(z['rect'])
    zones_table = '\n'.join(f'- `{sec}`: {rects}' for sec, rects in by_scene.items()) or '(none)'
    try:
        from . import ai_layer
        entries = ai_layer.load_manifest(project_dir, words)
        manifest_entries = '\n'.join(f'- `{g["id"]}`: `{g["file"]}`, anchor {g["anchor"]}, '
                                     f'layer {g["layer"]}, sfx {len(g.get("sfx", []))} cue(s)'
                                     for g in entries) or '(none yet)'
    except Exception as e:
        manifest_entries = f'(manifest invalid: {e})'
    example_words = [w['id'] for w in words if w.get('section') == scenes[0]['name']] if scenes else []
    example_word = example_words[0] if example_words else (words[0]['id'] if words else 'w0')
    example_section = scenes[0]['name'] if scenes else 'Intro'
    text = read_text(TEMPLATE)
    for key, val in {
        'project_name': p['name'], 'width': W, 'height': H, 'fps': fps, 'aspect': p['aspect'],
        'palette_table': palette_table, 'fonts_table': fonts_table, 'scene_table': scene_table,
        'zones_table': zones_table, 'project_dir': project_dir,
        'manifest_entries': manifest_entries, 'example_word': example_word,
        'example_section': example_section,
    }.items():
        text = text.replace('{' + key + '}', str(val))
    out = os.path.join(project_dir, OUT_NAME)
    with open(out, 'w') as f:
        f.write(text)
    return out
