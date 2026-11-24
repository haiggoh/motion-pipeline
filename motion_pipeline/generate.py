"""generate.py — deterministic kinetic-typography generator (Task 8, design G6).

Consumes a project dir: project.json, scheme.json (per variant), timing.json (Task 7),
transcript model, font role map (Task 3), zones. Writes ONLY under src/ (never
ai_graphics/): one HTML page per section with GSAP masked slide-up reveals on word
onsets, dimming of the spoken line as the next lands, emphasis words in a heavier
weight, and a unit-heading card per section. Layout is computed HERE in Python
(line breaking + DE/EN hyphenation, font sizes per aspect, boxes), emitted as
absolutely-positioned DOM. All times anchor to word ids / section names (data
attributes + embedded timing JSON keyed by id) — a re-take only changes times.
Also writes src/element_ids.json (stable published ids for the AI layer).
"""
import html
import json
import os

from .util import load_json, read_text

ASPECT_FONT_SCALE = {'16:9': 1.0, '9:16': 0.62, '1:1': 0.72, '4:5': 0.68}
VOWELS = 'aeiouyäöü'


def _syllable_points(word):
    """Vowel-group boundaries (for hyphenation). German umlauts included."""
    pts = []
    prev_v = False
    for i, ch in enumerate(word.lower()):
        v = ch in VOWELS
        if v and not prev_v and i > 0:
            pts.append(i)
        prev_v = v
    return pts


def hyphenate(word, max_chars):
    """Split a long word with '-' at a syllable boundary (DE/EN)."""
    if len(word) <= max_chars:
        return [word]
    pts = _syllable_points(word)
    pts = [p for p in pts if p <= max_chars - 1]  # leave room for the '-'
    if not pts:
        return [word[:max_chars - 1] + '-', word[max_chars - 1:]]
    p = pts[-1]
    return [word[:p] + '-', word[p:]]


def layout_lines(words, max_chars_per_line, font_px, char_w=0.52):
    """Greedy line breaking with hyphenation. Returns list of lines; each line is a list
    of (word, emphasized)."""
    lines = []
    cur = []
    cur_w = 0
    max_w = max_chars_per_line * font_px * char_w
    for w in words:
        text = w['text']
        pieces = hyphenate(text, max_chars_per_line)
        for k, piece in enumerate(pieces):
            pw = len(piece) * font_px * char_w
            if cur and cur_w + pw > max_w:
                lines.append(cur)
                cur = []
                cur_w = 0
            cur.append((w, piece, k))  # Task 12: k = piece index within the word
            cur_w += pw + font_px * char_w * 0.3
    if cur:
        lines.append(cur)
    return lines


