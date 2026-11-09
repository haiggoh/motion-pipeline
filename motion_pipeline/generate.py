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
import json
import os

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
            cur.append((w, piece, k == len(pieces) - 1))
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


def generate(project_path, _variant='default'):
    """Generate src/ for one project+variant. Returns the list of written files."""
    pj = json.load(open(os.path.join(project_path, 'project.json')))
    scheme = json.load(open(os.path.join(project_path, 'scheme.json')))
    timing = json.load(open(os.path.join(project_path, 'timing.json')))
    tr = json.load(open(os.path.join(project_path, 'transcript_model.json')))
    W, H = pj['resolution']
    aspect = pj['aspect']
    from .scheme import derive_palette
    from .fonts import font_gate
    from .background import background_js
    palette = derive_palette(scheme)
    bg_js = background_js(palette, W, H)
    roles = font_gate(project_path, pj)
    font_px = int(H / 12 * ASPECT_FONT_SCALE.get(aspect, 1.0))
    line_h = int(font_px * 1.25)
    zones = [z for z in pj.get('zones', [])]
    out_dir = os.path.join(project_path, 'src')
    os.makedirs(out_dir, exist_ok=True)
    element_ids = {}
    written = []
    timings_by_id = {w['id']: w for w in timing['words']}
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
    for sec in tr['sections']:
        words = [w for w in tr['words'] if w['section'] == sec['name']]
        if not words:
            continue
        lines = layout_lines(words, max(8, int(W * 0.84 / (font_px * 0.52))), font_px)
        zs = [z for z in zones if z['section'] == sec['name']]
        x, y = place_text_block(lines, W, H, font_px, line_h, zs)
        # build DOM: one absolutely positioned line per layout line; each word a span with data-id
        line_html = []
        for li, ln in enumerate(lines):
            spans = []
            for w, piece, _is_last in ln:
                emph = ' class="emph"' if w['emphasized'] else ''
                spans.append(f'<span data-id="{w["id"]}"{emph}>{piece}</span>')
                element_ids[w['id']] = f'el-{w["id"]}'
            line_html.append(f'<div class="line" style="left:{x}px;top:{y + li * line_h}px;'
                             f'font-size:{font_px}px">{ " ".join(spans) }</div>')
        card_id = f'card-{sec["name"]}'
        element_ids[sec['name']] = card_id
        tj = json.dumps({w['id']: {'start': timings_by_id[w['id']]['start'],
                                    'end': timings_by_id[w['id']]['end']} for w in words})
        duration = max(t['end'] for t in timings_by_id.values()) + 1.6
        page = f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;
font-family:'{roles['body']['family']}';color:{palette['text']}}}
#root{{position:absolute;width:{W}px;height:{H}px;overflow:hidden}}
#bg{{position:absolute;inset:0}}
.line{{position:absolute;font-weight:{roles['body']['weight']};white-space:nowrap;
overflow:hidden;height:{line_h}px}}
.line span{{display:inline-block;transform:translateY(110%);opacity:0}}
.line span.emph{{font-weight:{roles['emphasis']['weight']};color:{palette['accent']}}}
#card{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
font-size:{int(H / 8)}px;font-weight:{roles['headline']['weight']};color:{palette['text']};
background:{palette['background_dark']};opacity:0}}
</style></head><body>
<div id="root" data-composition-id="{card_id}" data-width="{W}" data-height="{H}" data-fps="{pj['fps']}" data-duration="{duration:.3f}">
<canvas id="bg" width="{W}" height="{H}"></canvas>
<div id="{card_id}">{sec['name']}</div>
{chr(10).join(line_html)}
</div>
<script src="gsap.min.js"></script>
{graphics_html}
<script>
{bg_js}
const T = {tj};
const card = document.getElementById('{card_id}');
gsap.to(card, {{duration: 0.6, opacity: 1, ease: 'power2.out'}});
gsap.to(card, {{duration: 0.4, opacity: 0, delay: 1.2, ease: 'power2.in'}});
for (const el of document.querySelectorAll('.line span')) {{
  const t = T[el.dataset.id];
  gsap.to(el, {{duration: 0.35, y: '0%', opacity: 1, delay: t.start, ease: 'power3.out'}});
}}
</script></body></html>
"""
        name = f'scene_{sec["name"]}.html'
        with open(os.path.join(out_dir, name), 'w') as f:
            f.write(page)
        written.append(os.path.join('src', name))
    with open(os.path.join(out_dir, 'element_ids.json'), 'w') as f:
        json.dump(element_ids, f, indent=2)
        f.write('\n')
    written.append('src/element_ids.json')
    return written