def _rects_intersect(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def place_text_block(lines, W, H, font_px, line_h, zones):
    """Choose a y position for the text block that avoids the zone rects active now.
    Returns (x, y). Zones are [x,y,w,h] in frame coords."""
    block_h = len(lines) * line_h
    x = int(W * 0.08)
    max_w = max(len(''.join(p for _, p, _ in ln)) for ln in lines) if lines else 1
    block_w = int(max_w * font_px * 0.52)
    candidates = [int(H * 0.55), int(H * 0.30), int(H * 0.70), int(H * 0.15)]
    for y in candidates:
        block = (x, y, block_w, block_h)
        if not any(_rects_intersect(block, z['rect']) for z in zones):
            return x, y
    # fall back: above the first zone
    if zones:
        z = zones[0]['rect']
        return x, max(0, z[1] - block_h - 10)
    return x, int(H * 0.55)


def section_slug(name: str, taken: set) -> str:
    """NFKD-fold to ASCII, lowercase, [^a-z0-9]+ -> '-', trimmed; empty -> 'section';
    collisions get -2, -3. (Task 12)"""
    import re as _re
    import unicodedata
    s = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    s = _re.sub(r'[^a-z0-9]+', '-', s).strip('-') or 'section'
    if s not in taken:
        return s
    i = 2
    while f'{s}-{i}' in taken:
        i += 1
    return f'{s}-{i}'


def scene_spans(timing, model, fps, tail=1.6):
    """[{"index", "name", "slug", "start", "end"}] — scene 0 starts at 0.0, scene k at its
    first word's start; each scene ends where the next starts; the last ends at the last
    word's end + tail; all frame-aligned (P3). (Task 12)"""
    times = {w['id']: w for w in timing['words']}
    abs_end = max((times[w['id']]['end'] for w in model['words'] if w['id'] in times),
                  default=0.0)
    spans = []
    taken = set()
    for sec in model['sections']:
        ws = [w for w in model['words'] if w['section'] == sec['name'] and w['id'] in times]
        if not ws:
            continue
        start = 0.0 if not spans else times[ws[0]['id']]['start']
        slug = section_slug(sec['name'], taken)
        taken.add(slug)
        spans.append({'index': len(spans), 'name': sec['name'], 'slug': slug, 'start': start})
    out = []
    for k, s in enumerate(spans):
        end = spans[k + 1]['start'] if k + 1 < len(spans) else abs_end + tail
        out.append({'index': s['index'], 'name': s['name'], 'slug': s['slug'],
                    'start': round(s['start'] * fps) / fps, 'end': round(end * fps) / fps})
    return out


def _avoids_zones(lines, W, H, font_px, line_h, zones):
    """True when some candidate y puts the text block inside 0.9*H and clear of the zones."""
    x = int(W * 0.08)
    max_w = max(len(''.join(p for _, p, _ in ln)) for ln in lines) if lines else 1
    block_w = int(max_w * font_px * 0.52)
    if len(lines) * line_h > 0.9 * H:
        return False
    for y in (int(H * 0.55), int(H * 0.30), int(H * 0.70), int(H * 0.15)):
        if not any(_rects_intersect((x, y, block_w, len(lines) * line_h), z['rect']) for z in zones):
            return True
    return False


def generate(project_path, variant='default', max_seconds=None):
    """Generate src/ for one project+variant (the variant's colour overlay applied to the base
    scheme — scheme.resolve_variant). Returns the list of written files."""
    from .scheme import resolve_variant
    pj = load_json(os.path.join(project_path, 'project.json'))
    from . import text_styles
    _style_name = pj.get('text_style', text_styles.DEFAULT)
    if _style_name not in text_styles.STYLES:
        raise ValueError(f"invalid text_style {_style_name!r} — want one of "
                         f"{sorted(text_styles.STYLES)} (key 'text_style')")
    style = text_styles.STYLES[_style_name]
    style_css = style.css
    tween_js = style.tween_js()
    scheme = resolve_variant(project_path, variant)
    timing = load_json(os.path.join(project_path, 'timing.json'))
    tr = load_json(os.path.join(project_path, 'transcript_model.json'))
    W, H = pj['resolution']
    aspect = pj['aspect']
    from . import audio_mux  # Task 22: sfx cue list for the page API
    from .background import background_js
    from .fonts import font_gate, resolve_role_map
    from .scheme import derive_palette
    palette = derive_palette(scheme)
    bg_js = background_js(palette, W, H)
    if not (pj.get('fonts') or {}):
        # 2026-11-22 user report: a project without a font config must not hard-error at render —
        # fall back to a bundled family with a note; the fonts screen still guides the choice.
        print('note: project.json has no fonts config — using bundled Montserrat '
              '(pick fonts in step 2)', flush=True)
        # bundled fallback: resolve to ABSOLUTE package paths (the bare map's refs are
        # package-relative and only work when CWD is the repo root — 0.8.1 crash fix)
        roles = resolve_role_map(project_path, {'family': 'Montserrat'})   # bare role map, ABS paths
    else:
        roles = font_gate(project_path, pj)
    font_px = int(H / 12 * ASPECT_FONT_SCALE.get(aspect, 1.0))
    from .project import active_zones
    zones = active_zones(pj)
    out_dir = os.path.join(project_path, 'src')
    os.makedirs(out_dir, exist_ok=True)
    # Task 11: embed each role's face into src/fonts/ and alias it mp-<role> (P6)
    import shutil as _sh_fonts
    fonts_out = os.path.join(out_dir, 'fonts')
    os.makedirs(fonts_out, exist_ok=True)
    face_css = []
    fonts_js = []
    for role in ('headline', 'label', 'body', 'emphasis'):
        r = roles[role]
        base = os.path.basename(r['file'])
        dst_name = f'{role}-{base}'
        _sh_fonts.copy(r['file'], os.path.join(fonts_out, dst_name))
        face_css.append(f"@font-face{{font-family:'mp-{role}';src:url('fonts/{dst_name}');"
                        f"font-weight:{r['weight']};font-style:normal}}")
        fonts_js.append({'role': role, 'w': r['weight'], 'file': f'fonts/{dst_name}'})
        r['css_file'] = f'fonts/{dst_name}'
    font_css = '\n'.join(face_css)
    fonts_js_s = json.dumps(fonts_js)
    # AI-owned layer (ai_layer.py): validated BEFORE anything is written, copied into
    # src/ai_graphics/ (src/ is ours to rebuild; ai_graphics/ itself is only ever read)
    import shutil as _sh

    from . import ai_layer
    ai = ai_layer.load_manifest(project_path, tr['words'])
    ai_out = os.path.join(out_dir, 'ai_graphics')
    _sh.rmtree(ai_out, ignore_errors=True)
    for g in ai:
        if not g.get('file'):
            continue  # declarative shapes entry: nothing to copy
        dst = os.path.join(ai_out, g['file'])
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        _sh.copy2(os.path.join(project_path, ai_layer.DIR, g['file']), dst)
    element_ids = {}
    written = []
    graphics_html = ''
    for g in pj.get('graphics', []):
        if g == 'globe':
            import shutil
            gdir = os.path.join(os.path.dirname(__file__), 'graphics')
            for f in ('globe.js', 'land-110m.js'):
                shutil.copy(os.path.join(gdir, f), os.path.join(out_dir, f))
            written.extend([f'src/{f}' for f in ('globe.js', 'land-110m.js')])
            R = int(min(W, H) * 0.30)
            graphics_html += (
                '<div id="globe"></div>\n'
                f'<script src="land-110m.js"></script><script src="globe.js"></script>\n'
                f'<script>const G = GLOBE.create({{cx: {int(W * 0.78)}, cy: {int(H * 0.30)}, R: {R}, '
                f"colors: {{ocean0: '{palette['background_light']}', ocean1: '{palette['background_dark']}', "
                f"land: '{palette['particle_colour']}', coast: '{palette['label_tint']}'}}}}); "
                'document.getElementById("globe").appendChild(G.el); '
                'const gt = () => G.draw(performance.now() / 1000 * 12); '
                'if (window.gsap && gsap.ticker) { gsap.ticker.add(gt); } '
                'else { const loop = () => { gt(); requestAnimationFrame(loop); }; loop(); }</script>\n')
    # Task 12 scene model: scenes.json drives the render order; pages are scene_<NN>_<slug>.html
    # with scene-relative timings, a registered paused timeline and dimming.
    times = {w['id']: w for w in timing['words']}
    scenes = scene_spans(timing, tr, pj['fps'])
    if max_seconds is not None:  # test_frames mode: cap every scene (render_cli passes 60/fps)
        scenes = [dict(s, end=min(s['end'], s['start'] + max_seconds)) for s in scenes]
    scenes_json = [dict(s, file=f"scene_{i:02d}_{s['slug']}.html") for i, s in enumerate(scenes)]
    with open(os.path.join(out_dir, 'scenes.json'), 'w') as f:
        json.dump(scenes_json, f, indent=2)
        f.write('\n')
    written.append('src/scenes.json')
    for sp in scenes:
        sec_name = sp['name']
        slug = sp['slug']
        start, end = sp['start'], sp['end']
        words = [w for w in tr['words'] if w['section'] == sec_name]
        rel = {w['id']: {'start': times[w['id']]['start'] - start,
                         'end': times[w['id']]['end'] - start} for w in words}
        zs = [z for z in zones if z['section'] == sec_name]
        # fit: shrink font by 0.9 until the block fits 0.9*H and avoids the zones (floor 0.5x)
        f_px = font_px
        while True:
            lines = style.layout(words, max(8, int(W * 0.84 / (f_px * 0.52))), f_px)
            lh = int(f_px * 1.25)
            if _avoids_zones(lines, W, H, f_px, lh, zs):
                break
            if f_px <= max(1, font_px // 2):
                raise ValueError(f'section "{sec_name}" does not fit one frame at {aspect} — '
                                 'split it with a # heading or move the zone')
            f_px = max(1, int(f_px * 0.9))
        x, y = place_text_block(lines, W, H, f_px, lh, zs)
        # DOM: one absolutely positioned line per layout line; words html-escaped; hyphenation
        # piece k>0 gets id el-<id>-<k+1>; element_ids maps the word id to the FIRST piece id
        line_html = []
        letter_off = {}
        for li, ln in enumerate(lines):
            spans = []
            for w, piece, k in ln:
                emph = ' class="emph"' if w['emphasized'] else ''
                pid = f'el-{w["id"]}' if k == 0 else f'el-{w["id"]}-{k + 1}'
                element_ids.setdefault(w['id'], pid)
                if style.granularity == 'letter':
                    # letter spans keep data-id = word id (AI anchors stay word-addressed)
                    # plus data-k = letter index within the word
                    off = letter_off.get(w['id'], 0)
                    for j, ch in enumerate(piece):
                        spans.append(f'<span id="{pid}-L{off + j}" data-id="{w["id"]}" '
                                     f'data-k="{off + j}"{emph}>{html.escape(ch)}</span>')
                    letter_off[w['id']] = off + len(piece)
                else:
                    spans.append(f'<span id="{pid}" data-id="{w["id"]}"{emph}>{html.escape(piece)}</span>')
            sep = '' if style.granularity == 'letter' else ' '   # letters are adjacent, not spaced
            line_html.append(f'<div class="line" data-line="{li}" style="left:{x}px;top:{y + li * lh}px;'
                             f'font-size:{f_px}px">{sep.join(spans)}</div>')
        card_id = f'card-{slug}'  # ids only from slugs (Task 12) — never the raw section name
        element_ids[sec_name] = card_id
        tj = json.dumps({w['id']: rel[w['id']] for w in words})  # scene-relative (Task 12)
        duration = end - start
        mine = [g for g in ai if g['section'] == sec_name]
        ai_html = ''.join(
            f'<div class="ai-graphic ai-{g["layer"]}" data-ai-id="{g["id"]}" data-anchor="{g["element"]}">'
            + (read_text(os.path.join(project_path, ai_layer.DIR, g['file']))
               if (g.get('file') or '').endswith('.html') else '')
            + '</div>\n'
            for g in mine if (g.get('file') or '').endswith('.html') or 'shapes' in g)
        ai_js = ''.join(
            (f'<script src="ai_graphics/{g["file"]}" data-ai-id="{g["id"]}" '
             f'data-anchor="{g["element"]}"></script>\n')
            if (g.get('file') or '').endswith('.js') else
            (f'<script data-ai-id="{g["id"]}" data-anchor="{g["element"]}">\n'
             # arm AFTER the page's font-gated tweens (they use vars delay and would land
             # after ours if we extended the timeline end first — the dogfood arming pattern)
             f'(() => {{ let armed = false; const arm = () => {{ if (armed) return; armed = true;\n'
             f'  MP.runShapes({json.dumps(g["shapes"])}, '
             f'{{ layer: document.querySelector(\'[data-ai-id="{g["id"]}"]\'), '
             f'sceneName: {sec_name!r} }}); }};\n'
             f'  if (document.fonts?.ready) document.fonts.ready.then(arm);\n'
             f'  else if (document.readyState === "complete") arm();\n'
             f'  else window.addEventListener("load", arm, {{ once: true }});\n'
             f'}})();\n</script>\n')
            for g in mine if (g.get('file') or '').endswith('.js') or 'shapes' in g)
        layers = sorted({g['layer'] for g in mine
                         if (g.get('file') or '').endswith('.html') or 'shapes' in g})
        ai_css = ('.ai-graphic{position:absolute;inset:0;pointer-events:none}\n' if layers else '') + \
            ''.join(f".ai-{lyr}{{z-index:{1 if lyr == 'below' else 3}}}\n" for lyr in layers)
        ai_anchors = json.dumps({g['id']: {'element': g['element'], 'layer': g['layer'],
                                           **({'start': rel[g['anchor']['word']]['start']}
                                              if 'word' in g['anchor'] else {})} for g in mine})
        # Task 22 page-API data (scene-relative)
        sections_js = json.dumps({s['name']: round(s['start'] - start, 3)
                                  for s in load_json(os.path.join(project_path, 'src', 'scenes.json'))})
        sec_name_js = sec_name
        palette_js = json.dumps(palette)
        fonts_js2 = json.dumps({r: f'mp-{r}' for r in ('headline', 'label', 'body', 'emphasis')})
        zones_js = json.dumps([[z['rect'][0], z['rect'][1], z['rect'][2], z['rect'][3]] for z in zs])
        sfx_js = json.dumps([{'file': os.path.basename(c['file']), 'time': round(c['time'] - start, 3),
                              'gain_db': c['gain_db'], 'graphic': c['graphic']}
                             for c in audio_mux.sfx_cues(project_path, timing, tr)
                             if start <= c['time'] < end])
        # dimming (README "dimming as the next lands"): every line except the last dims its
        # spans at the NEXT line's first word start
        dim_js = []
        for li in range(len(lines) - 1):
            t0 = rel[lines[li + 1][0][0]['id']]['start']
            dim_js.append(f"tl.to(document.querySelectorAll('.line[data-line=\"{li}\"] span'), "
                          f"{{color: '{palette['secondary_text']}', duration: 0.3, delay: {t0:.3f}}});")
        dim_js_s = '\n'.join(dim_js)
        page = f"""<!doctype html><html><head><meta charset="utf-8"><style>
{font_css}
body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;
font-family:'mp-body';color:{palette['text']}}}
#root{{position:absolute;width:{W}px;height:{H}px;overflow:hidden}}
#bg{{position:absolute;inset:0}}
.line{{position:absolute;z-index:2;font-weight:{roles['body']['weight']};white-space:nowrap;
overflow:hidden;height:{lh}px}}
{ai_css}{style_css}
.line span.emph{{font-family:'mp-emphasis';font-weight:{roles['emphasis']['weight']};color:{palette['accent']}}}
.card{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
font-family:'mp-headline';font-size:{int(H / 8)}px;font-weight:{roles['headline']['weight']};color:{palette['text']};
background:{palette['background_dark']};opacity:0}}
</style></head><body>
<div id="root" data-composition-id="{slug}" data-width="{W}" data-height="{H}" data-fps="{pj['fps']}" data-duration="{duration:.3f}">
<canvas id="bg" width="{W}" height="{H}"></canvas>
<div id="{card_id}" class="card">{html.escape(sec_name)}</div>
{ai_html}
{chr(10).join(line_html)}
</div>
<script src="gsap.min.js"></script>
<script src="DrawSVGPlugin.min.js"></script>
{graphics_html}
<script>
// Task 22 page API: defined BEFORE any ai_graphics script loads; mp_lib.js loads AFTER it
// (its IIFE reads window.MP immediately — loading it before MP logs MP_LIB_NO_MP)
const tl = gsap.timeline({{paused: true}});
window.__timelines = window.__timelines || {{}};   // hyperframes does not predefine it
window.__timelines['{slug}'] = tl;
const T = {tj};
const SECTIONS = {sections_js};
window.MP = {{
  tl, timings: T, anchors: {ai_anchors},
  at(ref, offset) {{ offset = offset || 0;
    if (typeof ref === 'number') return ref + offset;
    if (ref[0] === '#') return (SECTIONS[ref.slice(1)] != null ? SECTIONS[ref.slice(1)] : 0) + offset;
    const w = T[ref]; return (w ? w.start : 0) + offset; }},
  scene: {{name: {sec_name_js!r}, slug: {slug!r}, start: {start}, end: {end}, duration: {duration:.3f}}},
  frame: {{W: {W}, H: {H}, fps: {pj['fps']}, aspect: {aspect!r}}},
  palette: {palette_js},
  fonts: {fonts_js2},
  zones: {zones_js},
  sfx: {sfx_js},
  random: null  // set by mp_lib.js
}};
</script>
<script src="mp_lib.js"></script>
{ai_js}
<script>
(async () => {{
  // Task 11 font gate: every role's face must load before the timeline is built;
  // on failure log MP_FONT_MISSING (render_scene.sh greps it -> exit 5) and do NOT register
  for (const f of {fonts_js_s}) {{
    let loaded = [];
    try {{ loaded = await document.fonts.load(`${{f.w}} 16px mp-${{f.role}}`); }} catch (e) {{}}
    if (!loaded.length) {{ console.error(`MP_FONT_MISSING ${{f.role}} ${{f.file}}`); return; }}
  }}
{bg_js}
const card = document.getElementById('{card_id}');
tl.to(card, {{duration: 0.6, opacity: 1, ease: 'power2.out'}});
tl.to(card, {{duration: 0.4, opacity: 0, delay: 1.2, ease: 'power2.in'}});
{tween_js}
{dim_js_s}
}})();
</script>
</body></html>
"""
        name = scenes_json[sp['index']]['file']
        with open(os.path.join(out_dir, name), 'w') as f:
            f.write(page)
        written.append(os.path.join('src', name))
    with open(os.path.join(out_dir, 'element_ids.json'), 'w') as f:
        json.dump(element_ids, f, indent=2)
        f.write('\n')
    written.append('src/element_ids.json')
    return written
